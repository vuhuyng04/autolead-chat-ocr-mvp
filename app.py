"""MVP: ảnh chụp đoạn chat Zalo / Messenger → transcript → tín hiệu lead (AutoLead).

    .venv\\Scripts\\python app.py      → http://127.0.0.1:7860
"""

import json
import os
from datetime import date

import gradio as gr
from PIL import Image

from extract import LABEL, llm_available
from pipeline import SAMPLES, analyse, from_text, read_image, sample_meta, to_text
from render import render, render_all
from scenarios import SCENARIOS, by_id, transcript_lines
from vlm import LLAMA, MOCK, VINTERN_MODELS, ApiVLM, HFRouterVLM, LlamaCppVLM, hf_label, model_ready

if not any(SAMPLES.glob("s*.png")):
    render_all(SAMPLES)

SAMPLE_IDS = [s["id"] for s in SCENARIOS]


def backends() -> list[str]:
    names = [LLAMA] if LlamaCppVLM.available() else []
    names += [n for n in VINTERN_MODELS if model_ready(n)]
    if HFRouterVLM.available():
        names.append(hf_label())
    if ApiVLM.available():
        names.append("API")
    return names + [MOCK]


def status_md() -> str:
    rows = [f"- **{n}**: {'✅ đã có trên máy' if model_ready(n) else '⚠️ chưa tải trọng số (xem README)'}"
            for n in VINTERN_MODELS]
    rows.insert(0, f"- **{LLAMA}** (nhanh, GPU Arc qua Vulkan): {'✅ sẵn sàng' if LlamaCppVLM.available() else '⚠️ thiếu tools/llama-* hoặc file GGUF'}")
    rows.append(f"- **{hf_label()}** (Hugging Face, ảnh rời máy): {'✅ có token' if HFRouterVLM.available() else '— chưa có HF_TOKEN'}")
    rows.append(f"- **VLM qua API**: {'✅ ' + os.getenv('VLM_MODEL', '') if ApiVLM.available() else '— chưa cấu hình VLM_API_KEY'}")
    rows.append(f"- **LLM trích tín hiệu**: {'✅ ' + os.getenv('LLM_MODEL', 'gpt-oss-120b') if llm_available() else '— chưa có LLM_API_KEY, dùng bộ luật offline'}")
    return "\n".join(rows)


# ---------------------------------------------------------------- tab 1: tạo ảnh


def gen_one(sid: str):
    s = by_id(sid)
    img, _ = render(s)
    img.save(SAMPLES / f"{sid}.png")
    gt = "\n".join(f"{a}: {b}" for a, b in transcript_lines(s))
    return img, gt, s["expect"]


# ---------------------------------------------------------------- tab 2: đọc + trích


def load_sample(sid: str):
    if not sid:
        return None, None
    return Image.open(SAMPLES / f"{sid}.png"), sid


def do_read(img, backend, mode, tiles, sid):
    if img is None:
        raise gr.Error("Chưa có ảnh.")
    try:
        r = read_image(img, backend, mode, int(tiles))
    except Exception as e:  # model chưa tải, ảnh không phải mẫu (giả lập), API lỗi…
        raise gr.Error(f"Không đọc được ảnh: {e}") from e
    info = (f"**Nền tảng:** {r['platform']} · **bong bóng tách được:** {r['bubbles'] or '— (chế độ cả trang)'} · "
            f"**thời gian OCR:** {r['seconds']} s · **backend:** {backend}")
    return r["overlay"], to_text(r["lines"]), info, r["raw"]


def _quote(item) -> str:
    return f"“{item['quote']}”" if item and item.get("quote") else ""


