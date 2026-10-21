"""Gọi Ollama dùng chung cho GenReport, Pháp luật, Reviewing CV (qua điều phối GPU, báo lỗi rõ ràng)."""

import json
import re

import requests

from . import config, gpu


class LLMError(RuntimeError):
    """Lỗi AI local, thông điệp đã đủ rõ để hiển thị cho người dùng."""


def installed():
    try:
        r = requests.get(f"{config.get()['ollama_url']}/api/tags", timeout=4)
        r.raise_for_status()
        return [m["name"] for m in r.json().get("models", [])]
    except requests.RequestException:
        return None


def status(model):
    names = installed()
    if names is None:
        return {
            "ok": False,
            "model": model,
            "error": "Ollama chưa chạy (localhost:11434)",
        }
    if model not in names and f"{model}:latest" not in names:
        return {
            "ok": False,
            "model": model,
            "error": f"Ollama chưa có model {model} (ollama pull {model})",
        }
    return {"ok": True, "model": model}


def embed(model, texts, *, name="embed", batch=16, timeout=300):
    """Vector hoá danh sách văn bản bằng Ollama; trả về ndarray (n, dim) đã chuẩn hoá L2."""
    import numpy as np

    st = status(model)
    if not st["ok"]:
        raise LLMError(st["error"])
    url = f"{config.get()['ollama_url']}/api/embed"
    out = []
    try:
        with gpu.task(name, "ollama"):
            for i in range(0, len(texts), batch):
                r = requests.post(
                    url, json={"model": model, "input": texts[i : i + batch]}, timeout=timeout
                )
                if r.status_code != 200:
                    raise LLMError(f"Ollama embed lỗi HTTP {r.status_code}: {r.text[:200]}")
                out.extend(r.json()["embeddings"])
    except requests.RequestException as e:
        raise LLMError(f"Không gọi được Ollama embed: {e}") from e
    m = np.asarray(out, dtype="float32")
    norms = np.linalg.norm(m, axis=1, keepdims=True)
    return m / np.maximum(norms, 1e-9)


def strip_think(text):
    return re.sub(r"<think>.*?</think>", "", text or "", flags=re.S).strip()


def chat(
    model,
    messages,
    *,
    fmt=None,
    num_ctx=16384,
    num_predict=4096,
    temperature=0.2,
    timeout=900,
    name="llm",
    on_wait=None,
    seed=None,
):
    """Trả về nội dung text của câu trả lời. Ném LLMError nếu không gọi được."""
    st = status(model)
    if not st["ok"]:
        raise LLMError(st["error"])
    payload = {
        "model": model,
        "stream": False,
        "think": False,
        "messages": messages,
        "options": {
            "temperature": temperature,
            "num_ctx": num_ctx,
            "num_predict": num_predict,
        },
    }
    if seed is not None:
        payload["options"]["seed"] = seed
    if fmt:
        payload["format"] = fmt
    url = f"{config.get()['ollama_url']}/api/chat"
    try:
        with gpu.task(name, "ollama", on_wait=on_wait):
            r = requests.post(url, json=payload, timeout=timeout)
            if r.status_code == 400 and "think" in r.text.lower():
                payload.pop("think", None)
                r = requests.post(url, json=payload, timeout=timeout)
    except requests.ConnectionError:
        raise LLMError("Mất kết nối Ollama (localhost:11434)") from None
    except requests.Timeout:
        raise LLMError(f"Ollama trả lời quá {timeout}s") from None
    if r.status_code != 200:
        raise LLMError(f"Ollama lỗi HTTP {r.status_code}: {r.text[:200]}")
    data = r.json()
    text = strip_think((data.get("message") or {}).get("content", ""))
    if not text:
        raise LLMError("Model không trả về nội dung")
    if data.get("done_reason") == "length":
        raise LLMError("Câu trả lời bị cắt giữa chừng (quá dài)")
    return text


def chat_json(model, messages, *, retries=1, **kw):
    """Gọi và ép ra JSON; tự thử lại khi model trả sai định dạng."""
    last = None
    for _ in range(retries + 1):
        text = chat(model, messages, **kw)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            m = re.search(r"\{.*\}", text, re.S)
            if m:
                try:
                    return json.loads(m.group(0))
                except json.JSONDecodeError:
                    pass
            last = text[:200]
    raise LLMError(f"Model trả về không phải JSON hợp lệ: {last}")
