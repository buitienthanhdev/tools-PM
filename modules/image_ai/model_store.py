"""Pinned ONNX model registry and on-demand, checksum-verified downloader."""

import hashlib
import os
import threading
import urllib.parse
import urllib.request

from . import paths

HF = "https://huggingface.co"
OPENCV_ZOO = "https://media.githubusercontent.com/media/opencv/opencv_zoo"

# Each model file is pinned to an immutable upstream revision and HF LFS SHA-256.
# The upstream engine code and model weights have separate licenses.
MODELS = {
    "enhance": {
        "label": "Real-ESRGAN same-size enhancement",
        "license": "BSD-3-Clause (Real-ESRGAN upstream)",
        "files": [
            (
                f"{HF}/OwlMaster/AllFilesRope/resolve/d783e61585b3d83a85c91ca8a3b299e8ade94d72/realesr-general-x4v3.onnx",
                "realesr-general-x4v3.onnx",
                4871181,
                "09b757accd747d7e423c1d352b3e8f23e77cc5742d04bae958d4eb8082b76fa4",
            )
        ],
    },
    "bg": {
        "label": "BiRefNet background removal",
        "license": "MIT",
        "files": [
            (
                f"{HF}/onnx-community/BiRefNet_lite/resolve/de15b22ba131738a16dff04aab8bdf8dc32e3ac1/onnx/model.onnx",
                "birefnet-lite.onnx",
                224005088,
                "5600024376f572a557870a5eb0afb1e5961636bef4e1e22132025467d0f03333",
            )
        ],
    },
    "denoise": {
        "label": "SCUNet photo denoise",
        "license": "Apache-2.0",
        "files": [
            (
                f"{HF}/Heliosoph/scunet-onnx/resolve/6d11417ee2fbcc73783c502a238ac115097754fe/scunet_color_real_psnr.onnx",
                "scunet_color_real_psnr.onnx",
                3798678,
                "231be201ab413dbc999d7951caa9844846b93a12a40a41e037d6b5888ed4e88c",
            ),
            (
                f"{HF}/Heliosoph/scunet-onnx/resolve/6d11417ee2fbcc73783c502a238ac115097754fe/scunet_color_real_psnr.onnx.data",
                "scunet_color_real_psnr.onnx.data",
                73138176,
                "98825ea1210b641c71e5f052f582c70c49fd44b35387ebe2c034268c17df3feb",
            ),
        ],
    },
    "deblur": {
        "label": "NAFNet photo deblur",
        "license": "MIT",
        "files": [
            (
                f"{HF}/opencv/deblurring_nafnet/resolve/f1f255116cdb628a311d2b5749871189a4639d84/deblurring_nafnet_2025may.onnx",
                "nafnet-deblur.onnx",
                91736251,
                "07263f416febecce10193dd648e950b22e397cf521eedab1a114ef77b2bc9587",
            )
        ],
    },
    "colorize": {
        "label": "DDColor old photo colorization",
        "license": "Apache-2.0",
        "files": [
            (
                f"{HF}/edgetools/ddcolor/resolve/4755ae9f1f7a35a9e7693b96c2a88f3432cb6ab0/ddcolor-tiny-fp16.onnx",
                "ddcolor-tiny.onnx",
                135444402,
                "2653da00dc15e54a45e5200b61dbf82ee9ceaf56b02bb9b9657569ac775e82e6",
            )
        ],
    },
    "erase": {
        "label": "LaMa object removal",
        "license": "Apache-2.0",
        "files": [
            (
                f"{HF}/Carve/LaMa-ONNX/resolve/c3c0c9e468934d62e79c329e35d82dd09ff8c444/lama_fp32.onnx",
                "lama.onnx",
                208044816,
                "1faef5301d78db7dda502fe59966957ec4b79dd64e16f03ed96913c7a4eb68d6",
            )
        ],
    },
    "face": {
        "label": "GFPGAN face restoration",
        "license": "Apache-2.0 (GFPGAN upstream)",
        "files": [
            (
                f"{OPENCV_ZOO}/47534e27c9851bb1128ccc0102f1145e27f23f98/models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
                "face_detection_yunet_2023mar.onnx",
                232589,
                "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4",
            ),
            (
                f"{HF}/OwlMaster/AllFilesRope/resolve/d783e61585b3d83a85c91ca8a3b299e8ade94d72/GFPGANv1.4.onnx",
                "GFPGANv1.4.onnx",
                340256690,
                "6548e54cbcf248af385248f0c1193b359c37a0f98b836282b09cf48af4fd2b73",
            ),
        ],
    },
}

