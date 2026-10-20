import io
from pathlib import Path

from flask import Flask
from PIL import Image
import pytest

from routes import image as image_route
from routes.image import MAX_IMAGE_UPLOAD_PIXELS, _inspect_image


@pytest.mark.parametrize(
    ("image_format", "expected"),
    [("PNG", "PNG"), ("JPEG", "JPEG"), ("WEBP", "WEBP"), ("BMP", "BMP")],
)
def test_image_inspection_accepts_supported_formats(tmp_path, image_format, expected):
    path = tmp_path / f"sample.{image_format.lower()}"
    mode = "RGBA" if image_format == "PNG" else "RGB"
    color = (10, 80, 160, 90) if image_format == "PNG" else (10, 80, 160)
    Image.new(mode, (24, 16), color).save(path, image_format)

    assert _inspect_image(path) == (24, 16, expected)


def test_image_inspection_preserves_alpha_format(tmp_path):
    path = tmp_path / "transparent.png"
    image = Image.new("RGBA", (2, 2), (20, 40, 60, 0))
    image.save(path)

    with Image.open(path) as decoded:
        assert decoded.mode == "RGBA"
    assert _inspect_image(path) == (2, 2, "PNG")


def test_image_inspection_rejects_corrupt_data(tmp_path):
    path = tmp_path / "broken.png"
    path.write_bytes(b"\x89PNG\r\n\x1a\nnot-an-image")

    with pytest.raises(ValueError, match="Không đọc được ảnh"):
        _inspect_image(path)


def test_image_inspection_rejects_oversized_dimensions(tmp_path):
    path = tmp_path / "too-large.png"
    Image.new("1", (MAX_IMAGE_UPLOAD_PIXELS + 1, 1)).save(path)

    with pytest.raises(ValueError, match="32 megapixel"):
        _inspect_image(path)


def test_image_inspection_accepts_maximum_dimensions(tmp_path):
    path = tmp_path / "maximum.png"
    Image.new("1", (8000, 4000)).save(path)

    assert _inspect_image(path) == (8000, 4000, "PNG")


@pytest.mark.parametrize(
    ("image_format", "filename"),
    [
        ("PNG", "alpha.png"),
        ("JPEG", "photo.jpg"),
        ("WEBP", "photo.webp"),
        ("BMP", "photo.bmp"),
    ],
)
def test_image_upload_endpoint_saves_supported_images(
    tmp_path, monkeypatch, image_format, filename
):
    monkeypatch.setattr(image_route, "UPLOAD_DIR", tmp_path)
    source = io.BytesIO()
    mode = "RGBA" if image_format == "PNG" else "RGB"
    color = (20, 40, 60, 0) if image_format == "PNG" else (20, 40, 60)
    Image.new(mode, (12, 9), color).save(source, image_format)
    source.seek(0)
    app = Flask(__name__)

    with app.test_request_context(
        "/api/image/upload",
        method="POST",
        data={"image": (source, filename)},
        content_type="multipart/form-data",
    ):
        result = image_route.api_image_upload()
        response, status = result if isinstance(result, tuple) else (result, 200)

    assert status == 200
    assert response.get_json()["width"] == 12
    saved = tmp_path / response.get_json()["file_path"].rsplit("/", 1)[-1]
    assert saved.is_file()
    if image_format == "PNG":
        with Image.open(saved) as uploaded:
            assert uploaded.mode == "RGBA"
            assert uploaded.getpixel((0, 0))[3] == 0


def test_image_upload_endpoint_rejects_mismatched_extension(tmp_path, monkeypatch):
    monkeypatch.setattr(image_route, "UPLOAD_DIR", tmp_path)
    source = io.BytesIO()
    Image.new("RGB", (12, 9), (20, 40, 60)).save(source, "PNG")
    source.seek(0)
    app = Flask(__name__)

    with app.test_request_context(
        "/api/image/upload",
        method="POST",
        data={"image": (source, "photo.jpg")},
        content_type="multipart/form-data",
    ):
        result = image_route.api_image_upload()
        response, status = result if isinstance(result, tuple) else (result, 200)

    assert status == 400
    assert "không khớp" in response.get_json()["error"]
    assert list(tmp_path.iterdir()) == []


