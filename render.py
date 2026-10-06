"""Vẽ ảnh chụp màn hình giả lập Zalo / Messenger từ một kịch bản (Pillow, không cần mạng).

Trả về ảnh + danh sách bong bóng chuẩn (người nói, loại, chữ, toạ độ) để chấm bước tách bong bóng.
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONT_DIR = Path("C:/Windows/Fonts")
W = 720
STATUS_H, HEADER_H, INPUT_H = 36, 68, 66
MIN_H = 1280

THEMES = {
    "zalo": {
        "status_bg": (0, 104, 255), "status_fg": (255, 255, 255),
        "header_bg": (0, 104, 255), "header_fg": (255, 255, 255), "header_sub": (214, 232, 255),
        "chat_bg": (226, 233, 241),
        "left_bg": (255, 255, 255), "left_fg": (8, 28, 54),
        "right_bg": (219, 235, 255), "right_fg": (8, 28, 54),
        "time_fg": (128, 140, 156),
        "radius": 14, "gap_in": 6, "gap_out": 18,
        "input_bg": (255, 255, 255), "placeholder": "Tin nhắn", "accent": (0, 104, 255),
    },
    "messenger": {
        "status_bg": (255, 255, 255), "status_fg": (5, 5, 5),
        "header_bg": (255, 255, 255), "header_fg": (5, 5, 5), "header_sub": (101, 103, 107),
        "chat_bg": (255, 255, 255),
        "left_bg": (233, 233, 235), "left_fg": (5, 5, 5),
        "right_bg": (0, 132, 255), "right_fg": (255, 255, 255),
        "time_fg": (138, 141, 145),
        "radius": 20, "gap_in": 4, "gap_out": 16,
        "input_bg": (255, 255, 255), "placeholder": "Nhắn tin", "accent": (0, 132, 255),
    },
}


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    name = "segoeuib.ttf" if bold else "segoeui.ttf"
    try:
        return ImageFont.truetype(str(FONT_DIR / name), size)
    except OSError:
        return ImageFont.truetype("arialbd.ttf" if bold else "arial.ttf", size)


F_MSG, F_TIME, F_NAME, F_SUB, F_SEP = _font(26), _font(16), _font(25, True), _font(17), _font(17)


def _wrap(text: str, font, max_w: int) -> list[str]:
    lines, cur = [], ""
    for word in text.split():
        trial = f"{cur} {word}".strip()
        if font.getlength(trial) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines or [""]


def _initials(name: str) -> str:
    parts = name.split()
    return (parts[0][0] + (parts[-1][0] if len(parts) > 1 else "")).upper()


def _avatar(d: ImageDraw.ImageDraw, x: int, y: int, size: int, name: str) -> None:
    d.ellipse([x, y, x + size, y + size], fill=(245, 166, 35))
    f = _font(int(size * 0.4), True)
    t = _initials(name)
    d.text((x + size / 2, y + size / 2), t, font=f, fill=(255, 255, 255), anchor="mm")


def _status_bar(d, th) -> None:
    d.rectangle([0, 0, W, STATUS_H], fill=th["status_bg"])
    d.text((24, STATUS_H / 2), "9:41", font=_font(18, True), fill=th["status_fg"], anchor="lm")
    x = W - 30
    d.rounded_rectangle([x - 26, 12, x, 24], radius=3, outline=th["status_fg"], width=2)
    d.rectangle([x - 23, 15, x - 8, 21], fill=th["status_fg"])
    for i in range(4):
        h = 4 + i * 3
        d.rectangle([x - 70 + i * 7, 26 - h, x - 66 + i * 7, 26], fill=th["status_fg"])


def _header(d, th, platform: str, name: str, status: str) -> None:
    y0, y1 = STATUS_H, STATUS_H + HEADER_H
    d.rectangle([0, y0, W, y1], fill=th["header_bg"])
    cy = (y0 + y1) / 2
    fg = th["header_fg"] if platform == "zalo" else th["accent"]
    d.line([(20, cy), (32, cy - 12)], fill=fg, width=3)
    d.line([(20, cy), (32, cy + 12)], fill=fg, width=3)
    if platform == "zalo":
        d.line([(20, cy), (40, cy)], fill=fg, width=3)
        tx = 60
    else:
        _avatar(d, 52, int(cy - 21), 42, name)
        d.ellipse([84, int(cy + 8), 96, int(cy + 20)], fill=(49, 162, 76), outline=(255, 255, 255), width=2)
        tx = 106
    d.text((tx, cy - 3), name, font=F_NAME, fill=th["header_fg"], anchor="ls")
    d.text((tx, cy + 3), status, font=F_SUB, fill=th["header_sub"], anchor="lt")
    # phone, video, menu icons
    ic = th["header_fg"] if platform == "zalo" else th["accent"]
    x = W - 150
    d.rounded_rectangle([x, cy - 11, x + 22, cy + 11], radius=6, outline=ic, width=3)
    d.rounded_rectangle([x + 50, cy - 9, x + 74, cy + 9], radius=3, outline=ic, width=3)
    d.polygon([(x + 74, cy - 2), (x + 84, cy - 8), (x + 84, cy + 8), (x + 74, cy + 2)], fill=ic)
    if platform == "zalo":
        for i in range(3):
            d.line([(x + 106, cy - 9 + i * 9), (x + 128, cy - 9 + i * 9)], fill=ic, width=3)
    else:
        d.ellipse([x + 104, cy - 12, x + 128, cy + 12], outline=ic, width=3)
        d.text((x + 116, cy), "i", font=_font(18, True), fill=ic, anchor="mm")
    if platform == "messenger":
        d.line([(0, y1), (W, y1)], fill=(228, 230, 235), width=1)


def _input_bar(d, th, platform: str, H: int) -> None:
    y0 = H - INPUT_H
    d.rectangle([0, y0, W, H], fill=th["input_bg"])
    cy = y0 + INPUT_H / 2
    grey = (138, 148, 163)
    if platform == "zalo":
        d.line([(0, y0), (W, y0)], fill=(214, 220, 228), width=1)
        d.ellipse([18, cy - 14, 46, cy + 14], outline=grey, width=3)
        d.text((62, cy), th["placeholder"], font=_font(24), fill=grey, anchor="lm")
        for i, x in enumerate((W - 130, W - 82)):
            d.rounded_rectangle([x, cy - 12, x + 26, cy + 12], radius=4 if i else 12, outline=grey, width=3)
        d.ellipse([W - 40, cy - 3, W - 34, cy + 3], fill=grey)
    else:
        acc = th["accent"]
        for x in (16, 58, 100):
            d.ellipse([x, cy - 13, x + 26, cy + 13], outline=acc, width=3)
        d.rounded_rectangle([140, cy - 21, W - 64, cy + 21], radius=21, fill=(240, 242, 245))
        d.text((160, cy), th["placeholder"], font=_font(23), fill=(101, 103, 107), anchor="lm")
        d.polygon([(W - 46, cy + 12), (W - 46, cy - 6), (W - 36, cy - 16), (W - 22, cy - 2), (W - 22, cy + 12)], fill=acc)


def _bubble_size(kind: str, text: str, platform: str, show_time: bool) -> tuple[int, int, list[str]]:
    if kind == "sticker":
        return 130, 130, []
    if kind == "voice":
        return 270, 60 + (22 if show_time and platform == "zalo" else 0), []
    max_w = int(W * 0.66) - 32
    lines = _wrap(text, F_MSG, max_w)
    tw = max(F_MSG.getlength(line) for line in lines)
    h = len(lines) * 34 + 22
    if show_time and platform == "zalo":
        h += 22
        tw = max(tw, F_TIME.getlength("00:00"))
    return int(tw) + 32, h, lines


def _sticker(d, x: int, y: int) -> None:
    d.ellipse([x + 5, y + 5, x + 125, y + 125], fill=(255, 205, 64), outline=(230, 160, 20), width=4)
    d.ellipse([x + 38, y + 42, x + 52, y + 62], fill=(70, 45, 20))
    d.ellipse([x + 78, y + 42, x + 92, y + 62], fill=(70, 45, 20))
    d.arc([x + 32, y + 50, x + 98, y + 104], start=20, end=160, fill=(70, 45, 20), width=6)


def render(scenario: dict) -> tuple[Image.Image, list[dict]]:
    platform = scenario["platform"]
    th = THEMES[platform]
    msgs = scenario["messages"]

    # Layout pass: sizes and vertical positions.
    items, y = [], 22 + 40  # day separator first
    for i, (speaker, kind, text, time) in enumerate(msgs):
        nxt = msgs[i + 1] if i + 1 < len(msgs) else None
        last_in_group = nxt is None or nxt[0] != speaker
        first_in_group = i == 0 or msgs[i - 1][0] != speaker
        bw, bh, lines = _bubble_size(kind, text, platform, last_in_group)
        if not first_in_group:
            y -= th["gap_out"] - th["gap_in"]
        items.append(dict(speaker=speaker, kind=kind, text=text, time=time, lines=lines, w=bw, h=bh, y=y,
                          first=first_in_group, last=last_in_group))
        y += bh + th["gap_out"]
    content_h = y + 10
    chat_top = STATUS_H + HEADER_H
    H = max(MIN_H, chat_top + content_h + INPUT_H)
    offset = chat_top + (H - INPUT_H - chat_top - content_h)  # messages sit at the bottom like real apps

    img = Image.new("RGB", (W, H), th["chat_bg"])
    d = ImageDraw.Draw(img)

    sep_y = offset + 22
    if platform == "zalo":
        tw = F_SEP.getlength(scenario["day_label"])
        d.rounded_rectangle([W / 2 - tw / 2 - 14, sep_y - 2, W / 2 + tw / 2 + 14, sep_y + 28], radius=14,
                            fill=(166, 176, 189))
        d.text((W / 2, sep_y + 13), scenario["day_label"], font=F_SEP, fill=(255, 255, 255), anchor="mm")
    else:
        d.text((W / 2, sep_y + 13), scenario["day_label"], font=F_SEP, fill=th["time_fg"], anchor="mm")

    truth = []
    for it in items:
        top = offset + it["y"]
        right = it["speaker"] == "TVV"
        if right:
            x = W - 14 - it["w"]
        else:
            x = 64 if platform == "zalo" else 52
        if not right:
            av = 40 if platform == "zalo" else 30
            if platform == "zalo" and it["first"]:
                _avatar(d, 14, top, av, scenario["contact_name"])
            if platform == "messenger" and it["last"]:
                _avatar(d, 14, top + it["h"] - av, av, scenario["contact_name"])
        bg, fg = (th["right_bg"], th["right_fg"]) if right else (th["left_bg"], th["left_fg"])
        box = [x, top, x + it["w"], top + it["h"]]
        if it["kind"] == "sticker":
            _sticker(d, x, top)
        else:
            d.rounded_rectangle(box, radius=th["radius"], fill=bg)
            if it["kind"] == "voice":
                cy = top + 30
                d.polygon([(x + 22, cy - 12), (x + 22, cy + 12), (x + 42, cy)], fill=th["accent"] if not right else fg)
                for k in range(16):
                    hh = [6, 14, 20, 10, 16, 24, 12, 8, 18, 22, 10, 14, 6, 12, 18, 8][k]
                    d.rectangle([x + 60 + k * 9, cy - hh / 2, x + 64 + k * 9, cy + hh / 2], fill=fg)
                d.text((x + it["w"] - 18, cy), it["text"], font=_font(20), fill=fg, anchor="rm")
            else:
                ty = top + 11
                for line in it["lines"]:
                    d.text((x + 16, ty), line, font=F_MSG, fill=fg)
                    ty += 34
            if it["last"] and platform == "zalo":
                d.text((x + 16, top + it["h"] - 26), it["time"], font=F_TIME, fill=th["time_fg"])
        truth.append({"speaker": it["speaker"], "kind": it["kind"], "text": it["text"], "box": box})

    _status_bar(d, th)
    _header(d, th, platform, scenario["contact_name"], scenario["status"])
    _input_bar(d, th, platform, H)
    return img, truth


def render_all(out_dir: Path) -> list[Path]:
    import json

    from scenarios import SCENARIOS, transcript_lines

    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for s in SCENARIOS:
        img, truth = render(s)
        p = out_dir / f"{s['id']}.png"
        img.save(p)
        meta = {
            "id": s["id"], "platform": s["platform"], "bubbles": truth,
            "transcript": [{"speaker": sp, "text": t} for sp, t in transcript_lines(s)],
            "expect": s["expect"],
        }
        (out_dir / f"{s['id']}.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
        paths.append(p)
    return paths


if __name__ == "__main__":
    for p in render_all(Path(__file__).parent / "samples"):
        print(p)
