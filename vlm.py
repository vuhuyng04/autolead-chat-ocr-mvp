"""Đọc chữ trong ảnh: Vintern (chạy local trên CPU/GPU) hoặc một VLM qua API tương thích OpenAI.

Hai chế độ:
- "bubbles": code tách bong bóng (bubbles.py) → VLM chỉ chép chữ từng bong bóng. Người nói do code gán.
- "page": đưa nguyên ảnh, VLM tự chép và tự gán TVV/KH (để so sánh xem model nhỏ đoán phía có đúng không).
"""

import base64
import io
import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

VINTERN_MODELS = {
    "Vintern-1B-v3.5": "5CD-AI/Vintern-1B-v3_5",
    "Vintern-1B-v2": "5CD-AI/Vintern-1B-v2",
}
MOCK = "Giả lập (đáp án chuẩn, không phải OCR)"
MODELS_DIR = Path(__file__).parent / "models"


def model_source(name: str) -> str:
    """Thư mục model tải tay (models/<tên repo>) nếu có, không thì repo trên Hugging Face."""
    repo = VINTERN_MODELS[name]
    local = MODELS_DIR / repo.split("/")[1]
    return str(local) if (local / "config.json").exists() else repo


def model_ready(name: str) -> bool:
    """Đã có trọng số trên máy chưa (thư mục models/ hoặc cache Hugging Face)."""
    src = model_source(name)
    if Path(src).exists():
        return any(Path(src).glob("*.safetensors"))
    cache = Path.home() / ".cache/huggingface/hub" / ("models--" + src.replace("/", "--"))
    return any(cache.glob("snapshots/*/*.safetensors"))

PROMPT_BUBBLE = (
    "Chép lại nguyên văn chữ trong ảnh, giữ đúng dấu tiếng Việt, chữ viết tắt và con số. "
    "Chỉ trả về phần chữ, không giải thích."
)
PROMPT_PAGE = (
    "Đây là ảnh chụp màn hình đoạn chat {app} giữa tư vấn viên bán ô tô (bong bóng bên PHẢI) và khách "
    "hàng (bong bóng bên TRÁI). Chép lại lần lượt từng tin nhắn từ trên xuống, mỗi tin một dòng, dạng "
    "'TVV: <nội dung>' hoặc 'KH: <nội dung>'. Giữ nguyên văn, không ghi giờ, không giải thích."
)


@dataclass
class Line:
    speaker: str
    text: str
    kind: str = "text"  # text | voice


# ---------------------------------------------------------------- hậu xử lý chung

_PREFIX = re.compile(r"^\s*(văn bản|nội dung|chữ trong ảnh|đoạn văn)[^:]{0,30}:\s*", re.I)
_ZALO_TIME = re.compile(r"\s*\b\d{2}:\d{2}\s*$")
_VOICE = re.compile(r"^\s*\d{1,2}:\d{2}\s*$")


def clean_bubble_text(text: str) -> tuple[str, str]:
    """Bỏ lời dẫn của model, giờ gửi trong bong bóng Zalo; nhận ra tin nhắn thoại. Trả (kind, text)."""
    t = _PREFIX.sub("", text.strip()).strip().strip('"“”').strip()
    t = re.sub(r"\s*\n\s*", " ", t)
    if _VOICE.match(t) and len(t) <= 5 and not re.match(r"^\d{2}:", t):
        return "voice", f"[tin nhắn thoại {t.strip()}]"
    t = _ZALO_TIME.sub("", t).strip()
    return "text", t


def parse_page(text: str) -> list[Line]:
    lines: list[Line] = []
    for raw in text.splitlines():
        raw = raw.strip().lstrip("-•* ").strip()
        if not raw:
            continue
        m = re.match(r"^(TVV|KH|Tư vấn viên|Khách hàng|Khách)\s*[:：]\s*(.*)$", raw, re.I)
        if m:
            who = "TVV" if m.group(1).lower().startswith(("tvv", "tư")) else "KH"
            kind, t = clean_bubble_text(m.group(2))
            if t:
                lines.append(Line(who, t, kind))
        elif lines:
            lines[-1].text += " " + raw
    return lines


# ---------------------------------------------------------------- Vintern (InternVL) local

IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)


def _transform(size: int):
    import torchvision.transforms as T
    from torchvision.transforms.functional import InterpolationMode

    return T.Compose([
        T.Lambda(lambda img: img.convert("RGB")),
        T.Resize((size, size), interpolation=InterpolationMode.BICUBIC),
        T.ToTensor(),
        T.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
    ])


def _closest_ratio(aspect, ratios, w, h, size):
    best, best_diff = (1, 1), float("inf")
    for r in ratios:
        diff = abs(aspect - r[0] / r[1])
        if diff < best_diff:
            best_diff, best = diff, r
        elif diff == best_diff and w * h > 0.5 * size * size * r[0] * r[1]:
            best = r
    return best


