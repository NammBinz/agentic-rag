# Kết quả kiểm tra bản Flask K37

Phần bên dưới ghi phiên kiểm tra offline ban đầu. Trạng thái tích hợp và API Gemini
sau đó được cập nhật riêng tại [GEMINI.md](GEMINI.md).

Kiểm tra ban đầu ngày 27/10/2026 trên Windows, Python 3.10.0, Flask 3.1.3,
Chrome 155.0.8059.85 qua Playwright, chế độ headless. Không có `.env` hoặc
`OPENAI_API_KEY` thật trong môi trường kiểm tra. Ứng dụng chạy offline + BM25.

## Kết quả thực chạy

| Nội dung | Kết quả |
|---|---|
| `python test.py` | 44/44 bài đạt |
| `python scripts/run_demo_checks.py` | 15/15 câu qua Flask test client đạt; cập nhật `docs/demo_results.jsonl` |
| `python scripts/run_smoke.py` | 20/20 case hồi quy engine đạt; fixture nghiên cứu, không được mở trong demo |
| JavaScript | `node --check -` nhận nội dung `web/app.js` qua stdin đạt |
| Flask chạy thật | `python run.py`, http://127.0.0.1:8765; debug tắt; health, catalog, conditions và chat hoạt động |
| Phạm vi HTTP mặc định | `demo_only=true`, K37 — CNTT-2024; catalog K38, sample và CNTT-2025 trả HTTP 400; `/.env` trả 404 |
| 15 câu trên UI qua HTTP thật | 14/15 khớp status/nội dung/nguồn của kỳ vọng demo; D08 khác do biểu diễn hồ sơ trống, xem dưới |
| Tương tác bổ sung | 21/21 kiểm tra đạt: khóa phạm vi, câu mẫu, nguồn, hành động, danh mục 99 môn/tìm không dấu/chọn bằng Enter, hồ sơ mẫu, lỗi nhập điểm, lưu/khôi phục/xóa lịch sử, chế độ RAG một lượt, chat và nguồn bằng cảm ứng mô phỏng |
| Bố cục | 9/9 lượt kiểm tra không tràn ngang: trang chào ở 1366×768, 1024×768, 768×1024, 390×844, 360×800; hội thoại chuỗi mã ở 1366×768, 768×1024, 390×844, 360×800; có ảnh desktop 1440×1000 |
| Lỗi trình duyệt | Không ghi nhận lỗi runtime JavaScript, console error hoặc request thất bại trong lần kiểm tra hoàn tất |
| Chuỗi IT320 | IT320 → CS122 → CS121; tab Hành động hiện đúng 2 lượt truy xuất và điểm dừng |
| Metadata nguồn IT320 | COURSE-IT320, S01:2024-08-19, phiên bản 24081902/2024, trang PDF được ghi là 21, `Hoc phan!68` |
| Nạp `.env` | Đã thử bằng cấu hình tạm: đọc provider/model đúng; biến môi trường có sẵn thắng `.env`; thiếu khóa chặn khởi động. Không gọi API |
| Dữ liệu | SHA-256 của toàn bộ 17 tệp trong `data/` trước/sau giống nhau |

Lệnh Node đọc trực tiếp đường dẫn `node --check web/app.js` gặp EPERM khi Node
realpath qua `C:\Users\Admin` trong sandbox. Đọc cùng nội dung qua stdin vượt qua
giới hạn đường dẫn và kiểm tra cú pháp thành công; đây không phải lỗi cú pháp ứng dụng.

## Các điểm phát hiện

1. **D08 khác giữa UI và API khi chưa nhập hồ sơ.** Runner API không gửi `profile`,
   nhận `needs_input`. UI luôn gửi object với `completed=null`, `grades={}`,
   `credits=null`, `average=null`, nên nhận `insufficient_data`. UI vẫn hiển thị
   “Chưa cung cấp tín chỉ tích lũy”, điểm IP406 và điểm TBTL; không kết luận đủ điều kiện.
   Đây là khác biệt hợp đồng trạng thái cần thống nhất nếu yêu cầu UI giống chính xác ca API.
   Chưa sửa mã ứng dụng trong lần kiểm tra này.
2. **D02 trả thêm đoạn ít liên quan khi offline.** Hỏi đầy đủ tên “Phát triển ứng dụng
   với Python có bao nhiêu tín chỉ?” đưa IT320/3 TC lên đầu nhưng kèm SE422, CS318,
   AD215. Demo test vẫn đạt vì chỉ kiểm tra có nội dung và nguồn kỳ vọng, không kiểm tra
   loại bỏ mọi đoạn thừa. Đây là hạn chế độ tập trung của câu trả lời offline.