def test_image_upload_endpoint_rejects_oversized_request():
    app = Flask(__name__)
    length = image_route.MAX_IMAGE_UPLOAD_BYTES + 1024 * 1024 + 1

    with app.test_request_context(
        "/api/image/upload",
        method="POST",
        environ_overrides={"CONTENT_LENGTH": str(length)},
    ):
        response, status = image_route.api_image_upload()

    assert status == 413
    assert "50 MB" in response.get_json()["error"]


def test_image_upload_endpoint_stops_oversized_stream(tmp_path, monkeypatch):
    monkeypatch.setattr(image_route, "UPLOAD_DIR", tmp_path)
    monkeypatch.setattr(image_route, "MAX_IMAGE_UPLOAD_BYTES", 5)
    source = io.BytesIO()
    Image.new("RGB", (12, 9), (20, 40, 60)).save(source, "PNG")
    source.seek(0)
    app = Flask(__name__)

    with app.test_request_context(
        "/api/image/upload",
        method="POST",
        data={"image": (source, "photo.png")},
        content_type="multipart/form-data",
    ):
        response, status = image_route.api_image_upload()

    assert status == 413
    assert list(tmp_path.iterdir()) == []


def test_image_upload_access_is_limited_to_owner(tmp_path, monkeypatch):
    upload_id = "11111111-1111-4111-8111-111111111111"
    filename = f"image_{upload_id}.png"
    image_path = tmp_path / filename
    image_path.write_bytes(b"test image")
    record = {"path": image_path, "owner": "owner@example.com"}
    monkeypatch.setattr(image_route, "IMAGE_UPLOADS", {upload_id: record})
    monkeypatch.setattr(
        image_route.auth,
        "check_job_owner",
        lambda item: None if item["owner"] == "owner@example.com" else ("forbidden", 403),
    )

    assert image_route.authorize_image_upload(filename) is None
    app = Flask(__name__)
    with app.app_context():
        missing = image_route.authorize_image_upload(
            "image_22222222-2222-4222-8222-222222222222.png"
        )
    assert missing[1] == 404
    assert missing[0].get_json()["error"] == "Ảnh không tồn tại hoặc đã hết hạn."
    record["owner"] = "another@example.com"
    assert image_route.authorize_image_upload(filename) == ("forbidden", 403)


def test_ai_result_upload_access_is_limited_to_job_owner(monkeypatch):
    job_id = "33333333-3333-4333-8333-333333333333"
    filename = f"image_ai_{job_id}.png"
    job = {
        "owner": "another@example.com",
        "result": {"enhanced_path": f"/uploads/{filename}"},
    }
    monkeypatch.setattr(image_route, "jobs", {job_id: job})
    monkeypatch.setattr(
        image_route.auth,
        "check_job_owner",
        lambda item: None if item["owner"] == "owner@example.com" else ("forbidden", 403),
    )

    assert image_route.authorize_image_upload(filename) == ("forbidden", 403)
    assert image_route.authorize_image_upload("voice_result.wav") is None


@pytest.mark.parametrize(
    ("payload", "expected_status"),
    [
        ({"job_id": "test", "scale": "8x"}, 400),
        ({"job_id": "test", "scale": "2x", "model": "unknown"}, 400),
        ({"scale": "2x"}, 400),
        ({"job_id": "missing", "scale": "2x", "model": "photo"}, 404),
    ],
)
def test_image_process_endpoint_validates_request(
    payload, expected_status, monkeypatch
):
    monkeypatch.setattr(image_route, "_esrgan_exe", lambda: (object(), None))
    app = Flask(__name__)
    with app.test_request_context(
        "/api/image/process",
        method="POST",
        json=payload,
    ):
        result = image_route.api_image_process()

    response, status = result if isinstance(result, tuple) else (result, 200)
    assert status == expected_status


