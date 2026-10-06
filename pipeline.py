"""Ảnh → bong bóng → transcript → tín hiệu. Dùng chung cho app.py và evaluate.py."""

import json
from pathlib import Path

from dotenv import load_dotenv
from PIL import Image

from bubbles import draw_overlay
from extract import extract
from metrics import field_score, transcript_score
from vlm import transcribe

ROOT = Path(__file__).parent
SAMPLES = ROOT / "samples"
load_dotenv(ROOT / ".env")


def sample_meta(sample_id: str | None) -> dict | None:
    if not sample_id:
        return None
    p = SAMPLES / f"{sample_id}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def to_text(lines: list[dict]) -> str:
    """Định dạng RAW của AutoLead: mỗi tin một dòng "TVV: …" / "KH: …"."""
    return "\n".join(f"{ln['speaker']}: {ln['text']}" for ln in lines)


def from_text(text: str) -> list[dict]:
    out = []
    for raw in text.splitlines():
        if ":" in raw:
            who, _, body = raw.partition(":")
            who = who.strip().upper()
            if who in ("TVV", "KH") and body.strip():
                out.append({"speaker": who, "text": body.strip()})
    return out


def read_image(img: Image.Image, backend: str, mode: str, tiles: int = 1, platform: str | None = None) -> dict:
    lines, bubbles, platform, seconds, raw = transcribe(img, backend, mode, platform, tiles)
    return {
        "platform": platform,
        "lines": [{"speaker": ln.speaker, "text": ln.text, "kind": ln.kind} for ln in lines],
        "overlay": draw_overlay(img, bubbles) if bubbles else img,
        "bubbles": len(bubbles),
        "seconds": round(seconds, 1),
        "raw": raw,
    }


def analyse(lines: list[dict], method: str, meta: dict | None = None) -> dict:
    res = extract(lines, method)
    out = {"result": res}
    if meta:
        out["transcript"] = transcript_score(lines, meta["transcript"])
        out["fields"] = field_score(res, meta["expect"])
    return out
