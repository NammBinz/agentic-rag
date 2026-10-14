# Kết quả kiểm tra bản bàn giao

Ngày kiểm tra: 14/10/2026. Python 3.12.14; chế độ offline.

| Kiểm tra | Kết quả |
|---|---|
| Unit/integration tests `python test.py` | 35/35 đạt |
| Tình huống mẫu `python scripts/run_smoke.py` | 20/20 đạt |
| HTTP local | Chat, tra môn, tiên quyết, đoạn nguồn và trang HTML trả kết quả đúng |
| RAG một lượt | Ghi nhận 1 lượt, 0 tool; nguồn COURSE-IT320 |
| Agent truy xuất bổ sung | Fixture top_k=1 thực sự gọi search 2 lần; không vượt 2 |
| Dữ liệu | 99 mã; 100 dòng raw; 76 điều kiện; giữ null và mã chưa xác minh |
| Nguồn sai khóa | S05–S07/S12 không xuất hiện trong truy xuất áp dụng K37 |
| Ngưỡng | AND/OR, điểm/tín chỉ/TBTL, giá trị đúng biên và thiếu đầu vào đạt kiểm tra |
| LLM/embedding adapter | Phản hồi mock; quote/ID bịa bị chặn; cache/usage được kiểm tra |
| Nhiều khóa | PY201: K37 3 TC/12 TC tiên quyết; K38 4 TC/24 TC; K39 không mượn môn |
| Quy định chung | Một nguồn TEST-COMMON dùng cả 5 khóa; S04 dùng K36–K37 |
| Hiệu lực/xung đột | Ánh xạ hết hạn, chưa xác minh, trùng phiên bản, thiếu nguồn đều chặn tra môn |
| API phạm vi | Catalog/chunk lọc cohort; thiếu khóa không lấy mặc định K37 |
| JavaScript | `node --check web/app.js` đạt |
| Browser visual / thao tác UI thật | Chưa xác minh: browser kiểm tra không truy cập được localhost; không có browser binary local khả dụng |
| LLM/embedding gọi API thật | Chưa xác minh: không có API key được cung cấp |

Các kết quả trên là kiểm tra phần mềm, không phải kết quả đánh giá nghiên cứu.
Không báo tỷ lệ đúng học vụ, cải thiện so với baseline hoặc chi phí LLM từ các
test giả lập. Giao diện có CSS responsive nhưng bố cục desktop/mobile cần được
xem trên trình duyệt của máy chạy demo. Nguồn hiện là bảng chép/danh mục; việc
nhập toàn văn và xây bộ câu hỏi thật là bước tiếp theo trước thực nghiệm chính thức.