def test_image_ai_model_status_lists_each_engine(monkeypatch):
    monkeypatch.setattr(
        image_route, "_onnx_runtime_available", lambda: (True, "test-runtime")
    )
    model_keys = {key for key, _ in image_route.IMAGE_AI_TOOLS.values()}
    monkeypatch.setattr(
        image_route.ai_model_store,
        "status",
        lambda key: {
            "available": key == "enhance",
            "status": "done" if key == "enhance" else "idle",
            "progress": 100 if key == "enhance" else 0,
            "error": None,
            "size": 1024,
            "label": key,
            "license": "MIT",
        },
    )
    app = Flask(__name__)

    with app.test_request_context("/api/image/ai/models"):
        payload = image_route.api_image_ai_models().get_json()

    assert payload["runtime_available"] is True
    assert payload["runtime_version"] == "test-runtime"
    assert payload["provider"] == "CPUExecutionProvider"
    assert set(payload["models"]) == model_keys
    assert payload["models"]["enhance"]["available"] is True


def test_image_ai_model_download_rejects_invalid_key_and_missing_runtime(monkeypatch):
    app = Flask(__name__)
    with app.test_request_context("/api/image/ai/models/not-a-model", method="POST"):
        response, status = image_route.api_image_ai_model_download("not-a-model")
    assert status == 404
    assert "không hợp lệ" in response.get_json()["error"]

    monkeypatch.setattr(
        image_route, "_onnx_runtime_available", lambda: (False, None)
    )
    with app.test_request_context("/api/image/ai/models/bg", method="POST"):
        response, status = image_route.api_image_ai_model_download("bg")
    assert status == 503
    assert "onnxruntime" in response.get_json()["error"]


def test_image_ai_tool_requires_downloaded_model(monkeypatch):
    monkeypatch.setattr(
        image_route, "_onnx_runtime_available", lambda: (True, "test-runtime")
    )
    monkeypatch.setattr(
        image_route, "_uploaded_image", lambda _upload_id: {"path": Path("image.png")}
    )
    monkeypatch.setattr(image_route.ai_model_store, "available", lambda _key: False)
    app = Flask(__name__)

    with app.test_request_context(
        "/api/image/ai/enhance",
        method="POST",
        data={"job_id": "00000000-0000-0000-0000-000000000000"},
    ):
        response, status = image_route.api_image_ai_start("enhance")

    assert status == 409
    assert response.get_json()["model"] == "enhance"


def test_image_ai_enhance_enforces_memory_limit(monkeypatch):
    monkeypatch.setattr(
        image_route, "_onnx_runtime_available", lambda: (True, "test-runtime")
    )
    monkeypatch.setattr(
        image_route,
        "_uploaded_image",
        lambda _upload_id: {
            "path": Path("image.png"),
            "width": 3000,
            "height": 3000,
        },
    )
    monkeypatch.setattr(image_route.ai_model_store, "available", lambda _key: True)
    app = Flask(__name__)

    with app.test_request_context(
        "/api/image/ai/enhance",
        method="POST",
        data={"job_id": "00000000-0000-0000-0000-000000000000"},
    ):
        response, status = image_route.api_image_ai_start("enhance")

    assert status == 413
    assert response.get_json()["max_pixels"] == 8_000_000


def test_image_ai_queue_rejects_when_capacity_is_full(monkeypatch):
    monkeypatch.setattr(
        image_route, "_onnx_runtime_available", lambda: (True, "test-runtime")
    )
    monkeypatch.setattr(
        image_route, "_uploaded_image", lambda _upload_id: {"path": Path("image.png")}
    )
    monkeypatch.setattr(image_route.ai_model_store, "available", lambda _key: True)
    monkeypatch.setattr(
        image_route,
        "jobs",
        {
            str(index): {"tool": "background", "status": "queued"}
            for index in range(image_route.MAX_PENDING_IMAGE_AI_JOBS)
        },
    )
    app = Flask(__name__)

    with app.test_request_context(
        "/api/image/ai/background",
        method="POST",
        data={
            "job_id": "00000000-0000-0000-0000-000000000000",
            "background": "transparent",
        },
    ):
        response, status = image_route.api_image_ai_start("background")

    assert status == 429
    assert "hàng đợi" in response.get_json()["error"].lower()
