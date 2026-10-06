"""Transcript (TVV/KH) → tín hiệu khách theo đúng bộ trường của AutoLead.

Hai cách trích, chung một bước kiểm:
- "llm": LLM tương thích OpenAI (mặc định FPT AI Factory `gpt-oss-120b`, giống dự án). Text đã che SĐT.
- "rules": luật + từ khoá, chạy offline, để demo không cần key và làm mốc so sánh.

Bước kiểm (giống `claims.py` của dự án): mỗi tín hiệu phải kèm trích dẫn có thật trong transcript, giá
trị phải thuộc enum, tên mẫu xe phải có trong danh mục. Không đạt → bỏ, ghi lý do vào `dropped`.
"""

import json
import os
import re
import unicodedata
from datetime import date, timedelta

from scenarios import CATALOG_COLORS, CATALOG_MODELS

FINANCE = ("insufficient", "enough_with_loan", "enough_cash")
CO_DECIDER = ("self", "yes_not_involved", "yes_involved")
EVENTS = ("test_drive", "deposit", "deposit_cancelled", "contact")
LABEL = {
    "insufficient": "chưa đủ tài chính", "enough_with_loan": "đủ nếu vay / trả góp", "enough_cash": "trả thẳng",
    "self": "tự quyết", "yes_not_involved": "có người cùng quyết, chưa tham gia",
    "yes_involved": "có người cùng quyết, đã tham gia", "unknown": "chưa rõ",
    "test_drive": "đã lái thử", "deposit": "đã đặt cọc", "deposit_cancelled": "huỷ cọc", "contact": "liên lạc",
}

# ---------------------------------------------------------------- tiện ích chữ

PHONE = re.compile(r"(?<!\d)(?:\+?84|0)(?:[\s.\-]?\d){8,10}(?!\d)")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
CCCD = re.compile(r"(?<!\d)\d{12}(?!\d)")


def mask(text: str) -> str:
    """Che định danh trước khi gửi LLM (ADR-017 của dự án). Tên gọi giữ lại."""
    for p, label in ((EMAIL, "[EMAIL]"), (CCCD, "[CCCD]"), (PHONE, "[SĐT]")):
        text = p.sub(label, text)
    return text


def fold(s: str) -> str:
    s = unicodedata.normalize("NFD", s.lower().replace("đ", "d"))
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


TEENCODE = {
    "e": "em", "a": "anh", "c": "chị", "dc": "được", "đc": "được", "k": "không", "ko": "không", "kh": "không",
    "hok": "không", "bn": "bao nhiêu", "hn": "hà nội", "vs": "với", "ck": "chồng", "vk": "vợ", "trc": "trước",
    "r": "rồi", "j": "gì", "mk": "mình", "ok": "ok", "oke": "ok",
}


def norm(text: str) -> str:
    words = re.findall(r"\w+|[^\w\s]", text.lower())
    return " ".join(TEENCODE.get(w, w) for w in words)


def has(pattern: str, text: str) -> bool:
    """Câu có dấu → khớp có dấu. Câu gõ không dấu → khớp bản bỏ dấu (tránh "bà" khớp nhầm "ba")."""
    n = norm(text)
    if any(ord(c) > 127 for c in text):
        return bool(re.search(pattern, n))
    return bool(re.search(fold(pattern), fold(n)))


def model_spans(text: str) -> list[tuple[str, str, str]]:
    """(tên mẫu, phần trước, phần sau) trên bản đã chuẩn hoá + bỏ dấu."""
    f = fold(norm(text))
    out = []
    for m in re.finditer(r"\bvf\s*(\d+|wild)\b", f):
        name = "VF Wild" if m.group(1) == "wild" else f"VF {m.group(1)}"
        if name in CATALOG_MODELS:
            out.append((name, f[: m.start()], f[m.end():]))
    return out


def find_models(text: str) -> list[str]:
    seen = []
    for name, _, _ in model_spans(text):
        if name not in seen:
            seen.append(name)
    return seen


# ---------------------------------------------------------------- luật (offline)

