"""Tải trọng số Vintern về thư mục models/ (cần mạng vào được huggingface.co).

    python download_models.py            # v3.5 (≈3,8 GB)
    python download_models.py --v2       # thêm v2 (≈1,9 GB)
"""

import sys

from huggingface_hub import snapshot_download

from vlm import MODELS_DIR, VINTERN_MODELS

FILES = ["*.json", "*.py", "*.safetensors", "*.txt"]

names = ["Vintern-1B-v3.5"] + (["Vintern-1B-v2"] if "--v2" in sys.argv else [])
for name in names:
    repo = VINTERN_MODELS[name]
    target = MODELS_DIR / repo.split("/")[1]
    print(f"Tải {repo} → {target}")
    snapshot_download(repo, local_dir=target, allow_patterns=FILES)
print("Xong.")
