"""Tách bong bóng chat bằng code (OpenCV), gán người nói theo màu + phía của bong bóng.

Vì sao không để VLM tự đoán người nói: model 1B hay nhầm trái/phải, mà nhầm một bong bóng là đảo
nghĩa ("Em vay được không?" của TVV thành ý của khách). Code làm phần chắc chắn được; VLM chỉ đọc chữ.

Giới hạn MVP: chỉ giao diện sáng mặc định của Zalo và Messenger; giao diện tối, ảnh nền chat tuỳ
chỉnh, chat nhóm cần thêm luật.
"""

from dataclasses import dataclass, field

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageOps

# Màu bong bóng (RGB) và dung sai cho từng nền tảng, giao diện sáng mặc định.
PALETTE = {
    "zalo": {"KH": ((255, 255, 255), 4), "TVV": ((219, 235, 255), 8)},
    "messenger": {"KH": ((233, 233, 235), 6), "TVV": ((0, 132, 255), 40)},
}


@dataclass
class Bubble:
    speaker: str  # "TVV" (bên phải, người chụp) | "KH" (bên trái)
    box: tuple[int, int, int, int]  # x0, y0, x1, y1
    crop: Image.Image = field(repr=False)
    kind: str = "text"  # text | voice — tin thoại nhận bằng code, không để VLM đoán


def is_voice(crop: Image.Image) -> bool:
    """Tin thoại: bong bóng thấp (một dòng) có nút ▶ màu xanh đậm ở mép trái. Chữ thường không có màu này."""
    a = np.asarray(crop.convert("RGB")).astype(np.int16)
    h, w = a.shape[:2]
    if h > 0.12 * w + 60:
        return False
    bg = np.median(a.reshape(-1, 3), axis=0)
    if bg.min() < 180:  # chỉ xét bong bóng nền sáng (bong bóng xanh của Messenger thì cả nền đã xanh)
        return False
    left = a[:, : max(1, w // 5)]
    blue = (left[:, :, 2] > 200) & (left[:, :, 0] < 60) & (left[:, :, 1] < 160)
    return blue.sum() > 0.01 * left.shape[0] * left.shape[1]


def detect_platform(img: Image.Image) -> str:
    a = np.asarray(img.convert("RGB"))
    top = a[: max(20, a.shape[0] // 20)].reshape(-1, 3).mean(axis=0)
    r, g, b = top
    return "zalo" if b > 180 and r < 90 else "messenger"


def _chat_area(a: np.ndarray, platform: str) -> tuple[int, int]:
    """Hàng đầu và cuối của vùng tin nhắn (bỏ thanh trạng thái, header, ô nhập)."""
    h, w = a.shape[:2]
    s = w / 720
    top = int(104 * s)
    if platform == "zalo":
        blue = (a[:, :, 2] > 200) & (a[:, :, 0] < 60)
        rows = blue.mean(axis=1) > 0.6
        y = 0
        while y < h // 3 and rows[y]:
            y += 1
        if y > 10:
            top = y
    bottom = h - int(66 * s)
    return top + 2, bottom - 2


def _mask(a: np.ndarray, color: tuple[int, int, int], tol: int) -> np.ndarray:
    diff = np.abs(a.astype(np.int16) - np.array(color, dtype=np.int16)).max(axis=2)
    return (diff <= tol).astype(np.uint8) * 255


def normalize_crop(crop: Image.Image) -> Image.Image:
    """Đưa về chữ tối trên nền sáng (bong bóng xanh chữ trắng của Messenger) cho dễ đọc."""
    gray = ImageOps.grayscale(crop)
    if np.asarray(gray).mean() < 140:
        gray = ImageOps.invert(gray)
    return ImageOps.autocontrast(gray).convert("RGB")


def split_bubbles(img: Image.Image, platform: str | None = None) -> tuple[str, list[Bubble]]:
    img = img.convert("RGB")
    platform = platform or detect_platform(img)
    a = np.asarray(img)
    h, w = a.shape[:2]
    y0, y1 = _chat_area(a, platform)
    min_w, min_h = int(0.07 * w), int(0.045 * w)

    found: list[Bubble] = []
    for speaker, (color, tol) in PALETTE[platform].items():
        m = np.zeros((h, w), np.uint8)
        m[y0:y1] = _mask(a[y0:y1], color, tol)
        m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        contours, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for c in contours:
            x, y, bw, bh = cv2.boundingRect(c)
            if bw < min_w or bh < min_h or bw > 0.9 * w:
                continue
            # Bong bóng phải lấp gần đầy khung chữ nhật của nó (loại vệt màu lẻ).
            if cv2.contourArea(c) < 0.6 * bw * bh:
                continue
            cx = x + bw / 2
            side = "TVV" if cx > w / 2 else "KH"
            if side != speaker and min(x, w - (x + bw)) > 0.1 * w:
                continue  # màu khớp nhưng sai phía và không sát mép: bỏ
            crop = img.crop((x, y, x + bw, y + bh))
            found.append(Bubble(speaker, (x, y, x + bw, y + bh), crop, "voice" if is_voice(crop) else "text"))
    found.sort(key=lambda b: b.box[1])
    return platform, found


def draw_overlay(img: Image.Image, bubbles: list[Bubble]) -> Image.Image:
    out = img.convert("RGB").copy()
    d = ImageDraw.Draw(out)
    for i, b in enumerate(bubbles, 1):
        color = (232, 89, 12) if b.speaker == "TVV" else (12, 166, 120)
        d.rectangle(b.box, outline=color, width=4)
        d.rectangle([b.box[0], b.box[1] - 22, b.box[0] + 70, b.box[1]], fill=color)
        d.text((b.box[0] + 5, b.box[1] - 20), f"{i} {b.speaker}", fill=(255, 255, 255))
    return out