RELATIVE = r"\b(vợ|chồng|bố|mẹ|ba|má|con|ông|bà|anh trai|chị gái|gia đình)\b"
CUES = {
    ("finance", "enough_cash"): r"tiền mặt|trả thẳng|trả hết|trả đủ|không (cần |phải )?vay|một lần|tiền sẵn|có sẵn",
    ("finance", "insufficient"): r"chưa đủ|thiếu|chưa gom|chưa lo|không đủ|eo hẹp|chưa xoay|chưa có tiền|đang gom",
    ("finance", "enough_with_loan"): r"vay|trả góp|ngân hàng",
    ("co_decider", "self"): r"tự quyết|tự mình|không (cần |phải )?hỏi|một mình|tự định|tự lo",
    ("co_decider", "yes_not_involved"): RELATIVE + r".*(chưa|hỏi|bàn|ý kiến)|(chưa|hỏi|bàn|ý kiến).*" + RELATIVE,
    ("co_decider", "yes_involved"): RELATIVE + r".*(đã|cùng|đi|gọi|qua|xem|lái|trao đổi)",
    ("contact", "rejected"): r"không mua|từ chối|^thôi|không có nhu cầu|chưa có nhu cầu|không lấy nữa|dừng",
    ("test_drive", None): r"lái thử",
    ("deposit", None): r"cọc",
    ("deposit_cancelled", None): r"hu[ỷủ] cọc|rút cọc|trả (lại )?cọc|lấy lại cọc",
}
PAST = r"\bđã\b|\brồi\b|hôm qua|hôm trước|hôm kia|vừa|nhận được"
NOT_YET = r"muốn|định|\bsẽ\b|hẹn|dự định|chuẩn bị|chiều nay|sáng mai|ngày mai|cuối tuần|\bnhé\b|\bnha\b|\?"
YES = r"^(có|ừ|ừm|vâng|dạ vâng|ok|đúng|uh|um|được)\b"
DROP_BEFORE = r"(không (còn )?(quan tâm|thích|lấy|mua)|thôi|bỏ|chuyển từ|đổi từ)\s*(mẫu\s*)?$"
ONLY_BEFORE = r"(chỉ (lấy|cần|quan tâm|thích|chọn)|chốt|chuyển( hẳn)? sang|đổi sang|sang|quay về)\s*(mẫu\s*)?$"
ONLY_AFTER = r"^\s*(là đủ|thôi là đủ)"
CONCERN = r"\blo\b|\bsợ\b|băn khoăn|\bngại\b|lăn tăn|hơi (bé|nhỏ|đắt|chật)|chưa yên tâm"
NEXT = r"hẹn|thứ \d|chủ nhật|cuối tuần|chiều nay|sáng mai|ngày mai|tuần sau|gửi|qua showroom"


def _search(pattern: str, text: str):
    n = norm(text)
    return re.search(pattern, n) if any(ord(c) > 127 for c in text) else re.search(fold(pattern), fold(n))


def _purchase(text: str):
    """Thời điểm mua khách nêu: (số ngày | None nếu mơ hồ | "none" nếu không nói, cụm gốc)."""
    if m := _search(r"(\d+)\s*tháng (nữa|tới)", text):
        return int(m.group(1)) * 30, m.group(0)
    if m := _search(r"(\d+)\s*tuần (nữa|tới)", text):
        return int(m.group(1)) * 7, m.group(0)
    for pat, days in ((r"tháng (sau|tới)", 30), (r"tuần (sau|tới)", 7)):
        if m := _search(pat, text):
            return days, m.group(0)
    if m := _search(r"cuối năm|đầu năm|sang năm|năm sau|sau tết|qua tết", text):
        return None, m.group(0)
    return "none", None


