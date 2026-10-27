# Gemini cho demo K37 — CNTT-2024

Cập nhật ngày 27/10/2026 tại `D:\Nghiên cứu khoa học\Agentic RAG\agentic-rag`.

## Cấu hình đang dùng

Đã nạp khóa Gemini người dùng lưu trong `.env`, không hiển thị hoặc commit khóa.
`RAG_PROVIDER=gemini`, `RAG_RETRIEVER=bm25`, `GEMINI_MODEL=gemini-3.5-flash-lite`.
Đã đổi theo yêu cầu người dùng: 3.8 Flash thử trước bị timeout, sau đó 3.5 Flash-Lite trả lời IT320 thành công.
Model mặc định khi không cấu hình là `gemini-3.8-flash` theo tài liệu Google đã đối chiếu.

Flask chạy cục bộ tại http://127.0.0.1:8765, debug tắt, phạm vi K37 — CNTT-2024.
PID của tiến trình được khởi động trong phiên này là **13492**, lưu tại
`.runtime/gemini-verification/flask.pid`. Có thể dừng tiến trình này bằng
`Stop-Process -Id 13492`. Sau khi đổi `.env`, dừng server cũ rồi chạy `python run.py`.
Health xác nhận provider, model, BM25 và demo_only; không xác nhận dịch vụ đang sẵn sàng.

## Thay đổi

- Thêm adapter REST Gemini qua endpoint tương thích do Google cung cấp; không cần SDK mới.
- Gemini đọc `GEMINI_API_KEY` / `GEMINI_MODEL`, tách biệt với biến OpenAI.
- Chỉ bật BM25; không tạo embedding/index, không sửa `data/`.
- Giữ cùng công cụ, kiểm tra ID/quote, giới hạn 2 lượt truy xuất và phạm vi demo.
- Health hiện đúng model Gemini; giao diện ghi rõ Gemini.
- Ghi bước `generate` ngay khi gọi provider, gồm cả nhánh tra cứu đơn giản; mỗi lần sinh ghi một bước.
- Phân biệt lỗi 429 về hạn mức và lỗi 5xx về dịch vụ; lỗi trả HTTP 502 cho UI,
  không ngầm thay bằng câu trả lời OpenAI/offline và không ghi khóa vào lỗi.

## Kết quả thực chạy

| Kiểm tra | Kết quả |
|---|---|
| `python -X utf8 test.py` | 56/56 đạt, gồm 12 bài Gemini dùng HTTP giả lập |
| `python scripts/run_demo_checks.py` | 15/15 đạt ở chế độ offline |
| Cú pháp `web/app.js` | `node --check -` qua stdin đạt |
| Khóa/kết nối thật | Thông điệp kỹ thuật không chứa học phần nhận HTTP 200; giới hạn 128 token của phép thử này làm JSON bị cắt, không coi là kiểm tra JSON hoàn chỉnh |
| RAG + Gemini thật qua Flask test client | Câu “IT320 tên gì, mấy tín chỉ?” nhận HTTP 200, status answered, nguồn COURSE-IT320; 851 prompt token, 72 completion token, khoảng 6,22 giây |
| Đối chiếu câu trả lời thật | “Môn học IT320 có tên là Phát triển ứng dụng với Python và có 3 tín chỉ.” khớp bản ghi K37; không suy rộng thành chất lượng mọi câu hỏi |
| UI với Flask thật | Hai lần cùng câu IT320 nhận lỗi upstream Google HTTP 503, Flask trả 502; chưa hoàn tất nhánh trả lời thành công trên UI bằng API thật |
| UI với provider Gemini giả lập | 7/7 đạt: nhãn/phạm vi, câu trả lời/token, action generate một lần, metadata nguồn, mobile không tràn ngang, lỗi 503 hiện rõ không fallback, không lỗi JS runtime |
| Toàn vẹn nguồn | SHA-256 của toàn bộ 17 tệp trong `data/` trước/sau giống nhau |

