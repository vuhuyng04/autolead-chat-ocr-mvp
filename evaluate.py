"""Chấm cả bộ ảnh mẫu, ghi báo cáo vào results/.

    python evaluate.py                                   # Vintern-1B-v3.5, tách bong bóng, trích bằng luật
    python evaluate.py --backend Vintern-1B-v2 --mode page
    python evaluate.py --method llm                      # trích bằng LLM (cần LLM_API_KEY trong .env)
    python evaluate.py --backend mock                    # chỉ chấm phần trích (transcript chuẩn)
"""

import argparse
import time
from datetime import datetime

from PIL import Image

from pipeline import ROOT, SAMPLES, analyse, read_image, sample_meta, to_text
from render import render_all
from vlm import LLAMA, MOCK, hf_label


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", default="Vintern-1B-v3.5", help="llama | hf | Vintern-1B-v3.5 | Vintern-1B-v2 | api | mock")
    ap.add_argument("--mode", default="bubbles", choices=["bubbles", "page"])
    ap.add_argument("--method", default="rules", choices=["rules", "llm"])
    ap.add_argument("--tiles", type=int, default=1)
    ap.add_argument("--only", default="", help="chỉ chạy kịch bản có id chứa chuỗi này")
    a = ap.parse_args()
    alias = {"mock": MOCK, "api": "API", "llama": LLAMA, "hf": hf_label()}
    backend = alias.get(a.backend.lower(), a.backend)

    if not any(SAMPLES.glob("s*.png")):
        render_all(SAMPLES)

    rows, details = [], []
    for png in sorted(SAMPLES.glob("s*.png")):
        if a.only and a.only not in png.stem:
            continue
        meta = sample_meta(png.stem)
        t0 = time.perf_counter()
        read = read_image(Image.open(png), backend, a.mode, a.tiles)
        res = analyse(read["lines"], a.method, meta)
        tr, fs = res["transcript"], res["fields"]
        rows.append((png.stem, tr["cer"], tr["lines_found"], tr["speaker_acc"], fs["accuracy"], read["seconds"]))
        print(f"{png.stem:26} CER {tr['cer']:.3f}  dòng {tr['lines_found']:>5}  người nói {tr['speaker_acc']:.2f}  "
              f"trường {fs['accuracy']:.2f}  OCR {read['seconds']}s  (tổng {time.perf_counter() - t0:.0f}s)")
        wrong = {k: v for k, v in fs["fields"].items() if not v["ok"]}
        details.append(f"### {png.stem}\n\n```\n{to_text(read['lines'])}\n```\n\n"
                       f"Trường sai: {wrong or 'không'}\n\nBị loại ở bước kiểm: {res['result']['dropped'] or 'không'}\n")

    n = max(1, len(rows))
    avg = lambda k: sum(r[k] for r in rows) / n  # noqa: E731
    out = ROOT / "results"
    out.mkdir(exist_ok=True)
    name = f"{a.backend}-{a.mode}-{a.method}".replace(" ", "_").replace(":", "")
    report = out / f"report-{name}.md"
    table = "\n".join(f"| {r[0]} | {r[1]:.3f} | {r[2]} | {r[3]:.2f} | {r[4]:.2f} | {r[5]} |" for r in rows)
    report.write_text(
        f"# Báo cáo: {backend} · {a.mode} · trích bằng {a.method}\n\n{datetime.now():%d/%m/%Y %H:%M}\n\n"
        "| Ảnh | CER | Dòng đọc được | Đúng người nói | Đúng trường | Giây OCR |\n|---|---|---|---|---|---|\n"
        f"{table}\n| **Trung bình** | **{avg(1):.3f}** | | **{avg(3):.2f}** | **{avg(4):.2f}** | **{avg(5):.1f}** |\n\n"
        + "\n".join(details),
        encoding="utf-8",
    )
    print(f"\nTB: CER {avg(1):.3f} · người nói {avg(3):.2f} · trường {avg(4):.2f} · OCR {avg(5):.1f}s/ảnh → {report}")


if __name__ == "__main__":
    main()