def dynamic_preprocess(image: Image.Image, max_num: int = 6, size: int = 448, use_thumbnail: bool = True):
    """Cắt ảnh thành các ô 448px theo tỉ lệ gần nhất (giống code mẫu của InternVL / Vintern)."""
    w, h = image.size
    ratios = sorted({(i, j) for n in range(1, max_num + 1) for i in range(1, n + 1) for j in range(1, n + 1)
                     if i * j <= max_num}, key=lambda r: r[0] * r[1])
    rw, rh = _closest_ratio(w / h, ratios, w, h, size)
    resized = image.resize((size * rw, size * rh))
    tiles = [resized.crop(((i % rw) * size, (i // rw) * size, (i % rw + 1) * size, (i // rw + 1) * size))
             for i in range(rw * rh)]
    if use_thumbnail and len(tiles) > 1:
        tiles.append(image.resize((size, size)))
    return tiles


def pad_to_aspect(img: Image.Image, ratio: float, fill=(255, 255, 255)) -> Image.Image:
    """Đệm bong bóng dẹt thành khung tỉ lệ `ratio` (rộng/cao) để không bị kéo méo khi resize về 448px."""
    w, h = img.size
    if w / h > ratio:
        nh = int(w / ratio)
        canvas = Image.new("RGB", (w, nh), fill)
        canvas.paste(img, (0, (nh - h) // 2))
    else:
        nw = int(h * ratio)
        canvas = Image.new("RGB", (nw, h), fill)
        canvas.paste(img, ((nw - w) // 2, 0))
    return canvas


class VinternOCR:
    def __init__(self, name: str = "Vintern-1B-v3.5"):
        self.name = name
        self.repo = model_source(name)
        self.model = None
        self.tok = None

    def load(self):
        if self.model is not None:
            return
        import torch
        from transformers import AutoModel, AutoTokenizer

        cuda = torch.cuda.is_available()
        dtype = torch.bfloat16 if cuda else torch.float32
        self.torch = torch
        self.dtype = dtype
        self.device = "cuda" if cuda else "cpu"
        self.model = AutoModel.from_pretrained(
            self.repo, torch_dtype=dtype, low_cpu_mem_usage=True, trust_remote_code=True, use_flash_attn=False
        ).eval().to(self.device)
        self.tok = AutoTokenizer.from_pretrained(self.repo, trust_remote_code=True, use_fast=False)

    def _pixels(self, img: Image.Image, max_num: int):
        tf = _transform(448)
        tiles = dynamic_preprocess(img.convert("RGB"), max_num=max_num)
        return self.torch.stack([tf(t) for t in tiles]).to(self.dtype).to(self.device)

    def _gen(self, max_new_tokens: int) -> dict:
        return dict(max_new_tokens=max_new_tokens, do_sample=False, num_beams=1, repetition_penalty=1.05,
                    pad_token_id=self.tok.eos_token_id)

    def read_bubbles(self, crops: list[Image.Image], tiles: int = 1) -> list[str]:
        """Chép chữ từng bong bóng. tiles=1: đệm thành ảnh vuông, 1 ô 448px (nhanh nhất trên CPU)."""
        self.load()
        prepared = [pad_to_aspect(c, 1.0 if tiles == 1 else 2.0) for c in crops]
        out = []
        with self.torch.inference_mode():
            for img in prepared:
                pv = self._pixels(img, max_num=tiles)
                out.append(self.model.chat(self.tok, pv, "<image>\n" + PROMPT_BUBBLE, self._gen(96)))
        return out

    def read_page(self, img: Image.Image, app: str, tiles: int = 6) -> str:
        self.load()
        with self.torch.inference_mode():
            pv = self._pixels(img, max_num=tiles)
            return self.model.chat(self.tok, pv, "<image>\n" + PROMPT_PAGE.format(app=app), self._gen(600))


# ---------------------------------------------------------------- VLM qua API (OpenAI-compatible)


def _b64(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


class OpenAICompatVLM:
    """VLM qua endpoint OpenAI-compatible. Mỗi bong bóng một request, gửi song song."""

    workers = 4
    system: str | None = None

    def __init__(self, name: str, base_url: str | None, model: str, api_key: str):
        from openai import OpenAI

        self.name, self.model_name = name, model
        self.client = OpenAI(base_url=base_url, api_key=api_key or "none", max_retries=2, timeout=180)

    def _ask(self, prompt: str, img: Image.Image, max_tokens: int) -> str:
        r = self.client.chat.completions.create(
            model=self.model_name, temperature=0, max_tokens=max_tokens,
            messages=([{"role": "system", "content": self.system}] if self.system else []) + [
                {"role": "user", "content": [{"type": "image_url", "image_url": {"url": _b64(img)}},
                                             {"type": "text", "text": prompt}]}])
        return r.choices[0].message.content or ""

    def read_bubbles(self, crops: list[Image.Image], tiles: int = 1) -> list[str]:
        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(self.workers) as ex:
            return list(ex.map(lambda c: self._ask(PROMPT_BUBBLE, c, 160), crops))

    def read_page(self, img: Image.Image, app: str, tiles: int = 6) -> str:
        return self._ask(PROMPT_PAGE.format(app=app), img, 900)


class ApiVLM(OpenAICompatVLM):
    """VLM tuỳ chọn cấu hình bằng VLM_BASE_URL / VLM_MODEL / VLM_API_KEY (GPT-4o, vLLM…)."""

    def __init__(self):
        model = os.getenv("VLM_MODEL", "gpt-4o-mini")
        super().__init__(f"API: {model}", os.getenv("VLM_BASE_URL") or None, model, os.getenv("VLM_API_KEY", ""))

    @staticmethod
    def available() -> bool:
        return bool(os.getenv("VLM_API_KEY"))


HF_ROUTER = "https://router.huggingface.co/v1"


def hf_token() -> str | None:
    """HF_TOKEN trong .env, không thì token đã `hf auth login` trên máy."""
    if os.getenv("HF_TOKEN"):
        return os.getenv("HF_TOKEN")
    try:
        from huggingface_hub import get_token

        return get_token()
    except Exception:
        return None


class HFRouterVLM(OpenAICompatVLM):
    """Qwen-VL qua Hugging Face Inference Providers (router.huggingface.co). Ảnh rời máy → chỉ ảnh tự dựng."""

    workers = 8

    def __init__(self):
        model = os.getenv("HF_VLM_MODEL", "Qwen/Qwen3-VL-30B-A3B-Instruct")
        super().__init__(hf_label(), HF_ROUTER, model, hf_token() or "")

    @staticmethod
    def available() -> bool:
        return bool(hf_token())


def hf_label() -> str:
    return "HF · " + os.getenv("HF_VLM_MODEL", "Qwen/Qwen3-VL-30B-A3B-Instruct").split("/")[-1]


LLAMA = "Vintern-1B-v3.5 GGUF · llama.cpp"
TOOLS_DIR = Path(__file__).parent / "tools"
GGUF_DIR = MODELS_DIR / "Vintern-1B-v3_5-GGUF"


class LlamaCppVLM(OpenAICompatVLM):
    """Vintern GGUF Q8 chạy bằng llama-server (Vulkan → GPU Intel Arc, hoặc CPU). App tự bật server."""

    port = int(os.getenv("LLAMA_PORT", "8091"))
    workers = 4  # = số slot song song của server (-np)
    # System prompt Vintern được huấn luyện cùng (conversation.py, template Hermes-2); thiếu nó model trả lời lệch.
    system = ("Bạn là một mô hình trí tuệ nhân tạo đa phương thức Tiếng Việt có tên gọi là Vintern, được phát triển "
              "bởi người Việt. Bạn là một trợ lý trí tuệ nhân tạo hữu ích và không gây hại.")

    def __init__(self):
        self.proc = None
        self._ensure_server()
        super().__init__(LLAMA, f"http://127.0.0.1:{self.port}/v1", "vintern", "")

    @staticmethod
    def exe() -> Path:
        flavour = os.getenv("LLAMA_BACKEND", "vulkan")  # vulkan | cpu
        return TOOLS_DIR / f"llama-{flavour}" / "llama-server.exe"

    @staticmethod
    def available() -> bool:
        return LlamaCppVLM.exe().exists() and all(
            (GGUF_DIR / f).exists() for f in ("Vintern-1B-v3_5-Q8_0.gguf", "mmproj-Vintern-1B-v3_5-Q8_0.gguf"))

    def _healthy(self) -> bool:
        import urllib.request

        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/health", timeout=2) as r:
                return r.status == 200
        except Exception:
            return False

    def _ensure_server(self) -> None:
        if self._healthy():
            return
        import atexit
        import subprocess

        log_dir = Path(__file__).parent / "logs"
        log_dir.mkdir(exist_ok=True)
        cmd = [str(self.exe()), "-m", str(GGUF_DIR / "Vintern-1B-v3_5-Q8_0.gguf"),
               "--mmproj", str(GGUF_DIR / "mmproj-Vintern-1B-v3_5-Q8_0.gguf"),
               "--host", "127.0.0.1", "--port", str(self.port), "-ngl", "99",
               "-np", str(self.workers), "-c", str(2048 * self.workers)]
        log = open(log_dir / "llama-server.log", "w", encoding="utf-8")
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        self.proc = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, creationflags=flags)
        atexit.register(self.proc.terminate)
        t0 = time.time()
        while time.time() - t0 < 180:
            if self.proc.poll() is not None:
                raise RuntimeError("llama-server thoát sớm — xem logs/llama-server.log")
            if self._healthy():
                return
            time.sleep(0.5)
        raise RuntimeError("llama-server không lên sau 180 s — xem logs/llama-server.log")


# ---------------------------------------------------------------- điều phối

_CACHE: dict[str, object] = {}


class MockOCR:
    """Trả chữ chuẩn của ảnh mẫu (tìm theo hash ảnh) — chỉ để demo phần sau OCR khi chưa có model."""

    name = MOCK

    def __init__(self):
        import hashlib
        import json

        self._by_hash = {}
        for png in (Path(__file__).parent / "samples").glob("s*.png"):
            meta = json.loads(png.with_suffix(".json").read_text(encoding="utf-8"))
            self._by_hash[hashlib.md5(png.read_bytes()).hexdigest()] = meta
        self.current = None

    def use(self, img: Image.Image):
        import hashlib

        buf = io.BytesIO()
        img.convert("RGB").save(buf, format="PNG")
        h = hashlib.md5(buf.getvalue()).hexdigest()
        self.current = self._by_hash.get(h) or next(
            (m for m in self._by_hash.values() if _same_pixels(img, m["id"])), None)
        if not self.current:
            raise ValueError("Chế độ giả lập chỉ dùng cho ảnh mẫu trong samples/.")

    def read_bubbles(self, crops, tiles: int = 1) -> list[str]:
        texts = [b["text"] for b in self.current["bubbles"] if b["kind"] != "sticker"]
        return (texts + [""] * len(crops))[: len(crops)]

    def read_page(self, img, app: str, tiles: int = 6) -> str:
        return "\n".join(f"{t['speaker']}: {t['text']}" for t in self.current["transcript"])


def _same_pixels(img: Image.Image, sid: str) -> bool:
    """Cùng ảnh mẫu dù đã qua nén (sai khác trung bình rất nhỏ)."""
    import numpy as np

    other = Image.open(Path(__file__).parent / "samples" / f"{sid}.png").convert("RGB")
    if other.size != img.size:
        return False
    diff = np.abs(np.asarray(other, np.int16) - np.asarray(img.convert("RGB"), np.int16))
    return float(diff.mean()) < 3.0


def get_backend(name: str):
    if name not in _CACHE:
        if name == MOCK:
            _CACHE[name] = MockOCR()
        elif name == LLAMA:
            _CACHE[name] = LlamaCppVLM()
        elif name.startswith("HF"):
            _CACHE[name] = HFRouterVLM()
        elif name.startswith("API"):
            _CACHE[name] = ApiVLM()
        else:
            _CACHE[name] = VinternOCR(name)
    return _CACHE[name]


def transcribe(img: Image.Image, backend: str, mode: str, platform: str | None = None, tiles: int = 1):
    """Ảnh → (lines, bubbles, platform, seconds). bubbles rỗng ở chế độ "page"."""
    from bubbles import split_bubbles

    be = get_backend(backend)
    if isinstance(be, MockOCR):
        be.use(img)
    t0 = time.perf_counter()
    platform, found = split_bubbles(img, platform)
    app = "Zalo" if platform == "zalo" else "Messenger"
    if mode == "page":
        raw = be.read_page(img, app, tiles=max(tiles, 6))
        return parse_page(raw), [], platform, time.perf_counter() - t0, raw
    from bubbles import normalize_crop

    def for_vlm(b):  # tin thoại: chỉ đưa phần thời lượng ở mép phải, bỏ nút ▶ và sóng âm (VLM hay đọc bịa)
        c = b.crop.crop((int(b.crop.width * 0.7), 0, b.crop.width, b.crop.height)) if b.kind == "voice" else b.crop
        return normalize_crop(c)

    texts = be.read_bubbles([for_vlm(b) for b in found], tiles=tiles)
    lines = []
    for b, t in zip(found, texts):
        kind, clean = clean_bubble_text(t)
        if b.kind == "voice":  # code đã nhận ra tin thoại: chỉ lấy thời lượng từ chữ VLM đọc được
            m = re.search(r"\d{1,2}:\d{2}", t)
            kind, clean = "voice", f"[tin nhắn thoại {m.group(0)}]" if m else "[tin nhắn thoại]"
        if clean:
            lines.append(Line(b.speaker, clean, kind))
    raw = "\n".join(f"[{i}] {t}" for i, t in enumerate(texts, 1))
    return lines, found, platform, time.perf_counter() - t0, raw
