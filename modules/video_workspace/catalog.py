"""
Danh mục model ĐÃ DUYỆT — chỉ các model này được tải và dùng. Nguồn duy nhất: bản phát hành chính thức mà ứng dụng
REAL-Video-Enhancer tự tải (github.com/TNTwise/real-video-enhancer-models, release "models"), kiểm tra SHA-256.
Tên file, hệ số và kiến trúc lấy từ src/ModelHandler.py của upstream (pytorch*Models). Mỗi model đã chạy thử trên
video thật bằng backend PyTorch CUDA (xem docs/video-workspace.md). Người dùng không thể đưa model khác vào.
"""

SOURCE = "https://github.com/TNTwise/real-video-enhancer-models/releases/download/models/"

MODELS = {
    # ── Tăng độ phân giải ───────────────────────────────────────────────────────
    "openproteus-2x": {
        "kind": "upscale", "file": "2x_OpenProteus_Compact_i2_70K.pth", "scale": 2, "arch": "Compact",
        "label": "OpenProteus 2x", "best_for": "Video quay thật, nguồn HD; nhanh",
        "sha256": "a943566242a830ace576b768921a63ddde2baf826b90712e869d937603008708",
        "license": "CC BY-NC 4.0 (Sirosky/Upscale-Hub)", "noncommercial": True,
    },
    "realesr-general-4x": {
        "kind": "upscale", "file": "realesr-general-x4v3.pth", "scale": 4, "arch": "Compact",
        "label": "Real-ESRGAN General v3 4x", "best_for": "Video quay thật, nguồn trung bình/thấp; nhanh",
        "sha256": "8dc7edb9ac80ccdc30c3a5dca6616509367f05fbc184ad95b731f05bece96292",
        "license": "BSD-3-Clause (xinntao/Real-ESRGAN)", "noncommercial": False,
    },
    "nomos8k-span-4x": {
        "kind": "upscale", "file": "4xNomos8k_span_otf_medium_no_update_params.pth", "scale": 4, "arch": "SPAN",
        "label": "Nomos8k SPAN 4x (medium)", "best_for": "Ảnh quay thật, nguồn chất lượng trung bình",
        "sha256": "685244ccf1f611a54929ec78ec99a54fdff8324d27003c4e27bd831b457ec13a",
        "license": "CC BY 4.0 theo trang của tác giả Helaman (chưa đối chiếu file giấy phép)", "noncommercial": False,
    },
    "janai-v3-2x": {
        "kind": "upscale", "file": "2x_AnimeJaNai_HD_V3_Sharp1_Compact_430k.pth", "scale": 2, "arch": "Compact",
        "label": "AnimeJaNai V3 Sharp 2x", "best_for": "Hoạt hình / anime; nhanh",
        "sha256": "903378423c9d4169f4c6ebcd7cf1fde927bb025636351abafae8bb98aef7c8ae",
        "license": "CC BY-NC-SA 4.0 (the-database/mpv-AnimeJaNai)", "noncommercial": True,
    },
    # ── Nội suy khung hình ──────────────────────────────────────────────────────
    "rife-4.26": {
        "kind": "interpolate", "file": "rife4.26.pkl", "arch": "rife425",
        "label": "RIFE 4.26", "best_for": "Đa dụng — khuyên dùng",
        "sha256": "45c7f74156704769dc9f85cfcaf8552e1e926f9399dcfa3a553dee88fac6f53f",
        "license": "MIT (hzwer/Practical-RIFE)", "noncommercial": False,
    },
    "rife-4.6": {
        "kind": "interpolate", "file": "rife4.6.pkl", "arch": "rife46",
        "label": "RIFE 4.6", "best_for": "Nhanh nhất, chất lượng thấp hơn 4.26",
        "sha256": "008646e761f0e67cb77f0c6c44cfe3c3e5a05d9d9465311b9681ca650ce030db",
        "license": "MIT (hzwer/Practical-RIFE)", "noncommercial": False,
    },
    # ── Phục hồi 1x (chạy trước nội suy và tăng độ phân giải) ──────────────────
    "deh264-span": {
        "kind": "restore", "group": "decompress", "file": "1x_DeH264_SPAN.safetensors", "arch": "SPAN",
        "label": "Khử vỡ hình do nén H.264 (DeH264 SPAN)", "best_for": "Video tải từ mạng, bị khối/vỡ do nén",
        "sha256": "fed5bd65b25215517ecbfaaa9fd57a318913573c626b8e6da03f4be79846a7c7",
        "license": "CC BY 4.0 (Phhofm/models)", "noncommercial": False,
    },
    "scunet-denoise": {
        "kind": "restore", "group": "denoise", "file": "scunet_color_real_psnr.pth", "arch": "scunet",
        "label": "Khử nhiễu (SCUNet)", "best_for": "Nhiễu hạt, quay thiếu sáng; giữ chi tiết tốt hơn DRUNet, chậm hơn",
        "sha256": "fa78899ba2caec9d235a900e91d96c689da71c42029230c2028b00f09f809c2e",
        "license": "Apache-2.0 (cszn/SCUNet)", "noncommercial": False,
    },
    "drunet-denoise": {
        "kind": "restore", "group": "denoise", "file": "drunet_color.pth", "arch": "drunet",
        "label": "Khử nhiễu mạnh (DRUNet)", "best_for": "Nhiễu nặng; làm mịn rõ, có thể mất chi tiết nhỏ",
        "sha256": "479abe3c5327dfd10ff54a80ec7d4098ca80752a5c9492cdff31cee430bec4b4",
        "license": "MIT (cszn/DPIR)", "noncommercial": False,
    },
    "nafnet-deblur": {
        "kind": "restore", "group": "deblur", "file": "nafnet_gopro1x.pth", "arch": "nafnet",
        "label": "Khử nhoè chuyển động (NAFNet GoPro)",
        "best_for": "Chỉ dùng khi video bị nhoè do rung/chuyển động — trên video vốn nét có thể sinh hạt",
        "sha256": "19394e6155d12ef6371d1d57496f87f0ec88f92bdffa27c0792690722d5d1a5c",
        "license": "MIT (megvii-research/NAFNet)", "noncommercial": False,
    },
}