def card(res: dict, platform_note: str) -> str:
    rows = []

    def add(name, value, item):
        rows.append(f"| {name} | {value} | {_quote(item)} |")

    if res["models"]:
        for m in res["models"]:
            add("Mẫu xe quan tâm", m["name"], m)
    for m in res["dropped_models"]:
        add("Bỏ mẫu xe", f"~~{m['name']}~~", m)
    f, c, ep = res["finance"], res["co_decider"], res["expected_purchase"]
    add("Tài chính", LABEL[f["value"]] if f else "chưa rõ", f)
    add("Người cùng quyết định", LABEL[c["value"]] if c else "chưa rõ", c)
    if ep:
        add("Thời điểm mua", f"{ep['text']} (~{ep['days']} ngày)" if ep.get("days") else f"{ep['text']} (mơ hồ, không quy đổi)", ep)
    for e in res["events"]:
        what = "Khách từ chối" if e["type"] == "contact" else LABEL[e["type"]]
        add("Mốc", what + (f" · {e['model']}" if e.get("model") else ""), e)
    for col in res["colors"]:
        add("Màu thích", col["value"], col)
    md = [f"### Đề xuất ghi vào lead — chờ TVV xác nhận\n\n{platform_note}\n",
          "| Trường | Giá trị | Căn cứ (trích nguyên văn) |", "|---|---|---|", *rows]
    if res["summary"]:
        md += ["\n**Dòng vá vào `summary_md` (nguồn: ảnh):**", *[f"- {s}" for s in res["summary"]]]
    if res["contacts"]:
        md.append("\n**Kênh liên lạc phát hiện (code đọc, không gửi LLM):** " + ", ".join(res["contacts"]))
    if res["dropped"]:
        md += ["\n**Bị loại ở bước kiểm (không có căn cứ / sai enum):**", *[f"- `{d}`" for d in res["dropped"]]]
    return "\n".join(md)


def score_md(out: dict) -> str:
    if "fields" not in out:
        return "_Ảnh tự tải lên — không có đáp án để chấm._"
    tr, fs = out["transcript"], out["fields"]
    rows = [f"| {k} | `{v['expected']}` | `{v['got']}` | {'✅' if v['ok'] else '❌'} |" for k, v in fs["fields"].items()]
    return (f"### So với đáp án\n\n**CER** {tr['cer']:.3f} · **dòng đọc được** {tr['lines_found']} · "
            f"**đúng người nói** {tr['speaker_acc']:.0%} · **đúng trường** {fs['accuracy']:.0%}\n\n"
            "| Trường | Đáp án | Trích được | |\n|---|---|---|---|\n" + "\n".join(rows))


def do_extract(transcript, method, sid, info):
    lines = from_text(transcript or "")
    if not lines:
        raise gr.Error("Transcript trống hoặc sai định dạng (mỗi dòng 'TVV: …' hoặc 'KH: …').")
    if method == "llm" and not llm_available():
        raise gr.Error("Chưa có LLM_API_KEY trong .env — chọn 'rules' hoặc thêm key.")
    try:
        out = analyse(lines, method, sample_meta(sid))
    except Exception as e:
        raise gr.Error(f"Trích tín hiệu lỗi: {e}") from e
    res = out["result"]
    return card(res, info or ""), score_md(out), json.dumps(res, ensure_ascii=False, indent=1)


# ---------------------------------------------------------------- tab 3: chấm cả bộ


def run_all(backend, mode, tiles, method, progress=gr.Progress()):
    rows = []
    for sid in progress.tqdm(SAMPLE_IDS, desc="Đang chấm"):
        meta = sample_meta(sid)
        try:
            r = read_image(Image.open(SAMPLES / f"{sid}.png"), backend, mode, int(tiles))
        except Exception as e:
            raise gr.Error(f"{sid}: {e}") from e
        out = analyse(r["lines"], method, meta)
        rows.append([sid, out["transcript"]["cer"], out["transcript"]["lines_found"],
                     out["transcript"]["speaker_acc"], out["fields"]["accuracy"], r["seconds"]])
    n = len(rows)
    avg = (f"**Trung bình:** CER {sum(r[1] for r in rows) / n:.3f} · đúng người nói {sum(r[3] for r in rows) / n:.0%} · "
           f"đúng trường {sum(r[4] for r in rows) / n:.0%} · OCR {sum(r[5] for r in rows) / n:.1f} s/ảnh")
    return rows, avg


# ---------------------------------------------------------------- giao diện