def extract_rules(lines: list[dict]) -> dict:
    out = _empty()
    mentioned: list[str] = []
    for i, ln in enumerate(lines):
        sp, text = ln["speaker"], ln["text"]
        prev = lines[i - 1] if i else None
        # Khách đồng ý với câu hỏi / đề xuất ngay trước của TVV → nội dung câu TVV tính như lời khách.
        affirmed = bool(sp == "KH" and prev and prev["speaker"] == "TVV" and has(YES, text))
        sources = []  # (câu dùng để đọc, trích dẫn); lời TVV một mình không phải thông tin về khách
        if sp == "KH":
            sources.append((text, text))
        if affirmed:
            sources.append((prev["text"], f"{prev['text']} / {text}"))

        for t, quote in sources:
            for model, head, tail in model_spans(t):
                item = {"name": model, "quote": quote}
                if re.search(fold(DROP_BEFORE), head):
                    out["dropped_models"].append(item)
                elif re.search(fold(ONLY_BEFORE), head) or re.search(fold(ONLY_AFTER), tail):
                    out["only_model"] = item
                    out["models"].append(item)
                else:
                    out["models"].append(item)
            for color in CATALOG_COLORS:
                if has(r"màu " + color.lower(), t):
                    out["colors"].append({"value": color, "quote": quote})
            for value in ("enough_cash", "insufficient", "enough_with_loan"):
                if not out["finance"] and has(CUES[("finance", value)], t):
                    out["finance"] = {"value": value, "quote": quote}
            for value in ("self", "yes_not_involved", "yes_involved"):
                if not out["co_decider"] and has(CUES[("co_decider", value)], t):
                    out["co_decider"] = {"value": value, "quote": quote}
            days, phrase = _purchase(t)
            if days != "none" and not out["expected_purchase"]:
                out["expected_purchase"] = {"text": phrase, "days": days, "quote": quote}

        if sp == "KH" and has(CONCERN, text):
            out["concerns"].append({"text": text, "quote": text})
        if sp == "KH" and has(CUES[("contact", "rejected")], text) and not find_models(text):
            out["events"].append({"type": "contact", "outcome": "rejected", "model": None, "quote": text})

        # Mốc (lái thử, cọc): chỉ khi đã xảy ra. TVV xác nhận "đã nhận cọc" cũng là căn cứ.
        mentioned += find_models(text)
        for etype in ("deposit_cancelled", "test_drive", "deposit"):
            if has(CUES[(etype, None)], text) and has(PAST, text) and not has(NOT_YET, text):
                if etype == "deposit" and has(CUES[("deposit_cancelled", None)], text):
                    continue
                model = find_models(text) or find_models(prev["text"] if prev else "") or mentioned[-1:]
                out["events"].append({"type": etype, "outcome": None, "model": model[-1] if model else None,
                                      "quote": text})
                break

        # Việc tiếp theo: khách hẹn / hứa, hoặc khách đồng ý đề xuất của TVV.
        if affirmed and (has(NEXT, prev["text"]) or has(NEXT, text)):
            q = f"{prev['text']} / {text}"
            out["next_steps"].append({"text": q, "quote": q})
        elif sp == "KH" and has(NEXT, text) and has(NOT_YET, text):
            out["next_steps"].append({"text": text, "quote": text})
    return out


# ---------------------------------------------------------------- LLM

SYSTEM = """Bạn trích thông tin bán hàng ô tô từ đoạn chat giữa tư vấn viên (TVV) và khách (KH).
Danh mục mẫu xe: {models}. Màu: {colors}. Hôm nay: {today}.

Quy tắc:
- Chỉ lời KH là thông tin về khách. Lời TVV chỉ là ngữ cảnh: nếu TVV hỏi/đề xuất và KH đồng ý ("có", "ừ",
  "ok") thì coi như KH nói ý đó; quote khi ấy ghi "câu TVV / câu KH".
- Ý định không phải sự kiện: "hẹn lái thử", "chiều nay sẽ cọc" → next_steps. Chỉ ghi events khi đã xảy ra
  ("hôm qua lái thử", "đã nhận cọc").
- Thời điểm mua: nói rõ ("3 tháng nữa", "tháng sau") thì days = số ngày; mơ hồ ("cuối năm") thì days = null.
- quote phải chép NGUYÊN VĂN từ đoạn chat. Không suy đoán. Không có thông tin thì để null / [].

Trả về DUY NHẤT một JSON:
{{"models":[{{"name":"VF 7","quote":"..."}}],
 "dropped_models":[{{"name":"VF 6","quote":"..."}}],
 "only_model":{{"name":"VF 7","quote":"..."}} | null,
 "finance":{{"value":"insufficient|enough_with_loan|enough_cash","quote":"..."}} | null,
 "co_decider":{{"value":"self|yes_not_involved|yes_involved","quote":"..."}} | null,
 "expected_purchase":{{"text":"3 tháng nữa","days":90,"quote":"..."}} | null,
 "events":[{{"type":"test_drive|deposit|deposit_cancelled|contact","outcome":"rejected|null","model":"VF 3|null","quote":"..."}}],
 "colors":[{{"value":"Xám","quote":"..."}}],
 "concerns":[{{"text":"lo sạc ở chung cư","quote":"..."}}],
 "next_steps":[{{"text":"hẹn lái thử thứ 7","quote":"..."}}]}}"""


