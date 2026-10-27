# Sửa thống kê và ngữ cảnh câu hỏi học phần

Ngày 27/10/2026. Giữ K37 — CNTT-2024, toàn bộ dữ liệu nguồn và cấu hình Gemini hiện có.

## Vấn đề và cách sửa

Câu “ngành công nghệ thông tin cần học những môn bắt buộc nào” trước đây đi vào QA
thông thường, chỉ lấy tối đa 4 đoạn rồi cho LLM diễn đạt. Kiểm tra ID/quote chỉ xác nhận
đoạn trích tồn tại, không chứng minh kết luận về tổng số/danh sách đầy đủ. Vì thế có thể
hiện “4 môn của K37” với nguồn EC102 dù snapshot có 99 mã. Các câu hỏi tiếp nối trước
đây chỉ nối lại mã môn qua “môn đó”, không giữ bộ lọc danh mục.

Đã thêm router câu hỏi danh mục, công cụ `catalog_summary`, định dạng câu trả lời bằng
kết quả trực tiếp và giải quyết các câu hỏi tiếp nối đếm/liệt kê. Không gửi danh mục cho
LLM, không đếm số chunk. Các câu mới đọc chính catalog đã lọc khóa, chương trình và phiên bản.
Nhận diện câu hỏi bằng quy tắc, không phải hiểu mọi cách diễn đạt tự nhiên.

## Cách đọc số liệu

| Tập trong bảng K37 | Số mã |
|---|---:|
| Toàn bộ danh mục chuẩn hóa | 99 |
| Ghi đúng “Bắt buộc theo mục khung” | 45 |
| Đại cương, theo quy tắc bắt buộc trên | 21 |
| Cơ sở khối ngành, theo quy tắc bắt buộc trên | 13 |
| Bắt buộc ngành, theo quy tắc bắt buộc trên | 10 |
| Tốt nghiệp, theo quy tắc bắt buộc trên | 1 |

Nhóm có tên “Bắt buộc ngành” còn có CS223/CS224 với quy tắc chọn 1 trong 2; không gán
cả hai thành bắt buộc riêng lẻ. Các cặp ngoại ngữ, nhóm lựa chọn ngành/AD và nhánh
IT499/IT486 vẫn được ghi riêng theo nguồn. Không suy ra tổng môn hoặc tổng tín chỉ mà
mọi sinh viên phải hoàn thành. IT334 vẫn chỉ tính một mã dù có hai dòng gốc.

Danh sách mỗi môn có citation riêng. Bằng chứng của báo cáo bao gồm các bản ghi dùng
để tính danh mục và các nhóm lựa chọn; số thẻ nguồn không phải số môn bắt buộc.

## Ngữ cảnh và giới hạn

- “có mấy môn” và “là những môn gì” giữ bộ lọc của câu danh mục gần nhất, qua cả chuỗi
  câu hỏi tiếp nối trong giới hạn 6 câu lịch sử hiện có.
- Câu hỏi có bộ lọc mới được ưu tiên. Đổi chủ đề, nhắc khóa/phiên bản khác trong lịch sử
  hoặc thiếu chủ đề thì hỏi làm rõ; không mượn tổng từ vài đoạn truy xuất.
- Cả Agent và RAG trên UI dùng công cụ khi là câu hỏi báo cáo danh mục. Không dùng các
  ca này làm đối chứng RAG thuần không công cụ trong thực nghiệm nghiên cứu.
- Khi tắt công cụ, báo thiếu căn cứ thay vì đoán từ top-k. Học phí, lịch học và điều kiện
  tốt nghiệp vẫn đi qua cổng dữ liệu thiếu hiện có.
- Bổ sung chỉ dẫn LLM không coi tập evidence là toàn bộ danh mục, không gắn một citation
  cho nhiều môn không nằm trong đoạn. Chỉ dẫn này không chứng minh mọi claim khác đều đúng.

## Kiểm chứng

- `python -X utf8 test.py`: **76/76 đạt**, gồm 20 hồi quy mới cho danh mục/ngữ cảnh.
- `python scripts/run_demo_checks.py`: **15/15** ca cũ đạt.
- `python scripts/run_smoke.py`: **20/20** ca engine cũ đạt, fixture không mở trong demo.
- Cú pháp JS qua `node --check -`: đạt.
- Chrome headless trên Flask thật: đúng ba câu trong ảnh đều trả `catalog_summary`,
  cùng count 45, tool_calls=1, retrieval_rounds=0 và prompt/completion token=0.
  Kiểm tra nội dung hiển thị khớp JSON, nhãn báo cáo, action thống kê, nguồn CS123 tại
  `Hoc phan!43`, mobile 390px không tràn ngang, và thiếu lịch sử thì yêu cầu làm rõ.
  Không có lỗi runtime JS hoặc request trình duyệt ra ngoài localhost trong phép thử.
- Hash toàn bộ **17 tệp trong data/** giống baseline trước khi sửa. Không chạy importer,
  migration, tạo lại workbook/index hoặc gọi Gemini cho các câu thống kê này.

Bằng chứng cục bộ được Git bỏ qua:
[log unit](../.runtime/catalog-verification/unit.log),
[đầu vào/đầu ra ba câu UI](../.runtime/catalog-verification/browser_results.json),
[ảnh đếm desktop](../.runtime/catalog-verification/count-desktop.png),
[ảnh liệt kê mobile](../.runtime/catalog-verification/list-mobile.png),
[ảnh nguồn](../.runtime/catalog-verification/source-dialog.png),
[hash dữ liệu](../.runtime/catalog-verification/data_integrity.json).

Các câu trả lời sai cũ đã lưu trong localStorage không được viết lại. Tải lại trang và
hỏi lại; có thể dùng nút Xóa hội thoại để bỏ kết quả cũ. Chưa chứng minh chất lượng với
mọi cách hỏi, chất lượng ngữ nghĩa LLM trên tác vụ khác hoặc tính đầy đủ học vụ sau 2024.
