# Kiểm tra từng chức năng

`python test.py` chạy kiểm tra catalog, tiên quyết, Agent, adapter API giả lập và
HTTP server. `python scripts/run_smoke.py` chạy 14 tình huống có kỳ vọng cụ thể,
lưu cả trích dẫn, trace, metrics vào `.runtime/smoke_results.jsonl`. Không gọi API.

## Demo thủ công

Chạy `python run.py`, mở http://127.0.0.1:8765. Chọn dữ liệu **giả lập** trước
khi dùng các môn PY/CS trong bảng dưới. Bấm “Điền hồ sơ mẫu” để có PY101 đã đạt,
12 tín chỉ, PY101=6, CS101=7, TBTL=7. Nhấn một mã trích dẫn hoặc thẻ nguồn để
xem excerpt, trang, phiên bản. Tab Hành động hiển thị thao tác, không phải suy luận nội bộ.

| Chức năng | Thao tác/đầu vào | Kỳ vọng |
|---|---|---|
| RAG 1 lượt | RAG một lượt; `PY201 có bao nhiêu tín chỉ?` | 1 lượt; nguồn COURSE-PY201; 3 tín chỉ |
| Tra môn | Agentic; `Tra học phần PY201` | lookup_course; tên, tín chỉ, nguồn |
| AND đạt | Agentic; `Kiểm tra tiên quyết PY201`; PY101, 12 TC | satisfied_in_snapshot |
| AND thiếu môn | Xóa PY101; giữ “đã cung cấp đủ danh sách” | not_met_in_snapshot; chỉ rõ PY101 |
| Chưa cung cấp danh sách | Bỏ chọn “đã cung cấp đủ danh sách” | insufficient_data, không coi null là [] |
| OR đạt | `Kiểm tra tiên quyết PY202`; completed=[]; CS101:7 | satisfied_in_snapshot; không bắt buộc cả hai nhánh |
| Điểm/TBTL | `Kiểm tra tiên quyết PY203`; PY101:5, TBTL=6 | đạt đúng ngưỡng; 4.9 không đạt |
| Thiếu khóa | Khóa “chưa cung cấp”; hỏi PY201 | needs_input; không truy xuất |
| Ngoài phạm vi | K38 | out_of_scope; không mượn dữ liệu K37 |
| Truy xuất bổ sung | `python scripts/run_smoke.py` → extra-retrieval | top_k=1, tắt tools; thiếu CS101 → tổng 2 lượt |
| Giới hạn vòng | extra-disabled trong smoke; các test Agent | tắt bổ sung → 1; không có trường hợp >2 |
| Lịch sử | Hỏi, tải lại trang; chọn lại cùng dataset | lịch sử còn; “Xóa hội thoại” xóa kho đang xem |
| Hội thoại tham chiếu | Hỏi IT320 rồi `Kiểm tra tiên quyết môn đó` | resolve IT320 trong tối đa 6 câu gần nhất |
| Nhãn dữ liệu | Đổi project ↔ sample | cảnh báo đổi đúng; hai lịch sử tách riêng |

## Các rào chắn dữ liệu project

Đổi về “CNTT K37 · Có nguồn”. IT320=3 TC, tiên quyết nguồn CS122. Kể cả đã nhập
CS122 đạt 10 điểm, tool vẫn chưa xác nhận đủ điều kiện: nguồn chưa xác minh nghĩa
của mã đơn thuần. CS121 có ô tiên quyết trống: trả unknown, không chuyển thành
“không có tiên quyết”. IT499 với 100 TC, IP406=4, TBTL=7 thỏa điều kiện **trong
snapshot**; với 99 TC không thỏa điều kiện tín chỉ. Không xác nhận quyền đăng ký.

Hỏi học phí/lịch học/ngưỡng TOEIC/đủ điều kiện tốt nghiệp: từ chối kết luận khi
thiếu nguồn. S05–S07/S12 không được đưa vào truy xuất áp dụng K37.

## HTTP API

| Endpoint | Dữ liệu |
|---|---|
| GET `/api/health` | provider, retriever, model đang chạy |
| GET `/api/catalog?dataset=project` | manifest, học phần, nguồn, phần cần xác minh |
| GET `/api/courses?q=IT320&cohort=K37&dataset=project` | lookup theo mã/tên |
| GET `/api/chunks/COURSE-IT320?dataset=project` | excerpt và metadata |
| POST `/api/chat` | question, mode, dataset, cohort, profile |
| POST `/api/prerequisites` | course_code, dataset, cohort, profile |

Ví dụ JSON cho `/api/chat`:

```json
{"question":"Kiểm tra tiên quyết PY201","mode":"agent","dataset":"sample",
 "cohort":"K37","profile":{"completed":["PY101"],"grades":{},"credits":12,"average":7}}
```

`enable_tools:false` và `enable_extra_retrieval:false` là tùy chọn ablation của
Agent. `intent:"prerequisites", target_course:"PY201"` cho phép gọi rõ tác vụ.
Không suy ra bảng điểm từ câu chat. Điểm dùng thang 10; tín chỉ/TBTL là đầu vào
khai báo, không tự tính hoặc quy đổi nếu thiếu quy tắc nguồn.

## Thực nghiệm A/B/C

`data/dev_smoke.jsonl` chỉ có 5 câu phát triển minh họa, không phải bộ 100–120 câu
đã chốt trong đề cương. Chạy trên cùng cấu hình LLM/dữ liệu:

```bash
python scripts/run_experiment.py --input data/dev_smoke.jsonl --output .runtime/dev_abc.jsonl
```

Chế độ offline bỏ qua A (status=unavailable) và B/C là trích xuất. Để thực nghiệm
LLM, cấu hình `.env` như README. Output lưu cấu hình, fingerprint, gold, token,
chi phí nếu đã nhập giá, thời gian, trace và chỗ chấm tay. Không tự chấm semantic
correctness chỉ vì trích dẫn tồn tại. Giá cần cấu hình theo thời điểm chạy; không
dùng số đo mock làm kết quả nghiên cứu. Token lập chỉ mục được báo riêng, nên
lập chỉ mục trước hoặc phân bổ chi phí này rõ ràng để so sánh công bằng.

Tập kiểm tra cuối cần được kiểm tra nguồn/đáp án và đóng băng; câu cần công cụ
có gold_status, ý bắt buộc và nguồn. Hai thành viên chấm chéo theo đề cương,
báo độ đúng/trích dẫn/từ chối, Cohen's kappa và CI ghép cặp. Repo hiện chưa tạo
giả bộ câu hỏi nghiên cứu hoặc số liệu này.