Trong phiên tích hợp ban đầu không tự đổi model sau lần thử lại 503. Người dùng sau đó yêu cầu đổi model; kết quả ở phần cập nhật dưới đây.
Lần gọi RAG thật diễn ra sau khi người dùng đồng ý gửi câu hỏi IT320 và các đoạn nguồn
được chọn tới Google Gemini. Không gửi toàn bộ workbook hoặc hồ sơ sinh viên thật.

## Bằng chứng

- [Phản hồi IT320 thật thành công](../.runtime/gemini-verification/live_first.json).
- [Lần UI đầu gặp 503](../.runtime/gemini-verification/live_ui_results.json),
  [lần thử lại gặp 503](../.runtime/gemini-verification/live_ui_results_final.json).
- [Kết quả UI giả lập](../.runtime/gemini-verification/ui_mock_results.json),
  [ảnh desktop giả lập](../.runtime/gemini-verification/gemini-ui-mock-desktop.png),
  [ảnh mobile giả lập](../.runtime/gemini-verification/gemini-ui-mock-mobile.png),
  [ảnh lỗi giả lập](../.runtime/gemini-verification/gemini-ui-mock-error.png).
- [Log 56 bài kiểm tra](../.runtime/gemini-verification/unit.log),
  [log 15 câu demo](../.runtime/gemini-verification/demo.log),
  [hash nguồn](../.runtime/gemini-verification/data_integrity.json).

Bằng chứng `.runtime/` được Git bỏ qua, chỉ có ở workspace này.

## Chưa kiểm chứng

Độ ổn định API/quota theo thời gian, chất lượng trên bộ câu hỏi đầy đủ, chi phí thực tế,
Gemini embedding/hybrid, thiết bị mobile vật lý và các model khác chưa được kiểm chứng.
Chuỗi tiên quyết với Gemini thật chưa thực hiện: bộ duyệt tự động từ chối mở rộng
payload nguồn ngoài câu IT320 đã chấp thuận; chuỗi vẫn có kiểm thử offline/giả lập.
OpenAI API thật và việc tái đối chiếu PDF/sửa đổi học vụ sau 2024 vẫn chưa kiểm chứng.

Hướng dẫn cấu hình trong [README](../README.md#dùng-khóa-gemini-từ-google-ai-studio).
Tài liệu kỹ thuật đã đối chiếu:
[Google API compatibility](https://ai.google.dev/gemini-api/docs/openai/),
[danh mục model](https://ai.google.dev/gemini-api/docs/models).


## Cập nhật đổi model theo yêu cầu người dùng

- Chỉ đổi `GEMINI_MODEL` trong `.env`, giữ nguyên khóa, BM25 và phạm vi K37 — CNTT-2024.
- Phát hiện hai Flask của cùng dự án cùng nghe cổng 8765 (PID 25412 và 5704). Đã xác minh cwd/command của cả hai, dừng và thay bằng một tiến trình.
- `gemini-3.8-flash`: health đúng model nhưng câu IT320 hết thời gian chờ sau khoảng 45,17 giây.
- `gemini-3.5-flash-lite`: health đúng model; cùng câu IT320 nhận HTTP 200, answered, khoảng **1,53 giây**, 851 prompt token / 104 completion token.
- Câu trả lời: “Môn học IT320 có tên là Phát triển ứng dụng với Python và có số tín chỉ là 3.”, nguồn COURSE-IT320; khớp bản ghi.
- Cấu hình cuối là **gemini-3.5-flash-lite**; PID Flask hiện tại **13492**. Toàn bộ 17 tệp `data/` giữ nguyên hash.
- Bằng chứng: [thử 3.8](../.runtime/gemini-verification/model38_check.json), [thử Flash-Lite](../.runtime/gemini-verification/model_lite_check.json).
- Mới kiểm chứng một câu thật trên model mới; chưa chứng minh độ ổn định hoặc chất lượng toàn bộ câu hỏi.

Model đã đối chiếu với [tài liệu Google về 3.5 Flash-Lite](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite).