def llm_available() -> bool:
    return bool(os.getenv("LLM_API_KEY"))


def extract_llm(lines: list[dict], today: date | None = None) -> dict:
    from openai import OpenAI

    client = OpenAI(base_url=os.getenv("LLM_BASE_URL", "https://mkp-api.fptcloud.com/v1"),
                    api_key=os.getenv("LLM_API_KEY", ""))
    transcript = "\n".join(f"{ln['speaker']}: {mask(ln['text'])}" for ln in lines)
    system = SYSTEM.format(models=", ".join(CATALOG_MODELS), colors=", ".join(CATALOG_COLORS),
                           today=(today or date.today()).isoformat())
    r = client.chat.completions.create(
        model=os.getenv("LLM_MODEL", "gpt-oss-120b"), temperature=0,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": f"<data>\n{transcript}\n</data>"}],
    )
    text = r.choices[0].message.content or "{}"
    m = re.search(r"\{.*\}", text, re.S)
    data = json.loads(m.group(0)) if m else {}
    out = _empty()
    for k in out:
        if k in data and data[k] is not None:
            out[k] = data[k]
    return out


# ---------------------------------------------------------------- kiểm + tóm tắt


def _empty() -> dict:
    return {"models": [], "dropped_models": [], "only_model": None, "finance": None, "co_decider": None,
            "expected_purchase": None, "events": [], "colors": [], "concerns": [], "next_steps": []}


def _quoted(quote: str | None, lines: list[dict]) -> bool:
    if not quote:
        return False
    hay = fold(" \n ".join(mask(ln["text"]) + " \n " + ln["text"] for ln in lines))
    return all(fold(part.strip()) in hay for part in quote.split(" / ") if part.strip())


def verify(raw: dict, lines: list[dict]) -> dict:
    """Bỏ mọi tín hiệu không có căn cứ nguyên văn, sai enum hoặc sai danh mục."""
    out, dropped = _empty(), []

    def ok(item, what, cond=True):
        if item and cond and _quoted(item.get("quote"), lines):
            return True
        if item:
            dropped.append(f"{what}: {json.dumps(item, ensure_ascii=False)}")
        return False

    def dedupe(items, key):
        seen, res = set(), []
        for it in items:
            if it[key] not in seen:
                seen.add(it[key])
                res.append(it)
        return res

    out["models"] = dedupe([m for m in raw["models"] if ok(m, "mẫu xe", m.get("name") in CATALOG_MODELS)], "name")
    out["dropped_models"] = dedupe([m for m in raw["dropped_models"]
                                    if ok(m, "bỏ mẫu", m.get("name") in CATALOG_MODELS)], "name")
    if ok(raw["only_model"], "chỉ mẫu", (raw["only_model"] or {}).get("name") in CATALOG_MODELS):
        out["only_model"] = raw["only_model"]
    if ok(raw["finance"], "tài chính", (raw["finance"] or {}).get("value") in FINANCE):
        out["finance"] = raw["finance"]
    if ok(raw["co_decider"], "người cùng quyết", (raw["co_decider"] or {}).get("value") in CO_DECIDER):
        out["co_decider"] = raw["co_decider"]
    if ok(raw["expected_purchase"], "thời điểm mua"):
        out["expected_purchase"] = raw["expected_purchase"]
    for e in raw["events"]:
        if e.get("outcome") in ("null", ""):
            e["outcome"] = None
        if e.get("model") in ("null", ""):
            e["model"] = None
        valid = e.get("type") in EVENTS and (e.get("type") != "contact" or e.get("outcome") == "rejected")
        if ok(e, "mốc", valid):
            out["events"].append(e)
    for e in out["events"]:
        if e["type"] in ("test_drive", "deposit") and e.get("model") in CATALOG_MODELS:
            if e["model"] not in {m["name"] for m in out["models"]}:
                out["models"].append({"name": e["model"], "quote": e["quote"]})
    out["colors"] = dedupe([c for c in raw["colors"] if ok(c, "màu", c.get("value") in CATALOG_COLORS)], "value")
    out["concerns"] = [c for c in raw["concerns"] if ok(c, "băn khoăn")]
    out["next_steps"] = [c for c in raw["next_steps"] if ok(c, "việc tiếp theo")]

    # Luật của dự án: "đổi sang / chỉ" một mẫu hoặc đặt cọc một mẫu → mẫu đó là duy nhất, các mẫu khác bị bỏ.
    only = out["only_model"]["name"] if out["only_model"] else None
    deposit = next((e["model"] for e in out["events"] if e["type"] == "deposit" and e.get("model")), None)
    keep = deposit or only
    if keep:
        for m in out["models"]:
            if m["name"] != keep and m["name"] not in {d["name"] for d in out["dropped_models"]}:
                out["dropped_models"].append({"name": m["name"], "quote": (out["only_model"] or m)["quote"]})
        out["models"] = [m for m in out["models"] if m["name"] == keep] or [{"name": keep, "quote": ""}]
    dropped_names = {d["name"] for d in out["dropped_models"]}
    out["models"] = [m for m in out["models"] if m["name"] not in dropped_names]
    out["dropped"] = dropped
    return out


