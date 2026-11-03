# Dữ liệu nhiều khóa · schema v3

Bản v0.4 cho người dùng chọn K35–K39 trước khi chat (`/api/cohorts` mô tả mức dữ
liệu từng khóa). `programs.json` có thêm `frame_version`, `admission_year`; điều kiện
có `group`, `within_group`, `between_groups`; học phần có nhóm điều kiện được lưu
thành cây `rule` (AND giữa nhóm, OR trong nhóm khi nguồn ghi "hoặc").

Ngành mục tiêu CNTT toàn khóa; phiên bản demo nhận lựa chọn K35–K39. Khả năng
lựa chọn khóa khác với mức đầy đủ dữ liệu. Không suy ra năm tuyển sinh hay phiên
bản chương trình bằng cách cộng/trừ số khóa. Không gán chương trình 2024 cho tất cả.

## Kho và ánh xạ

- `programs.json`: mỗi ánh xạ có `cohort`, `program_id`, `curriculum_id`, `version`,
  `source_id`, `status`, `effective_from`, `effective_to`, `limitations`.
- `VERIFIED_SNAPSHOT` (K37) và `PROVISIONAL_SNAPSHOT` (K36, trích từ ảnh chưa đối
  chiếu QĐ gốc) mới mở danh mục môn; bản tạm thời luôn kèm cảnh báo trong
  `context.message`, `notice` và `evidence_note` của từng trích dẫn.
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
| K35 | Chưa có (khung CNTT-2022, S13) | S03, S13, S14 | Chuẩn hóa danh mục S13, đề cương, quy chế gốc 2022 |
| K36 | 72 mã/82 điều kiện từ ảnh S26 (tạm thời) | S03, S04, S15, S16, S26 | Đối chiếu ảnh với QĐ S15, mã AD, 7 mã tham chiếu thiếu |
| K37 | 99 mã/76 điều kiện, khung 2024 | S01–S04 | Sửa đổi, toàn văn quy định, nghĩa điều kiện mã môn |
| K38 | Chưa có (bản mô tả CNTT-2025) | S05, S12, S17–S19 | QĐ CTĐT gốc 25042105, đề cương, danh mục |
| K39 | Chưa có (CTĐT CNTT-2026) | S06, S07, S20–S22, S24 | Phụ lục II đề cương, danh mục chuẩn hóa |

Mỗi khóa có một đoạn `VERSION-Kxx` (từ tab "Khoa va phien ban" và "Do day du")
để trả lời câu hỏi tổng quát về phiên bản, tổng tín chỉ và mức đầy đủ dữ liệu. S04 chỉ có
metadata, không có ngưỡng điểm TOEIC đã nhập. Giữ thông tin hạn chế của từng nguồn.

## Bổ sung một khóa

1. Đối chiếu văn bản chính thức, điều áp dụng, ngày hiệu lực và các sửa đổi.
2. Thêm nguồn và ánh xạ có bằng chứng; chưa rõ giữ UNVERIFIED.
3. Nhập môn/điều kiện đúng curriculum_id + version; không sửa đè bản khóa khác.
4. Nhập nguyên văn các điều dùng chung một lần, gắn nguồn có danh sách khóa.
5. Chạy `python test.py`, `python scripts/run_smoke.py`; thêm case mã môn giống
   nhưng khác tín chỉ/tiên quyết để kiểm tra cả retrieval và tool.
6. Khởi động lại máy chủ để nạp snapshot mới; cache gắn fingerprint đầy đủ phạm vi.

`scripts/import_catalog.py` đọc workbook CNTT K35–K39 và dựng lại toàn bộ
`data/project` (schema v3); dữ liệu được sửa trong workbook rồi nhập lại, không sửa
tay JSON.

## Toàn văn văn bản (`documents.json`)

`scripts/ingest_documents.py --notices <TLU_Notice_Tool/data>` dựng `data/project/documents.json` từ tệp
đã tải (chữ PDF hoặc bản OCR của `scripts/ocr_gemini.py`). Mỗi văn bản được gán tay vào một nguồn và
danh sách khóa đã xác minh từ chính văn bản: quy chế 2024 (S03, K35–K37), 2025 (S05, K38), 2026 (S06, K39),
TOEIC quốc tế (S04, K36–K37), chuẩn đầu ra ngoại ngữ 2026 (N01, K38) và 2023 (N02, K35–K37), học phí
2026–2027 (N03, K35–K38), học phí K39 (N04).

- Quy chế chia theo Điều (Điều dài tách theo khoản); văn bản bảng chia theo trang. ID ổn định dạng
  `DOC-<nguồn>-<QD|VB|PL|TR>-<D số Điều|P số trang>-<phần>` để đáp án chuẩn không đổi khi dựng lại.
- `verification`: `OCR_UNREVIEWED` (bản chép tự động, phải đối chiếu số liệu) hoặc `TEXT_EXTRACTED`.
- Trang OCR không đọc được hoặc trùng nội dung trang khác (OCR đọc lẫn trang) không vào kho; được ghi
  thành mục thiếu `OCR-<nguồn>` cho đúng các khóa.
- Catalog chỉ nạp đoạn của nguồn áp dụng cho khóa đang chọn; `covered_topics` (hoc_phi, tot_nghiep,
  toeic…) cho planner biết chủ đề nào đã có toàn văn để không trả "chưa có dữ liệu". Câu hỏi đủ điều
  kiện tốt nghiệp của cá nhân, lịch học, lớp mở vẫn bị chặn vì không có dữ liệu cá nhân/thời điểm.
