"""Chấm transcript (CER, gán người nói) và tín hiệu (so với đáp án của kịch bản)."""


def edit_distance(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def cer(pred: str, gt: str) -> float:
    return edit_distance(pred, gt) / max(1, len(gt))


def align(pred: list[dict], gt: list[dict]) -> list[tuple[int | None, int | None]]:
    """Ghép dòng dự đoán với dòng chuẩn (quy hoạch động, chi phí = CER, bỏ một dòng = 1)."""
    n, m = len(pred), len(gt)
    dp = [[float("inf")] * (m + 1) for _ in range(n + 1)]
    move = [[None] * (m + 1) for _ in range(n + 1)]
    dp[0][0] = 0.0
    for i in range(n + 1):
        for j in range(m + 1):
            base = dp[i][j]
            if i < n and base + 1 < dp[i + 1][j]:
                dp[i + 1][j], move[i + 1][j] = base + 1, "pred"
            if j < m and base + 1 < dp[i][j + 1]:
                dp[i][j + 1], move[i][j + 1] = base + 1, "gt"
            if i < n and j < m:
                c = base + min(1.0, cer(pred[i]["text"], gt[j]["text"]))
                if c < dp[i + 1][j + 1]:
                    dp[i + 1][j + 1], move[i + 1][j + 1] = c, "both"
    pairs, i, j = [], n, m
    while i or j:
        mv = move[i][j]
        if mv == "both":
            i, j = i - 1, j - 1
            pairs.append((i, j))
        elif mv == "pred":
            i -= 1
            pairs.append((i, None))
        else:
            j -= 1
            pairs.append((None, j))
    return pairs[::-1]


def transcript_score(pred: list[dict], gt: list[dict]) -> dict:
    pairs = align(pred, gt)
    matched = [(pred[i], gt[j]) for i, j in pairs if i is not None and j is not None]
    good = [(p, g) for p, g in matched if cer(p["text"], g["text"]) < 0.5]
    total_gt = sum(len(g["text"]) for g in gt)
    errors = sum(edit_distance(p["text"], g["text"]) for p, g in matched)
    errors += sum(len(gt[j]["text"]) for i, j in pairs if i is None and j is not None)  # dòng bị sót
    return {
        "cer": round(errors / max(1, total_gt), 3),
        "lines_found": f"{len(good)}/{len(gt)}",
        "speaker_acc": round(sum(p["speaker"] == g["speaker"] for p, g in good) / max(1, len(good)), 3),
        "pairs": [(pred[i] if i is not None else None, gt[j] if j is not None else None) for i, j in pairs],
    }


def summarize(res: dict) -> dict:
    """Kết quả trích → cùng dạng với `expect` của kịch bản."""
    return {
        "models": sorted(m["name"] for m in res["models"]),
        "dropped_models": sorted(m["name"] for m in res["dropped_models"]),
        "finance": (res["finance"] or {}).get("value", "unknown"),
        "co_decider": (res["co_decider"] or {}).get("value", "unknown"),
        "expected_days": (res["expected_purchase"] or {}).get("days"),
        "events": sorted(e["type"] + (f":{e['outcome']}" if e.get("outcome") else "") for e in res["events"]),
        "colors": sorted(c["value"] for c in res["colors"]),
    }


def field_score(res: dict, expect: dict) -> dict:
    got = summarize(res)
    rows = {}
    for k, want in expect.items():
        have = got[k]
        if k == "expected_days":
            ok = (have is None and want is None) or (have is not None and want is not None and abs(have - want) <= 7)
        elif isinstance(want, list):
            ok = sorted(want) == have
        else:
            ok = have == want
        rows[k] = {"expected": want, "got": have, "ok": ok}
    return {"fields": rows, "accuracy": round(sum(r["ok"] for r in rows.values()) / len(rows), 3)}