def contacts_found(lines: list[dict]) -> list[str]:
    """SĐT khách tự gửi trong chat → code đọc, đề xuất cập nhật kênh liên lạc (không qua LLM)."""
    return [m.group(0) for ln in lines if ln["speaker"] == "KH" for m in PHONE.finditer(ln["text"])]


def summary_lines(res: dict, today: date | None = None) -> list[str]:
    """Các dòng sẽ vá vào `summary_md` của lead (nguồn "ảnh"), theo khung 6 mục của dự án."""
    today = today or date.today()
    tag = f"(ảnh {today:%d/%m})"
    rows = []
    if res["models"]:
        need = ", ".join(m["name"] for m in res["models"])
        if res["colors"]:
            need += " · màu " + ", ".join(c["value"].lower() for c in res["colors"])
        rows.append(f"**Nhu cầu:** quan tâm {need} {tag}")
    if res["dropped_models"]:
        rows.append(f"**Nhu cầu:** không còn quan tâm {', '.join(m['name'] for m in res['dropped_models'])} {tag}")
    if res["finance"]:
        rows.append(f"**Tài chính:** {LABEL[res['finance']['value']]} — “{res['finance']['quote']}” {tag}")
    if res["co_decider"]:
        rows.append(f"**Người ảnh hưởng tới quyết định:** {LABEL[res['co_decider']['value']]} — "
                    f"“{res['co_decider']['quote']}” {tag}")
    ep = res["expected_purchase"]
    if ep:
        if ep.get("days"):
            when = today + timedelta(days=int(ep["days"]))
            rows.append(f"**Thời điểm mua:** dự kiến ~{when:%d/%m/%Y} (khách nói “{ep['text']}”) {tag}")
        else:
            rows.append(f"**Thời điểm mua:** mơ hồ — “{ep['text']}”, chưa quy đổi ngày {tag}")
    for e in res["events"]:
        what = "khách từ chối" if e["type"] == "contact" else LABEL[e["type"]]
        rows.append(f"**Mốc:** {what}{' ' + e['model'] if e.get('model') else ''} — “{e['quote']}” {tag}")
    for c in res["concerns"]:
        rows.append(f"**Lưu ý khi tiếp cận:** {c['text']} {tag}")
    for n in res["next_steps"]:
        rows.append(f"**Việc tiếp theo:** {n['text']} {tag}")
    return rows


def extract(lines: list[dict], method: str = "rules", today: date | None = None) -> dict:
    raw = extract_llm(lines, today) if method == "llm" else extract_rules(lines)
    res = verify(raw, lines)
    res["method"] = method
    res["contacts"] = contacts_found(lines)
    res["summary"] = summary_lines(res, today)
    return res
