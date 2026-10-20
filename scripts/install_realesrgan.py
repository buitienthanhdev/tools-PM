"""Tải Real-ESRGAN ncnn-vulkan (Windows) vào modules/image_enhancer/bin. Chạy: python scripts/install_realesrgan.py"""

import io
import os
import urllib.request
import zipfile

URL = "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesrgan-ncnn-vulkan-20220424-windows.zip"
DEST = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "modules",
    "image_enhancer",
    "bin",
)
KEEP = ("realesrgan-ncnn-vulkan.exe", "vcomp140.dll", "vcomp140d.dll", "models/")

os.makedirs(DEST, exist_ok=True)
print("Đang tải", URL)
data = urllib.request.urlopen(URL, timeout=300).read()
with zipfile.ZipFile(io.BytesIO(data)) as z:
    for name in z.namelist():
        if name.startswith(KEEP) and not name.endswith("/"):
            z.extract(name, DEST)
print("Xong:", DEST)