# Hệ số nội suy: chỉ số nguyên. RVE làm tròn lên số khung hình nhưng giữ fps = fps × hệ số, nên hệ số lẻ (2.5)
# sẽ làm video dài ra (slow motion ngoài ý muốn) — không cho chọn.
INTERPOLATE_FACTORS = (2, 3, 4)
# fps đích không phải bội số nguyên (24 → 60): nội suy với hệ số nguyên nhỏ nhất vượt fps đích rồi ffmpeg đổi về đúng fps đích
TARGET_FPS = (30, 50, 60, 120)
# Phụ đề dạng chữ chuyển được sang mov_text (MP4); phụ đề ảnh (PGS/DVD) thì không
TEXT_SUBS = {"subrip", "srt", "ass", "ssa", "mov_text", "webvtt", "text"}
# "pyscenedetect" (mặc định của RVE) lỗi khi có model phục hồi 1x trước nội suy (cv2.resize nhận khung hình float16)
# ở commit đang dùng → khi kết hợp, tự chuyển sang "mean". "none" = tắt.
SCENE_DETECT = {"pyscenedetect": "PySceneDetect (khuyên dùng)", "mean": "So sánh độ sáng trung bình", "none": "Tắt"}

PRESETS = [
    {"id": "sharp2x", "label": "Nét hơn ×2", "desc": "Tăng gấp đôi độ phân giải, giữ fps",
     "upscale": "openproteus-2x", "fallback_upscale": "realesr-general-4x"},
    {"id": "4k", "label": "Lên 4 lần", "desc": "Tăng 4 lần độ phân giải (ví dụ 540p → 4K)", "upscale": "realesr-general-4x"},
    {"id": "smooth", "label": "Mượt ×2 fps", "desc": "Nhân đôi số khung hình (24→48, 30→60)", "interpolate": "rife-4.26", "factor": 2},
    {"id": "restore", "label": "Phục hồi video nén", "desc": "Khử vỡ hình do nén rồi tăng ×2",
     "restore": ["deh264-span"], "upscale": "openproteus-2x", "fallback_upscale": "realesr-general-4x"},
    {"id": "denoise", "label": "Khử nhiễu", "desc": "Giảm nhiễu hạt, giữ độ phân giải", "restore": ["scunet-denoise"]},
    {"id": "anime", "label": "Hoạt hình", "desc": "Tăng ×2 cho anime/hoạt hình", "upscale": "janai-v3-2x"},
    {"id": "full", "label": "Toàn diện", "desc": "Khử nén + tăng ×2 + mượt ×2 fps",
     "restore": ["deh264-span"], "upscale": "openproteus-2x", "fallback_upscale": "realesr-general-4x",
     "interpolate": "rife-4.26", "factor": 2},
]


def allowed(cfg):
    """Model được phép theo cấu hình (tắt model phi thương mại nếu cần)."""
    return {k: m for k, m in MODELS.items() if cfg["allow_noncommercial_models"] or not m["noncommercial"]}
