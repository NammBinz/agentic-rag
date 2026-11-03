# Bộ đánh giá K37 — CNTT-2024 (bản nháp)

`eval_k37_draft.jsonl` gồm 177 câu, chia ổn định theo hash ID: khoảng 30% dev, 70% test.
Tạo lại bằng `python scripts/build_eval_set.py --force` (lệnh này ghi đè nhãn đã duyệt; chỉ dùng trước khi duyệt).

| Nhóm | Nguồn nhãn | Mục đích |
|---|---|---|
| lookup, prerequisite, comparison | Sinh từ bảng học phần | Tra một/hai bản ghi, nhiều cách diễn đạt |
| blank_prerequisite | Sinh từ ô SOURCE_BLANK | Không được nói "không có tiên quyết" |
| multi_step_chain | Sinh từ chuỗi X → Y → Z | Truy xuất nhiều bước |
| catalog_count, catalog_list | Đếm trực tiếp từ bảng | **So sánh riêng**: rag và agent dùng chung công cụ thống kê |
| missing_data, out_of_scope | Viết tay | Khả năng nhận biết thiếu dữ liệu và ngoài phạm vi |
| regulation_pending | Viết tay, đối chiếu Quy chế 2024 (S03) | Đã có toàn văn: đáp án theo Điều 10, 13, 14, 15, 18; 2 câu (học vượt, bảo lưu) chấp nhận trả lời hoặc từ chối |
| followup, profile_check | Viết tay | Ngữ cảnh hội thoại và đối chiếu hồ sơ |
| natural_* (41 câu) | Viết tay, đối chiếu bảng | Cách hỏi tự nhiên: viết tắt, không dấu, không mã môn, nhiều ý, chuỗi không dùng chữ "chuỗi", câu tiếp nối mà câu trước không có mã; dùng để phân biệt planner quy tắc và planner LLM |

Nhãn lấy từ dữ liệu hoặc được viết tay, **không lấy từ đầu ra của công cụ hệ thống**.

## Trường nhãn

- `gold_outcome`: `answer` / `abstain` / `refuse` / `needs_input`, hoặc danh sách các kết quả chấp nhận được.
- `gold_required_terms`: mỗi phần tử là danh sách các cách viết tương đương; câu trả lời phải chứa ít nhất một cách viết.
- `gold_forbidden_terms`: cụm từ không được xuất hiện trong câu trả lời.
- `gold_sources`: ID đoạn nguồn phải được trích dẫn.

## Quy trình duyệt

1. Người duyệt (lý tưởng là người khác người viết code) đọc từng câu, đối chiếu với PDF hoặc Excel,
   sửa nhãn nếu cần rồi đổi `review_status` thành `reviewed`.
2. Câu có thể dẫn đến hiểu sai được ghi vào `note`. Có thể thêm câu mới, nhưng phải giữ nguyên ID cũ.
3. Chỉ tinh chỉnh hệ thống trên tập **dev**. Tập test chỉ chạy một lần cho mỗi cấu hình cần báo cáo;
   `run_experiment.py` chặn tập test khi nhãn còn ở trạng thái `draft`.

## Chạy và chấm

```bash
python scripts/run_experiment.py --input data/eval/eval_k37_draft.jsonl --split dev --output .runtime/dev_all.jsonl
python scripts/run_experiment.py --input data/eval/eval_k37_draft.jsonl --split dev --mode agent --no-tools --output .runtime/dev_agent_notools.jsonl
python scripts/score_experiment.py .runtime/dev_all.jsonl --output .runtime/dev_all_score.md
```

Lần chạy bị lỗi 429 thì chạy lại riêng bằng `--rerun-errors <file cũ> --pause 6`; khi nhãn thay đổi, chấm lại bằng `score_experiment.py <file> --gold data/eval/eval_k37_draft.jsonl` mà không gọi API.

`score_experiment.py` chỉ cho điểm proxy (nhóm kết quả, từ khóa, ID nguồn). Độ đúng và tính hỗ trợ của
từng kết luận vẫn phải chấm tay vào trường `human_grading`.
