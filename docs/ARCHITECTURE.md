# Thiết kế demo Flask v0.3

Quyết định 24/10: tạm dừng thu thập nguồn, demo K37 — CNTT-2024; vẫn giữ mục tiêu
nghiên cứu CNTT toàn khóa, giai đoạn đầu K35–K39. Không thay nguồn/nhãn thiếu.

- Excel → courses/conditions/sources JSON; giữ thêm raw_rows, gaps và bản chụp
  từng tab có vị trí ô/dòng. Dữ liệu bảng chưa phải toàn văn PDF.
- Catalog tạo góc nhìn đúng khóa/curriculum/version trước khi lập chỉ mục.
- Retriever: BM25 không dấu, hoặc hybrid embedding + cosine/RRF khi cấu hình API.
- Router quy tắc xác định lookup, conditions, prerequisites hay câu hỏi thiếu dữ liệu.
- Agent: truy xuất lần đầu → gọi công cụ theo mục đích → nếu thiếu bản ghi liên quan,
  truy xuất bổ sung một lần → dừng → diễn đạt/trích đoạn có nguồn.
- `AcademicTools.conditions`: các thành phần điều kiện, quan hệ mã, nhãn trống,
  tham chiếu thiếu; tối đa hai cạnh/25 nút và không lặp chu trình.
- `AcademicTools.prerequisites`: đối chiếu hồ sơ khai báo bằng phép so sánh trong
  code. Chỉ ngưỡng nguồn ghi rõ mới so; mã trần giữ unknown. Không cấp phép đăng ký.
- LLM chỉ nhận đoạn được chọn, không có cả workbook. Với kết quả công cụ, phần
  kết luận máy tính vẫn giữ nguyên sau phần diễn đạt; không cho LLM tự tính số học.
- RAG một lượt không gọi tool; Agent tối đa 2 lượt tổng cộng. Tắt bổ sung mà còn
  thiếu thì nêu rõ, không đệ quy hoặc bù bằng kiến thức ngoài.
- Flask `create_app` mặc định chỉ tải project/K37, không tải sample. DemoEngine
  chặn câu hỏi khóa/ngành/phiên bản khác trước retrieval hoặc API.
- Frontend HTML/CSS/JS có hội thoại, hồ sơ giả lập, source cards, log công cụ và
  số lượt truy xuất. Nhật ký công khai là action log, không phải chain-of-thought.

Không có lookup câu hỏi → đáp án mẫu. Bộ 15 câu nằm ở runner riêng; pipeline
ứng dụng không import runner hoặc các đáp án kỳ vọng. Fixture đa khóa vẫn có
để hồi quy cấu trúc, không được phục vụ qua API demo.

Thiếu: toàn văn/sửa đổi sau 2024, đề cương đúng phiên bản, AD213, đối chiếu PG,
quy đổi/miễn học GE, dữ liệu cá nhân và quy định tốt nghiệp đầy đủ. Không mở lại
các đầu việc thu thập trong lần triển khai này.
