# Kết quả kiểm tra bản Flask K37

Ngày kiểm tra: 27/10/2026. Python 3.12; Flask 3.1.3. Không dùng API key thật.

| Nội dung | Kết quả |
|---|---|
| `python test.py` | 44 bài kiểm tra đạt |
| `python scripts/run_demo_checks.py` | 15/15 câu demo qua Flask test client đạt |
| `python scripts/run_smoke.py` | 20/20 case hồi quy engine nghiên cứu đạt |
| Nhập Excel | 99 mã; 100 raw; 76 thành phần; 31 SOURCE_BLANK; 12 nguồn |
| Công cụ trước LLM | 3 kiểm tra độc lập: chuỗi mã, ngưỡng và AD213/ô trống đạt |
| Phạm vi mặc định Flask | Chỉ K37/CNTT-2024; sample/khóa/phiên bản khác bị chặn |
| Chuỗi IT320 | CS122 → CS121; thực sự gọi truy xuất lượt 2, không vượt giới hạn |
| Mock LLM | Công cụ được chọn; chỉ evidence đã chọn đến adapter; token/nguồn được ghi |
| HTTP cục bộ | Test HTTP qua Werkzeug và khởi chạy run.py ở tiến trình riêng; health/chat/HTML đạt |
| JavaScript | `node --check web/app.js` đạt |
| Bố cục/thao tác trình duyệt thật | Chưa kiểm tra: chưa có browser binary trong môi trường |
| Gọi LLM/embedding API thật | Chưa kiểm tra: chưa cung cấp API key |

SHA-256 Excel vừa đính kèm:
`0a8d80f0d04634f1335fd80aa29b6a3756a914b10cb5a195b681e0ee19a5db5c`.
Bản này có 5 tab/12 nguồn; không đồng nhất với bản 9 tab/25 nguồn trong mốc 24/10.
Không tải/đọc lại website/PDF. Source labels, raw IT334 và các điểm chưa xác minh
được giữ. Trích dẫn về trang PDF là thông tin chép từ bảng, chưa xác minh lại trang.

Đây là kiểm thử phần mềm và demo ban đầu, không phải độ chính xác NCKH, kết quả
so sánh A/B/C hay xác nhận đủ điều kiện đăng ký thực tế. Kết quả từng câu có cả
input, expected, output và action log tại `docs/demo_results.jsonl`.
