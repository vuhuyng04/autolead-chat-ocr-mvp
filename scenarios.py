"""Kịch bản chat sale xe tự dựng (không có khách thật) + đáp án chuẩn để chấm.

Mỗi tin: (người nói, loại, nội dung, giờ). Người nói: "TVV" (tư vấn viên, người chụp màn hình,
bong bóng bên phải) hoặc "KH" (khách, bên trái). Loại: text · voice · sticker.

Đáp án (`expect`) dùng cùng enum với dự án AutoLead:
- finance: unknown · insufficient · enough_with_loan · enough_cash
- co_decider: unknown · self · yes_not_involved · yes_involved
- events: test_drive · deposit · contact:rejected  (ý định "hẹn lái thử", "sẽ cọc" KHÔNG phải sự kiện)
- expected_days: số ngày tới lúc mua nếu khách nói rõ; None nếu mơ hồ ("cuối năm") hoặc không nói.
"""

CATALOG_MODELS = ["VF 2", "VF 3", "VF 5", "VF 6", "VF 7", "VF 8", "VF 9", "VF Wild"]
CATALOG_COLORS = ["Trắng", "Đen", "Xám", "Bạc", "Đỏ", "Xanh dương", "Xanh lá", "Vàng", "Hồng", "Cam"]

SCENARIOS = [
    {
        "id": "s1_zalo_vf7_vay",
        "platform": "zalo",
        "contact_name": "Lan Nguyễn",
        "status": "Truy cập 5 phút trước",
        "day_label": "09:10 Hôm nay",
        "messages": [
            ("KH", "text", "Em ơi chị hỏi chút về VF 7 nhé", "09:10"),
            ("TVV", "text", "Dạ em chào chị Lan ạ. Chị đang quan tâm bản Eco hay bản Plus ạ?", "09:11"),
            ("KH", "text", "Chị thích bản Plus, màu xám", "09:12"),
            ("TVV", "text", "Dạ chị tính khoảng bao giờ lấy xe ạ?", "09:12"),
            ("KH", "text", "Chắc tầm 3 tháng nữa em", "09:13"),
            ("TVV", "text", "Về tài chính mình có cần hỗ trợ vay không chị?", "09:13"),
            ("KH", "text", "Có em, chị muốn vay khoảng 70%", "09:15"),
            ("KH", "text", "Để chị bàn thêm với chồng đã", "09:15"),
            ("TVV", "text", "Dạ vâng, cuối tuần anh chị qua showroom lái thử nhé", "09:16"),
            ("KH", "text", "Ok em, thứ 7 chị qua", "09:18"),
        ],
        "expect": {
            "models": ["VF 7"],
            "dropped_models": [],
            "finance": "enough_with_loan",
            "co_decider": "yes_not_involved",
            "expected_days": 90,
            "events": [],
            "colors": ["Xám"],
        },
    },
    {
        "id": "s2_messenger_vf8_coc",
        "platform": "messenger",
        "contact_name": "Tuấn Trần",
        "status": "Đang hoạt động",
        "day_label": "14:02",
        "messages": [
            ("KH", "text", "Shop cho mình hỏi VF 8 với VF 9 khác nhau nhiều không", "14:02"),
            ("TVV", "text", "Dạ VF 9 rộng hơn, có 7 chỗ ạ. Nhà mình đi mấy người anh?", "14:03"),
            ("KH", "text", "4 người thôi, VF 8 là đủ rồi", "14:05"),
            ("KH", "text", "Mình trả thẳng, không vay", "14:05"),
            ("TVV", "text", "Dạ anh tự quyết hay cần hỏi ý gia đình ạ?", "14:06"),
            ("KH", "text", "Mình tự quyết", "14:06"),
            ("KH", "text", "Chiều nay mình chuyển cọc VF 8 màu đen nhé", "14:08"),
            ("TVV", "text", "Dạ em đã nhận được tiền cọc 20 triệu rồi ạ, em cảm ơn anh", "16:40"),
        ],
        "expect": {
            "models": ["VF 8"],
            "dropped_models": ["VF 9"],
            "finance": "enough_cash",
            "co_decider": "self",
            "expected_days": None,
            "events": ["deposit"],
            "colors": ["Đen"],
        },
    },
    {
        "id": "s3_zalo_teencode_vf5",
        "platform": "zalo",
        "contact_name": "Hoàng Minh",
        "status": "Vừa mới truy cập",
        "day_label": "21:30 Hôm qua",
        "messages": [
            ("KH", "text", "a ơi vf5 lăn bánh hn bn vậy a", "21:30"),
            ("TVV", "text", "Dạ VF 5 lăn bánh Hà Nội khoảng 5xx triệu anh ạ, em gửi bảng giá chi tiết nhé", "21:32"),
            ("KH", "text", "ok a. e chưa đủ tiền, đang gom thêm", "21:35"),
            ("KH", "text", "chắc cuối năm mới mua dc", "21:35"),
            ("TVV", "text", "Dạ anh có lo gì về xe điện không ạ?", "21:36"),
            ("KH", "text", "e sợ sạc ở chung cư khó", "21:40"),
            ("KH", "text", "để e hỏi bố mẹ đã", "21:40"),
        ],
        "expect": {
            "models": ["VF 5"],
            "dropped_models": [],
            "finance": "insufficient",
            "co_decider": "yes_not_involved",
            "expected_days": None,
            "events": [],
            "colors": [],
        },
    },
    {
        "id": "s4_messenger_tu_choi",
        "platform": "messenger",
        "contact_name": "Thu Hà",
        "status": "Hoạt động 2 giờ trước",
        "day_label": "T3 10:20",
        "messages": [
            ("TVV", "text", "Chị Hà ơi, bên em đang có ưu đãi VF 6 tháng này ạ", "10:20"),
            ("KH", "text", "Thôi em ơi, nhà chị chưa có nhu cầu nữa", "11:02"),
            ("TVV", "text", "Dạ chị có muốn em giữ thông tin mẫu VF 6 không ạ?", "11:03"),
            ("KH", "text", "Không cần đâu em, chị không quan tâm VF 6 nữa", "11:05"),
            ("TVV", "text", "Dạ vâng, khi nào cần chị nhắn em nhé", "11:05"),
        ],
        "expect": {
            "models": [],
            "dropped_models": ["VF 6"],
            "finance": "unknown",
            "co_decider": "unknown",
            "expected_days": None,
            "events": ["contact:rejected"],
            "colors": [],
        },
    },
    {
        "id": "s5_zalo_doi_mau_sdt",
        "platform": "zalo",
        "contact_name": "Đức Anh",
        "status": "Truy cập 1 giờ trước",
        "day_label": "08:45 Hôm nay",
        "messages": [
            ("KH", "text", "Em ơi anh đổi ý, chuyển từ VF 6 sang VF 7 nhé", "08:45"),
            ("TVV", "text", "Dạ được anh, VF 7 đang có sẵn màu trắng và màu đỏ ạ", "08:47"),
            ("KH", "voice", "0:15", "08:50"),
            ("KH", "text", "Anh lấy màu trắng. Vợ anh đã đi xem xe cùng anh hôm trước rồi", "08:51"),
            ("KH", "text", "Số mới của anh 0912 345 678 nhé", "08:51"),
            ("TVV", "sticker", "", "08:52"),
            ("KH", "text", "Tháng sau anh nhận thưởng thì làm thủ tục trả góp", "08:55"),
        ],
        "expect": {
            "models": ["VF 7"],
            "dropped_models": ["VF 6"],
            "finance": "enough_with_loan",
            "co_decider": "yes_involved",
            "expected_days": 30,
            "events": [],
            "colors": ["Trắng"],
        },
    },
    {
        "id": "s6_messenger_lai_thu",
        "platform": "messenger",
        "contact_name": "Bảo Ngọc",
        "status": "Đang hoạt động",
        "day_label": "19:15",
        "messages": [
            ("TVV", "text", "Chị Ngọc lái thử VF 3 hôm qua thấy thế nào ạ?", "19:15"),
            ("KH", "text", "Hôm qua chị lái thử thấy xe nhỏ gọn, dễ đi phố", "19:20"),
            ("KH", "text", "Nhưng chị vẫn băn khoăn cốp hơi bé", "19:20"),
            ("TVV", "text", "Dạ chị có muốn tham khảo thêm VF 5 không ạ?", "19:22"),
            ("KH", "text", "Ừ em gửi chị xem thử", "19:25"),
        ],
        "expect": {
            "models": ["VF 3", "VF 5"],
            "dropped_models": [],
            "finance": "unknown",
            "co_decider": "unknown",
            "expected_days": None,
            "events": ["test_drive"],
            "colors": [],
        },
    },
]


def transcript_lines(scenario: dict) -> list[tuple[str, str]]:
    """Ground-truth transcript, in the AutoLead RAW format ("TVV: …" / "KH: …"). Stickers are dropped."""
    out = []
    for speaker, kind, text, _ in scenario["messages"]:
        if kind == "text":
            out.append((speaker, text))
        elif kind == "voice":
            out.append((speaker, f"[tin nhắn thoại {text}]"))
    return out


def by_id(sid: str) -> dict | None:
    return next((s for s in SCENARIOS if s["id"] == sid), None)