_lock = threading.Lock()
_state = {
    key: {"status": "idle", "progress": 0, "error": None} for key in MODELS
}
_MAX_TOTAL_MODEL_BYTES = 400 * 1024 * 1024
_ALLOWED_HOST_SUFFIXES = (
    "huggingface.co",
    "hf.co",
    "githubusercontent.com",
    "opencv.org",
)


def valid(key):
    return key in MODELS


def model_path(key, index=0):
    return paths.find_model(MODELS[key]["files"][index][1])


def _required_names(key):
    return [entry[1] for entry in MODELS[key]["files"]]


def available(key):
    return all(paths.find_model(name) is not None for name in _required_names(key))


def total_size(key):
    return sum(entry[2] for entry in MODELS[key]["files"])


def status(key):
    with _lock:
        state = dict(_state[key])
    model = MODELS[key]
    state.update(
        available=available(key),
        size=total_size(key),
        label=model["label"],
        license=model["license"],
    )
    return state


def start_download(key):
    if not valid(key):
        raise ValueError("Unknown image model")
    with _lock:
        if _state[key]["status"] == "downloading" or available(key):
            return
        _state[key].update(status="downloading", progress=0, error=None)
    threading.Thread(target=_download, args=(key,), daemon=True).start()


def _host_allowed(url):
    host = (urllib.parse.urlparse(url).hostname or "").lower()
    return any(host == suffix or host.endswith(f".{suffix}") for suffix in _ALLOWED_HOST_SUFFIXES)


def _existing_file_is_valid(path, expected_size, expected_sha256):
    if not path.is_file() or path.stat().st_size != expected_size:
        return False
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest() == expected_sha256


def _download(key):
    model_dir = paths.data("models")
    model_dir.mkdir(parents=True, exist_ok=True)
    files = MODELS[key]["files"]
    total = total_size(key)
    completed_before = 0
    try:
        for url, filename, expected_size, expected_sha256 in files:
            destination = model_dir / filename
            partial = destination.with_name(destination.name + ".part")
            if expected_sha256 == "pending":
                raise RuntimeError(f"Checksum not configured for model file {filename}")
            if _existing_file_is_valid(destination, expected_size, expected_sha256):
                completed_before += expected_size
                continue
            destination.unlink(missing_ok=True)
            partial.unlink(missing_ok=True)
            digest = hashlib.sha256()
            received = 0
            request = urllib.request.Request(
                url, headers={"User-Agent": "PM-Tools-Image-AI/1.0"}
            )
            try:
                import certifi

                import ssl

                context = ssl.create_default_context(cafile=certifi.where())
            except ImportError:
                context = None
            with urllib.request.urlopen(request, timeout=30, context=context) as response:
                if not _host_allowed(response.geturl()):
                    raise RuntimeError("Model download redirected to an untrusted host")
                length = response.headers.get("Content-Length")
                if length and int(length) != expected_size:
                    raise RuntimeError(f"Unexpected model size for {filename}")
                with partial.open("wb") as output:
                    while True:
                        chunk = response.read(1024 * 1024)
                        if not chunk:
                            break
                        received += len(chunk)
                        if received > expected_size or received > _MAX_TOTAL_MODEL_BYTES:
                            raise RuntimeError(f"Model file exceeds its expected size: {filename}")
                        output.write(chunk)
                        digest.update(chunk)
                        with _lock:
                            _state[key]["progress"] = min(
                                99, int((completed_before + received) * 100 / total)
                            )
            if received != expected_size or digest.hexdigest() != expected_sha256:
                raise RuntimeError(f"Model integrity check failed for {filename}")
            os.replace(partial, destination)
            completed_before += expected_size
        with _lock:
            _state[key].update(status="done", progress=100, error=None)
        print(f"[image-ai] model {key} ready ({total} bytes)", flush=True)
    except Exception as exc:
        for _, filename, _, _ in files:
            model_dir.joinpath(filename + ".part").unlink(missing_ok=True)
        error = str(exc)[:200]
        with _lock:
            _state[key].update(status="error", progress=0, error=error)
        print(f"[image-ai] model {key} download failed: {error}", flush=True)
