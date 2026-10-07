# Kết quả kiểm tra bản bàn giao

Ngày kiểm tra: 07/10/2026. Python 3.12.14; chế độ offline.

| Kiểm tra | Kết quả |
|---|---|
| Unit/integration tests `python test.py` | 26/26 đạt |
| Tình huống mẫu `python scripts/run_smoke.py` | 14/14 đạt |
| HTTP local | Chat, tra môn, tiên quyết, đoạn nguồn và trang HTML trả kết quả đúng |
| RAG một lượt | Ghi nhận 1 lượt, 0 tool; nguồn COURSE-IT320 |
| Agent truy xuất bổ sung | Fixture top_k=1 thực sự gọi search 2 lần; không vượt 2 |
| Dữ liệu | 99 mã; 100 dòng raw; 76 điều kiện; giữ null và mã chưa xác minh |
| Nguồn sai khóa | S05–S07/S12 không xuất hiện trong truy xuất áp dụng K37 |
| Ngưỡng | AND/OR, điểm/tín chỉ/TBTL, giá trị đúng biên và thiếu đầu vào đạt kiểm tra |
| LLM/embedding adapter | Phản hồi mock; quote/ID bịa bị chặn; cache/usage được kiểm tra |
| A/B/C exporter | 15 bản ghi offline từ 5 câu minh họa; A được đánh dấu skipped |
| JavaScript | `node --check web/app.js` đạt |
| Browser visual / thao tác UI thật | Chưa xác minh: browser kiểm tra không truy cập được localhost; không có browser binary local khả dụng |
| LLM/embedding gọi API thật | Chưa xác minh: không có API key được cung cấp |

Các kết quả trên là kiểm tra phần mềm, không phải kết quả đánh giá nghiên cứu.
Không báo tỷ lệ đúng học vụ, cải thiện so với baseline hoặc chi phí LLM từ các
test giả lập. Giao diện có CSS responsive nhưng bố cục desktop/mobile cần được
xem trên trình duyệt của máy chạy demo. Nguồn hiện là bảng chép/danh mục; việc
nhập toàn văn và xây bộ câu hỏi thật là bước tiếp theo trước thực nghiệm chính thức.
