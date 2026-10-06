"""Quay video demo một ảnh qua giao diện (app.py phải đang chạy ở cổng 7860).

    python record_demo.py [id ảnh mẫu]      → videos/demo-<id>.mp4

Dùng Chrome có sẵn trên máy (Playwright channel="chrome") nên không phải tải trình duyệt.
"""

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).parent
URL = os.getenv("DEMO_URL", "http://127.0.0.1:7860/")
SAMPLE = sys.argv[1] if len(sys.argv) > 1 else "s5_zalo_doi_mau_sdt"
BACKEND = os.getenv("DEMO_BACKEND", "Vintern-1B-v3.5 GGUF · llama.cpp")
BACKEND_NOTE = os.getenv("DEMO_BACKEND_NOTE", "chạy local trên GPU Intel Arc (Vulkan), ảnh không rời máy")
SIZE = {"width": 1600, "height": 1000}
FFMPEG = shutil.which("ffmpeg") or "C:/ffmpeg/ffmpeg.exe"

CAPTION_JS = """(text) => {
  let el = document.getElementById('demo-caption');
  if (!el) {
    el = document.createElement('div');
    el.id = 'demo-caption';
    el.style.cssText = 'position:fixed;left:50%;bottom:28px;transform:translateX(-50%);z-index:99999;' +
      'background:rgba(17,24,39,.92);color:#fff;font:600 22px/1.35 Segoe UI,sans-serif;padding:12px 22px;' +
      'border-radius:12px;box-shadow:0 6px 24px rgba(0,0,0,.25);max-width:1200px;text-align:center';
    document.body.appendChild(el);
  }
  el.textContent = text;
}"""


def main() -> None:
    out_dir = ROOT / "videos"
    out_dir.mkdir(exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        ctx = browser.new_context(viewport=SIZE, record_video_dir=str(out_dir), record_video_size=SIZE)
        page = ctx.new_page()

        def caption(text: str, hold: float = 0) -> None:
            page.evaluate(CAPTION_JS, text)
            time.sleep(hold)

        page.goto(URL)
        page.get_by_role("button", name="① Đọc ảnh").wait_for()
        caption("AutoLead · MVP đọc ảnh chụp đoạn chat — kịch bản sale xe tự dựng, không có khách thật", 3)

        page.get_by_role("listbox", name="Ảnh mẫu tự sinh").click()
        page.get_by_role("option", name=SAMPLE, exact=True).click()
        caption(f"Ảnh chụp màn hình Zalo: {SAMPLE}", 3)

        page.get_by_role("listbox", name="Đọc chữ bằng").click()
        page.get_by_role("option", name=BACKEND, exact=True).click()
        caption(f"Đọc chữ bằng: {BACKEND} — {BACKEND_NOTE}", 3)

        page.get_by_role("button", name="① Đọc ảnh").click()
        caption("① Code tách bong bóng + gán người nói → Vintern chép chữ từng bong bóng…")
        t0 = time.perf_counter()
        page.get_by_text("thời gian OCR").first.wait_for(timeout=600_000)
        caption(f"Xong sau {time.perf_counter() - t0:.0f} s · Khung xanh = khách (KH), khung cam = tư vấn viên (TVV)", 5)

        page.get_by_role("button", name="Output thô của VLM").click()
        caption("Output thô của Vintern cho từng bong bóng (giờ gửi của Zalo được code bỏ đi)", 5)

        page.get_by_label("② Transcript — TVV duyệt / sửa trước khi ghi RAW").scroll_into_view_if_needed()
        caption("② Transcript dạng RAW của AutoLead (TVV: … / KH: …) — tư vấn viên duyệt, sửa được trước khi ghi", 5)

        page.get_by_role("button", name="③ Trích tín hiệu").click()
        page.get_by_text("So với đáp án").first.wait_for(timeout=120_000)
        caption("③ Trích tín hiệu theo bộ trường AutoLead — mỗi giá trị kèm trích dẫn nguyên văn", 1)
        page.get_by_text("Đề xuất ghi vào lead").first.scroll_into_view_if_needed()
        page.mouse.wheel(0, 250)
        time.sleep(6)
        caption("Đổi VF 6 → VF 7 · trả góp · vợ đã cùng xem xe · mua tháng sau · SĐT do code đọc, che trước khi gửi LLM", 7)
        page.mouse.wheel(0, 600)
        caption("So với đáp án của kịch bản: CER, đúng người nói, đúng từng trường", 6)

        video = page.video.path()
        ctx.close()
        browser.close()

    webm = Path(video)
    tag = "llama" if "llama" in BACKEND else ("hf" if BACKEND.startswith("HF") else "pytorch")
    mp4 = out_dir / f"demo-{SAMPLE}-{tag}.mp4"
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-i", str(webm), "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-crf", "23", "-movflags", "+faststart", str(mp4)], check=True)
    webm.unlink(missing_ok=True)
    print(mp4)


if __name__ == "__main__":
    main()