3. **Health/nhãn LLM không kiểm tra API.** Chúng chỉ đọc cấu hình. Phải gửi câu hỏi thật
   và kiểm tra hành động/token/nguồn mới xác nhận được luồng sinh câu trả lời.

## Bằng chứng lưu tại workspace

- [Log 44 bài kiểm tra](../.runtime/verification/unit.log),
  [log demo](../.runtime/verification/demo.log),
  [log hồi quy engine](../.runtime/verification/smoke.log).
- [Kết quả trình duyệt, payload và response từng câu](../.runtime/verification/browser_results.json),
  [script kiểm tra trình duyệt](../.runtime/verification/browser_checks.py),
  [kết quả HTTP](../.runtime/verification/http_results.json).
- [Ảnh desktop](../.runtime/verification/desktop-welcome.png),
  [chuỗi mã và hành động desktop](../.runtime/verification/desktop-chain.png),
  [mobile](../.runtime/verification/mobile-welcome.png),
  [chat cảm ứng mô phỏng](../.runtime/verification/mobile-touch-chain.png),
  [hộp nguồn trên mobile](../.runtime/verification/mobile-source-dialog.png).
- [Hash trước chạy](../.runtime/verification/data_hashes_before.json) và
  [đối chiếu toàn bộ dữ liệu sau chạy](../.runtime/verification/data_integrity.json).

Các bằng chứng trong `.runtime/` được Git bỏ qua và chỉ có tại workspace này.
Không thay đổi mã nguồn ứng dụng, không chạy importer/migration/tạo lại dữ liệu.
Các thay đổi được theo dõi chỉ gồm tài liệu và kết quả demo có thời gian chạy mới.

## Chưa kiểm chứng

- **LLM/embedding API thật:** chưa kiểm tra xác thực, quyền model/quota, kết nối mạng,
  REST adapter với dịch vụ thật, chất lượng từng claim, latency/token/chi phí thực tế.
  Các kiểm thử provider giả lập không chứng minh những mục này.
- **Hybrid với API thật:** mới có hồi quy cache/embedding bằng provider giả lập;
  chưa tạo chỉ mục embedding thật trong phiên này.
- **Thiết bị/trình duyệt khác:** chưa kiểm tra điện thoại vật lý, Safari/Firefox/Edge,
  bàn phím ảo, screen reader hoặc audit accessibility đầy đủ. Mobile là Chrome giả lập;
  kiểm tra bố cục và xem ảnh không chứng minh toàn bộ UX đều tốt.
- **Nguồn học vụ:** không mở lại website/PDF, chưa đối chiếu trang PDF thực tế hoặc
  sửa đổi sau 2024, không xác nhận lịch mở lớp/học phí/chỗ trống/quyền đăng ký thực tế.
  AD213, PG100/PG121, quy đổi GE, tổng tín chỉ và bộ điều kiện tốt nghiệp vẫn là các
  điểm thiếu/chưa rõ đã ghi trong dữ liệu.
- **Nghiên cứu/triển khai:** không phải thực nghiệm NCKH, so sánh A/B/C, kiểm thử tải,
  kiểm toán bảo mật toàn diện hoặc xác nhận triển khai production.

SHA-256 workbook giữ nguyên:
`0a8d80f0d04634f1335fd80aa29b6a3756a914b10cb5a195b681e0ee19a5db5c`.
Snapshot có 99 mã học phần, 100 dòng gốc, 76 thành phần điều kiện, 31 SOURCE_BLANK,
5 tab và 12 nguồn. Không đồng nhất với bản 9 tab/25 nguồn ở mốc 24/10.

Hướng dẫn bật LLM, khởi động lại và kiểm tra health nằm trong
[README](../README.md#bật-llm-để-diễn-đạt-câu-trả-lời).


## Bổ sung hỗ trợ Gemini

Đã bổ sung adapter Gemini và chạy đạt 56/56 bài, gồm 12 kiểm thử mới bằng HTTP
giả lập. Phần kiểm tra Chrome/offline phía trên là lần kiểm tra ban đầu;
trạng thái cấu hình, kiểm thử giao diện Gemini và API thật được ghi riêng tại
[GEMINI.md](GEMINI.md). Dữ liệu nguồn tiếp tục được giữ nguyên.
