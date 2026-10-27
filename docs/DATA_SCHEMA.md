# Dữ liệu nhiều khóa · schema v2

Bản triển khai v0.3 tạm chỉ phục vụ K37/CNTT-2024 qua Flask. Các cấu trúc dưới
đây được giữ để mở rộng sau; không mở chọn khóa khác trong demo.

Ngành mục tiêu CNTT toàn khóa; phiên bản demo nhận lựa chọn K35–K39. Khả năng
lựa chọn khóa khác với mức đầy đủ dữ liệu. Không suy ra năm tuyển sinh hay phiên
bản chương trình bằng cách cộng/trừ số khóa. Không gán chương trình 2024 cho tất cả.

## Kho và ánh xạ

- `programs.json`: mỗi ánh xạ có `cohort`, `program_id`, `curriculum_id`, `version`,
  `source_id`, `status`, `effective_from`, `effective_to`, `limitations`.
- Chỉ `VERIFIED_SNAPSHOT` có căn cứ nguồn đúng phạm vi mới mở danh mục môn.
  Không có ánh xạ hoặc nhiều ánh xạ còn hiệu lực: yêu cầu bổ sung/xác minh; không
  chọn âm thầm. Demo chưa hỗ trợ người dùng chọn nhánh chương trình chuyển đổi.
- `sources.json`: một bản cho mỗi văn bản/phiên bản; `cohorts` là danh sách khóa,
  `programs` là danh sách ngành, `curriculum_ids` rỗng cho nguồn độc lập chương
  trình. Có `scope_verified`, `document_version`, khoảng hiệu lực và URL/vị trí.
- Khoảng hiệu lực dạng YYYY-MM-DD: từ ngày bắt đầu (bao gồm) đến ngày kết thúc
  (không bao gồm), đối chiếu `manifest.snapshot_date`. Ngày trống không đại diện
  việc đã xác minh đủ mọi sửa đổi. Cần ghi giới hạn trong `limitations`.
- `courses.json`: `code`, `program_id`, `curriculum_id`, `version`, `source_id`,
  `chunk_id` (nên duy nhất toàn kho), tên, tín chỉ và tiên quyết nguyên văn.
  Cùng mã môn ở hai phiên bản là hai bản ghi. Trong một phiên bản, mã trùng báo
  xung đột và chặn danh mục, không chọn bản cuối. IT334 đã gộp ở bước nhập bảng;
  hai dòng gốc vẫn nằm trong raw_rows.
- `conditions.json`: cùng định danh ngành/chương trình/phiên bản và `source_id`;
  điều kiện chỉ được dùng nếu khớp danh mục và nguồn. ID có thể tái dùng ở phiên
  bản khác vì công cụ lọc trước đánh giá. Không tự diễn giải mã môn trần/ô trống.
- `manifest.paragraphs`: đoạn văn với `source_id`, `id`, `text`, `kind`, phiên
  bản, trang/mục, mức chứng cứ. Phạm vi kế thừa từ nguồn. Tách các điều có phạm
  vi khác nhau thành nguồn hoặc nhóm nguồn có phạm vi tương ứng.

Một nguồn dùng chung có thể có `cohorts: ["K36", "K37"]` mà không nhân bản text.
Retrieval tạo góc nhìn cho khóa được chọn; trích dẫn vẫn giữ `applicable_cohorts`
và phiên bản gốc. Quy định chung không cần danh mục môn, nhưng phải có phạm vi
đã xác minh. Đoạn mô tả danh mục không thay thế toàn văn điều khoản.

## Trạng thái dữ liệu thật

| Khóa | Danh mục môn | Nguồn có phạm vi đã đối chiếu | Cần bổ sung |
|---|---|---|---|
| K35 | Chưa có | Chưa đủ | Ánh xạ năm tuyển sinh/chương trình, danh mục, quy chế |
| K36 | Chưa có | S04 chung K36–K37 | Ánh xạ chương trình, danh mục, quy chế, toàn văn S04 |
| K37 | 99 mã/76 điều kiện, khung 2024 | S01–S04 | Sửa đổi, toàn văn quy định, nghĩa điều kiện mã môn |
| K38 | Chưa có | S12 quyết định ghi từ K38 | Chương trình tương ứng, phụ lục/đề cương, quy chế |
| K39 | Chưa có | Chưa đủ ánh xạ | Xác minh chương trình, năm tuyển sinh, danh mục, quy chế |

Chưa suy rộng S12 sang K39 hoặc ánh xạ S05/S06 chỉ từ năm tuyển sinh. S04 chỉ có
metadata, không có ngưỡng điểm TOEIC đã nhập. Giữ thông tin hạn chế của từng nguồn.

## Bổ sung một khóa

1. Đối chiếu văn bản chính thức, điều áp dụng, ngày hiệu lực và các sửa đổi.
2. Thêm nguồn và ánh xạ có bằng chứng; chưa rõ giữ UNVERIFIED.
3. Nhập môn/điều kiện đúng curriculum_id + version; không sửa đè bản khóa khác.
4. Nhập nguyên văn các điều dùng chung một lần, gắn nguồn có danh sách khóa.
5. Chạy `python test.py`, `python scripts/run_smoke.py`; thêm case mã môn giống
   nhưng khác tín chỉ/tiên quyết để kiểm tra cả retrieval và tool.
6. Khởi động lại máy chủ để nạp snapshot mới; cache gắn fingerprint đầy đủ phạm vi.

`scripts/import_catalog.py` chỉ dành cho workbook K37 đã có; bước upgrade tự tạo
schema v2 và giữ các khóa còn thiếu. Không chạy lại importer trên kho đã bổ sung
nhiều khóa vì đây là lệnh tái xây dựng snapshot, có thể ghi đè phần đã thêm.
