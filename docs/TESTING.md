# Kiểm tra demo K37

Chạy `python test.py`, sau đó `python scripts/run_demo_checks.py`.
Lệnh thứ hai chạy 15 câu qua **Flask test client**, ghi đầy đủ đầu vào/đầu ra, nguồn,
hành động, kỳ vọng và passed vào `docs/demo_results.jsonl`.
Không dùng kết quả này làm độ chính xác học vụ hay kết quả NCKH chính thức.

| Case | Đầu vào | Kỳ vọng |
|---|---|---|
| D01 | IT320 tên gì, mấy tín chỉ? | Python, 3 TC; S01/trang 21 |
| D02 | Hỏi bằng tên đầy đủ không có mã | Chọn đúng IT320 |
| D03 | IT320 yêu cầu môn nào? Môn đó yêu cầu gì? | CS122 → CS121; hai lượt truy xuất tổng cộng |
| D04 | IS330 mấy tín chỉ và điều kiện gì? | 2 TC; IS224; CNTT-2024 |
| D05 | Điều kiện được ghi cho IT499 | 100 TC, IP406≥4,0, TBTL≥7,0; không phải toàn bộ tốt nghiệp |
| D06 | Kiểm tra IT499, 100 TC, IP406=4, TBTL=7 | satisfied_in_snapshot |
| D07 | Như D06 nhưng 99 TC | not_met_in_snapshot |
| D08 | Kiểm tra IT499, chưa cung cấp hồ sơ | needs_input |
| D09 | CS121 ô trống, đăng ký ngay? | insufficient_data; không coi là miễn tiên quyết |
| D10 | IT320, người dùng khai đã đạt CS122 | Chưa rõ nghĩa mã trần; insufficient_data |
| D11 | Chuỗi AD219 | Giữ AD213 là thiếu, không đổi mã |
| D12 | K38 dùng bảng K37 được không? | out_of_scope, không truy xuất/LLM |
| D13 | Lớp, chỗ trống, học phí hiện tại | Chưa có dữ liệu thời điểm |
| D14 | ZZ999 | Chưa có mã trong snapshot |
| D15 | Đủ điều kiện tốt nghiệp chưa? | Chưa có bộ điều kiện đầy đủ |

## Thử trên giao diện

1. `python run.py`, mở http://127.0.0.1:8765; xác nhận nhãn K37 — CNTT-2024.
2. Hỏi D01/D03/D05; mở nguồn, đối chiếu mã S01, trang PDF ghi trong bảng và dòng Excel.
3. Chọn tab Hành động: có route/retrieve/lookup/stop; truy xuất tối đa 2 lần.
4. Nhập hồ sơ giả lập cho D06/D07; danh sách chưa cung cấp khác với danh sách rỗng.
5. Hỏi D09/D11/D12/D13; phải giữ trạng thái thiếu/ngoài phạm vi.
6. Bật API trong `.env`, khởi động lại. Nhãn engine phải báo LLM đã bật; lỗi API
   hiển thị rõ. Lặp lại D01/D03/D05 và kiểm tra từng claim bằng nguồn, không chỉ ID.
7. Kiểm tra desktop/mobile, nguồn/hành động/cuộn hội thoại. Kiểm tra trình duyệt
   thật và API mạng thật chưa được thực hiện trong phiên xây dựng.

## API đang phục vụ (chỉ K37)

- `GET /api/health`: Flask, provider/retriever, phạm vi.
- `GET /api/catalog`: 99 môn, nguồn áp dụng, context và manifest.
- `GET /api/courses?q=IT320`: tra môn theo mã/tên.
- `GET /api/conditions?q=IT320&depth=2`: điều kiện và chuỗi, không cần hồ sơ.
- `GET /api/chunks/COURSE-IT320`: đoạn được tạo từ bảng, trang PDF và dòng Excel.
- `POST /api/chat`: `question`, `mode` (agent/rag), `profile`, `history` tùy chọn;
  `cohort=K37`, `curriculum_id=CNTT-2024` nếu truyền tường minh.
- `POST /api/prerequisites`: `course_code`, `profile` tùy chọn; đối chiếu điều kiện.

```json
{"question":"Kiểm tra tiên quyết IT499","mode":"agent","cohort":"K37",
 "curriculum_id":"CNTT-2024","profile":{"credits":100,"grades":{"IP406":4},"average":7}}
```

Mọi endpoint dữ liệu từ chối sample/khóa/phiên bản khác. Câu hỏi nhắc K38/K40,
khóa 38 hoặc CNTT-2025 bị chặn trước retriever/LLM. `create_app(demo_only=False)`
chỉ dùng cho kiểm thử engine nghiên cứu; không có nút mở phạm vi này trên giao diện.

Các kiểm thử mock LLM kiểm tra rằng chỉ đoạn được chọn đi tới adapter, tool thực
sự đã chạy, quote/ID phải hợp lệ và token được ghi. Không chứng minh chất lượng
câu trả lời bằng API thật. Fixture hồi quy sample không phải dữ liệu TLU.
