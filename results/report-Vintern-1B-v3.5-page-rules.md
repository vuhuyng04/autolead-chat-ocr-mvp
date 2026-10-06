# Báo cáo: Vintern-1B-v3.5 · page · trích bằng rules

05/10/2026 23:34

| Ảnh | CER | Dòng đọc được | Đúng người nói | Đúng trường | Giây OCR |
|---|---|---|---|---|---|
| s1_zalo_vf7_vay | 0.161 | 8/10 | 0.00 | 0.57 | 24.4 |
| s2_messenger_vf8_coc | 0.006 | 8/8 | 0.38 | 0.86 | 24.3 |
| s3_zalo_teencode_vf5 | 0.184 | 5/7 | 0.40 | 0.86 | 19.6 |
| s4_messenger_tu_choi | 0.009 | 5/5 | 1.00 | 1.00 | 21.0 |
| s5_zalo_doi_mau_sdt | 0.085 | 5/6 | 0.20 | 0.29 | 18.8 |
| s6_messenger_lai_thu | 0.005 | 5/5 | 0.40 | 1.00 | 27.0 |
| **Trung bình** | **0.075** | | **0.40** | **0.76** | **22.5** |

### s1_zalo_vf7_vay

```
TVV: Em ơi chị hỏi chút về VF 7 nhé
KH: Dạ em chào chị Lan ạ. Chị đang quan tâm bản Eco hay bản Plus ạ?
TVV: Chị thích bản Plus, màu xám
KH: Dạ chị tính khoảng bao giờ lấy xe ạ?
TVV: Chắc tầm 3 tháng nữa em
KH: Về tài chính mình có cần hỗ trợ vay không chị?
TVV: Có em, chị muốn vay khoảng 70% để chị bàn thêm với chồng đã
KH: Dạ vâng, cuối tuần anh chị qua showroom lái thử nhé
TVV: Ok em, thứ 7 chị qua
```

Trường sai: {'models': {'expected': ['VF 7'], 'got': [], 'ok': False}, 'expected_days': {'expected': 90, 'got': None, 'ok': False}, 'colors': {'expected': ['Xám'], 'got': [], 'ok': False}}

Bị loại ở bước kiểm: không

### s2_messenger_vf8_coc

```
TVV: Shop cho mình hỏi VF 8 với VF 9 khác nhau nhiều không
KH: Dạ VF 9 rộng hơn, có 7 chỗ. Nhà mình đi mấy người anh?
TVV: 4 người thôi, VF 8 là đủ rồi
KH: Mình trả thẳng, không vay
TVV: Dạ anh tự quyết hay cần hỏi ý gia đình ạ?
KH: Mình tự quyết
TVV: Chiều nay mình chuyển cọc VF 8 màu đen nhé
KH: Dạ em đã nhận được tiền cọc 20 triệu rồi ạ, em cảm ơn anh
```

Trường sai: {'colors': {'expected': ['Đen'], 'got': [], 'ok': False}}

Bị loại ở bước kiểm: không

### s3_zalo_teencode_vf5

```
TVV: a ơi vf5 lăn bánh hn bn vậy a
KH: Dạ VF 5 lần bánh Hà Nội khoảng 5xx triệu anh ạ, em gửi bảng giá chi tiết nhé
TVV: ok a.e chưa đủ tiền, đang gom thêm
KH: chắc cuối năm mới mua dc
TVV: Dạ anh có lo gì về xe điện không ạ?
KH: e sợ sạc ở chung cư khó để e hỏi bố mẹ đã
TVV: e sợ sạc ở chung cư khó để e hỏi bố mẹ đã
```

Trường sai: {'finance': {'expected': 'insufficient', 'got': 'unknown', 'ok': False}}

Bị loại ở bước kiểm: không

### s4_messenger_tu_choi

```
TVV: Thu Hà ơi, bên em đang có ưu đãi VF 6 tháng này ạ
KH: Thôi em ơi, nhà chị chưa có nhu cầu nữa
TVV: Dạ chị có muốn em giữ thông tin mẫu VF 6 không ạ?
KH: Không cần đâu em, chị không quan tâm VF 6 nữa
TVV: Dạ vâng, khi nào cần chị nhắn em nhé
```

Trường sai: không

Bị loại ở bước kiểm: không

### s5_zalo_doi_mau_sdt

```
TVV: Em ơi anh đổi ý, chuyển từ VF 6 sang VF 7 nhé
KH: Da được anh, VF 7 đang có sẵn màu trắng và màu đỏ ạ
TVV: Anh lấy màu trắng. Vợ anh đã đi xem xe cùng anh hôm trước rồi
KH: Số mới của anh 0912 345 678 nhé
TVV: Tháng sau anh nhận thưởng thì làm thủ tục trả góp
```

Trường sai: {'dropped_models': {'expected': ['VF 6'], 'got': [], 'ok': False}, 'finance': {'expected': 'enough_with_loan', 'got': 'enough_cash', 'ok': False}, 'co_decider': {'expected': 'yes_involved', 'got': 'unknown', 'ok': False}, 'expected_days': {'expected': 30, 'got': None, 'ok': False}, 'colors': {'expected': ['Trắng'], 'got': ['Trắng', 'Đỏ'], 'ok': False}}

Bị loại ở bước kiểm: không

### s6_messenger_lai_thu

```
TVV: Chị Ngọc lái thử VF 3 hôm qua thấy thế nào ạ?
KH: Hôm qua chị lái thử thấy xe nhỏ gọn, dễ đi phố.
TVV: Nhưng chị vẫn băn khoăn cốp hơi bé
KH: Dạ chị có muốn tham khảo thêm VF 5 không ạ?
TVV: Ừ em gửi chị xem thử
```

Trường sai: không

Bị loại ở bước kiểm: không