with gr.Blocks(title="AutoLead · Đọc ảnh chat") as demo:
    gr.Markdown(
        "# AutoLead · MVP đọc ảnh chụp đoạn chat Zalo / Messenger\n"
        "Ảnh → **code tách bong bóng & gán người nói** → **VLM chép chữ** → **TVV duyệt transcript** → "
        "**trích tín hiệu** (mẫu xe, tài chính, người cùng quyết, thời điểm mua, mốc) kèm trích dẫn nguyên văn.\n\n"
        f"Hôm nay: {date.today():%d/%m/%Y}. Mọi kịch bản là **tự dựng**, không có khách thật.")
    with gr.Accordion("Trạng thái model", open=False):
        gr.Markdown(status_md())
    sid_state = gr.State(None)

    with gr.Tab("1 · Đọc ảnh & trích tín hiệu"):
        with gr.Row():
            with gr.Column(scale=1):
                sample = gr.Dropdown(SAMPLE_IDS, label="Ảnh mẫu tự sinh", value=SAMPLE_IDS[0])
                image = gr.Image(type="pil", format="png", label="Ảnh chụp đoạn chat (hoặc tải ảnh của bạn)", height=560)
                backend = gr.Dropdown(backends(), value=backends()[0], label="Đọc chữ bằng")
                mode = gr.Radio([("Tách bong bóng (khuyên dùng)", "bubbles"), ("Cả trang — VLM tự gán người nói", "page")],
                                value="bubbles", label="Cách đọc")
                tiles = gr.Slider(1, 6, value=1, step=1, label="Số ô 448px mỗi ảnh (nhiều hơn = rõ hơn, chậm hơn)")
                read_btn = gr.Button("① Đọc ảnh", variant="primary")
            with gr.Column(scale=1):
                overlay = gr.Image(format="png", label="Bong bóng tách được (xanh = KH, cam = TVV)", height=560)
                info = gr.Markdown()
                with gr.Accordion("Output thô của VLM", open=False):
                    raw = gr.Textbox(lines=8, show_label=False)
            with gr.Column(scale=1):
                transcript = gr.Textbox(lines=14, label="② Transcript — TVV duyệt / sửa trước khi ghi RAW")
                method = gr.Radio([("Bộ luật (offline)", "rules"), ("LLM (gpt-oss-120b / OpenAI-compatible)", "llm")],
                                  value="llm" if llm_available() else "rules", label="Trích tín hiệu bằng")
                ext_btn = gr.Button("③ Trích tín hiệu", variant="primary")
        with gr.Row():
            card_md = gr.Markdown()
            score = gr.Markdown()
        with gr.Accordion("JSON đầy đủ", open=False):
            res_json = gr.Code(language="json")

    with gr.Tab("2 · Chấm cả bộ ảnh mẫu"):
        with gr.Row():
            b2 = gr.Dropdown(backends(), value=backends()[0], label="Đọc chữ bằng")
            m2 = gr.Radio([("Tách bong bóng", "bubbles"), ("Cả trang", "page")], value="bubbles", label="Cách đọc")
            t2 = gr.Slider(1, 6, value=1, step=1, label="Số ô 448px")
            e2 = gr.Radio([("Bộ luật", "rules"), ("LLM", "llm")], value="rules", label="Trích bằng")
        run_btn = gr.Button("Chạy cả 6 ảnh", variant="primary")
        table = gr.Dataframe(headers=["Ảnh", "CER", "Dòng đọc được", "Đúng người nói", "Đúng trường", "Giây OCR"])
        avg_md = gr.Markdown()

    with gr.Tab("3 · Tạo ảnh mẫu"):
        with gr.Row():
            with gr.Column():
                sc = gr.Dropdown(SAMPLE_IDS, value=SAMPLE_IDS[0], label="Kịch bản")
                gen_btn = gr.Button("Vẽ ảnh")
                gt_text = gr.Textbox(lines=12, label="Transcript chuẩn")
                gt_json = gr.JSON(label="Đáp án tín hiệu")
            gen_img = gr.Image(format="png", label="Ảnh sinh ra", height=640)
        gr.Markdown("Kịch bản nằm ở `scenarios.py` — thêm kịch bản mới rồi chạy `python render.py`.")

    sample.change(load_sample, sample, [image, sid_state])
    image.upload(lambda: None, None, sid_state)
    read_btn.click(do_read, [image, backend, mode, tiles, sid_state], [overlay, transcript, info, raw])
    ext_btn.click(do_extract, [transcript, method, sid_state, info], [card_md, score, res_json])
    run_btn.click(run_all, [b2, m2, t2, e2], [table, avg_md])
    gen_btn.click(gen_one, sc, [gen_img, gt_text, gt_json])
    demo.load(load_sample, sample, [image, sid_state])

if __name__ == "__main__":
    demo.launch(server_name="127.0.0.1", server_port=int(os.getenv("PORT", 7860)), inbrowser=True)
