"""Dựng backend nhanh: llama.cpp (Vulkan → GPU Intel Arc / AMD / NVIDIA, hoặc CPU) + Vintern GGUF Q8.

    python download_models.py        # trước: lấy bản gốc safetensors về models/Vintern-1B-v3_5
    python setup_llama.py            # tải llama.cpp, chuyển Vintern sang GGUF Q8, sửa metadata

Tự chuyển đổi từ bản gốc thay vì tải GGUF có sẵn: trên mạng hay bị reset, tải 1 GB GGUF chậm hơn nhiều so với
chuyển đổi tại chỗ (~30 s). Bước nào đã xong thì bỏ qua.
"""

import io
import json
import shutil
import subprocess
import sys
import tarfile
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).parent
BUILD = "b11433"  # bản llama.cpp đã thử với MVP này
TOOLS = ROOT / "tools"
SRC = TOOLS / "llama-src"
HF_DIR = ROOT / "models" / "Vintern-1B-v3_5"
OUT = ROOT / "models" / "Vintern-1B-v3_5-GGUF"
PY = sys.executable


def fetch(url: str) -> bytes:
    for attempt in range(5):
        try:
            with urllib.request.urlopen(url, timeout=120) as r:
                return r.read()
        except Exception as e:  # mạng chập chờn: thử lại
            print(f"  lỗi tải ({e}), thử lại {attempt + 1}/5")
    raise SystemExit(f"Không tải được {url}")


def llama_binaries() -> None:
    for flavour in ("vulkan", "cpu"):
        target = TOOLS / f"llama-{flavour}"
        if (target / "llama-server.exe").exists():
            continue
        name = f"llama-{BUILD}-bin-win-{flavour}-x64.zip"
        print(f"Tải {name}")
        zipfile.ZipFile(io.BytesIO(fetch(f"https://github.com/ggml-org/llama.cpp/releases/download/{BUILD}/{name}"))
                        ).extractall(target)


def converter() -> None:
    if (SRC / "convert_hf_to_gguf.py").exists():
        return
    print(f"Tải script chuyển đổi llama.cpp {BUILD}")
    data = fetch(f"https://codeload.github.com/ggml-org/llama.cpp/tar.gz/refs/tags/{BUILD}")
    with tarfile.open(fileobj=io.BytesIO(data)) as tar:
        for m in tar.getmembers():
            rel = m.name.split("/", 1)[-1]
            if rel == "convert_hf_to_gguf.py" or rel.startswith(("gguf-py/", "conversion/")):
                m.name = rel
                tar.extract(m, SRC)
    subprocess.run([PY, "-m", "pip", "install", "-q", str(SRC / "gguf-py"), "sentencepiece", "protobuf"], check=True)


def convert() -> None:
    if not (HF_DIR / "model.safetensors").exists():
        raise SystemExit("Chưa có models/Vintern-1B-v3_5 — chạy python download_models.py trước.")
    # Vintern không kèm preprocessor_config.json; script cần mean/std = IMAGENET như code suy luận chính thức.
    pre = HF_DIR / "preprocessor_config.json"
    if not pre.exists():
        pre.write_text(json.dumps({"image_mean": [0.485, 0.456, 0.406], "image_std": [0.229, 0.224, 0.225],
                                   "size": {"height": 448, "width": 448}}, indent=2), encoding="utf-8")
    OUT.mkdir(parents=True, exist_ok=True)
    model, mmproj = OUT / "Vintern-1B-v3_5-Q8_0.gguf", OUT / "mmproj-Vintern-1B-v3_5-Q8_0.gguf"
    conv = [PY, str(SRC / "convert_hf_to_gguf.py"), str(HF_DIR), "--outtype", "q8_0"]
    if not mmproj.exists():
        print("Chuyển bộ mã hoá ảnh → mmproj GGUF Q8")
        subprocess.run([*conv, "--mmproj", "--outfile", str(mmproj)], check=True)
    if not model.exists():
        print("Chuyển model ngôn ngữ → GGUF Q8")
        raw = OUT / "raw.gguf"
        subprocess.run([*conv, "--outfile", str(raw)], check=True)
        # Bản chuyển đổi thiếu eos_token_id → llama.cpp mặc định token 11 = dấu "," → câu bị cắt ở dấu phẩy.
        # Gán theo generation_config.json của Vintern: <|im_end|> = 151645, <|endoftext|> = 151643.
        subprocess.run([PY, "-m", "gguf.scripts.gguf_new_metadata", str(raw), str(model), "--force",
                        "--special-token-by-id", "eos", "151645", "--special-token-by-id", "eot", "151645",
                        "--special-token-by-id", "pad", "151643"], check=True)
        raw.unlink()


def check() -> None:
    from gguf import GGUFReader

    eos = GGUFReader(str(OUT / "Vintern-1B-v3_5-Q8_0.gguf")).fields["tokenizer.ggml.eos_token_id"].contents()
    assert eos == 151645, f"eos_token_id = {eos}, cần 151645"
    out = subprocess.run([str(TOOLS / "llama-vulkan" / "llama-server.exe"), "--list-devices"],
                         capture_output=True, text=True).stdout
    print("Thiết bị llama.cpp thấy được:\n" + out.strip())


if __name__ == "__main__":
    TOOLS.mkdir(exist_ok=True)
    llama_binaries()
    converter()
    convert()
    check()
    shutil.rmtree(SRC / "__pycache__", ignore_errors=True)
    print("Xong. Trong app chọn: Vintern-1B-v3.5 GGUF · llama.cpp")
