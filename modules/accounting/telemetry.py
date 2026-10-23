"""
Quan sát vận hành bằng OpenTelemetry: span cho tác vụ, từng công cụ, trích xuất, lập kế hoạch, OCR/docling.

Xuất ra <data_dir>/telemetry/spans-YYYYMMDD.jsonl (giữ 30 ngày). Thuộc tính span CHỈ gồm mã định danh,
tên công cụ, trạng thái, số đếm, thời gian — không bao giờ có nội dung chứng từ, tên khách hàng hay số tiền.
Provider riêng của module (không đặt provider toàn cục) để không ảnh hưởng phần khác của Hub.
"""

import json
import statistics
import threading
import time
from contextlib import contextmanager
from pathlib import Path

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExporter, SpanExportResult
from opentelemetry.trace import Status, StatusCode

from . import settings

KEEP_DAYS = 30
_lock = threading.Lock()
_tracer = None


class JsonlExporter(SpanExporter):
    def export(self, spans):
        d = Path(settings.data_dir()) / "telemetry"
        d.mkdir(parents=True, exist_ok=True)
        path = d / time.strftime("spans-%Y%m%d.jsonl")
        with _lock, open(path, "a", encoding="utf-8") as f:
            for s in spans:
                f.write(json.dumps({
                    "name": s.name, "trace": format(s.context.trace_id, "032x"), "span": format(s.context.span_id, "016x"),
                    "parent": format(s.parent.span_id, "016x") if s.parent else None,
                    "start": s.start_time / 1e9, "ms": round((s.end_time - s.start_time) / 1e6, 1),
                    "status": s.status.status_code.name, "attrs": dict(s.attributes or {}),
                }, ensure_ascii=False) + "\n")
        return SpanExportResult.SUCCESS

    def shutdown(self):
        pass


def _cleanup():
    d = Path(settings.data_dir()) / "telemetry"
    if not d.exists():
        return
    cutoff = time.time() - KEEP_DAYS * 86400
    for p in d.glob("spans-*.jsonl"):
        if p.stat().st_mtime < cutoff:
            p.unlink(missing_ok=True)


def tracer():
    global _tracer
    if _tracer is None:
        provider = TracerProvider()
        if settings.get().get("telemetry", "jsonl") == "jsonl":
            provider.add_span_processor(SimpleSpanProcessor(JsonlExporter()))
            _cleanup()
        _tracer = provider.get_tracer("pm-tools.accounting")
    return _tracer


SAFE = (str, int, float, bool)


@contextmanager
def span(name, **attrs):
    """with telemetry.span("tool", tool="reconcile_bank", org=...) as sp: ... — lỗi được ghi vào span rồi ném tiếp."""
    with tracer().start_as_current_span(name) as sp:
        for k, v in attrs.items():
            if isinstance(v, SAFE):
                sp.set_attribute(k, v)
        try:
            yield sp
        except Exception as e:
            sp.set_status(Status(StatusCode.ERROR, type(e).__name__))
            sp.set_attribute("error.type", type(e).__name__)
            raise


def summary(days=7):
    """P50/P95 (giây) và số lỗi theo loại span/công cụ trong N ngày gần nhất — cho trang Quản trị."""
    d = Path(settings.data_dir()) / "telemetry"
    rows = {}
    since = time.time() - days * 86400
    for p in sorted(d.glob("spans-*.jsonl")) if d.exists() else []:
        if p.stat().st_mtime < since:
            continue
        with open(p, encoding="utf-8") as f:
            for line in f:
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if r["start"] < since:
                    continue
                key = r["name"] + (f":{r['attrs']['tool']}" if r["attrs"].get("tool") else "")
                e = rows.setdefault(key, {"ms": [], "errors": 0})
                e["ms"].append(r["ms"])
                e["errors"] += r["status"] == "ERROR"
    out = {}
    for k, e in rows.items():
        ms = sorted(e["ms"])
        out[k] = {"count": len(ms), "errors": e["errors"], "p50_s": round(statistics.median(ms) / 1000, 2),
                  "p95_s": round(ms[int(0.95 * (len(ms) - 1))] / 1000, 2)}
    return out


def reset_for_tests():
    global _tracer
    _tracer = None

