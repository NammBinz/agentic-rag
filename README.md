# Trợ lý Agentic RAG · CNTT K35–K39

Prototype v0.2 theo phạm vi CNTT toàn khóa; triển khai lựa chọn K35–K39.
Giữ dữ liệu K37 có nguồn từ danh mục ngày 07/10/2026.
Một repository chứa RAG một lượt có dẫn nguồn, công cụ học phần/tiên quyết,
Agent bổ sung tối đa một lượt, API và giao diện demo.

## Chạy nhanh (Windows / macOS / Linux)

Cần **Python 3.10+**. Giải nén, mở terminal ở thư mục `agentic-rag`:

```bash
python run.py
```

Mở **http://127.0.0.1:8765**. Linux có thể dùng `python3`. Không cần pip, Node,
GPU hoặc API key để chạy bản trích xuất offline. Nhấn Ctrl+C để dừng. Đổi cổng:
`python run.py --port 8888`. Máy chủ mặc định chỉ phục vụ trên máy cá nhân.

## Kiểm tra

```bash
python test.py
python scripts/run_smoke.py
```

Các kịch bản nhập trên UI, đầu vào/kết quả và endpoint được ghi trong
[docs/TESTING.md](docs/TESTING.md). Mô tả thiết kế và quyết định dữ liệu nằm ở
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Chọn khóa và phiên bản

Mở web, chọn **K35–K39** trước khi hỏi. Mặc định chưa chọn khóa để tránh áp dụng nhầm.
Retrieval, API tra môn, kiểm tra tiên quyết và xem trích dẫn cùng dùng phạm vi đã chọn.
Đổi khóa sẽ chuyển lịch sử, xóa hồ sơ đang nhập và danh mục đang xem.

| Kho | Khóa | Trạng thái |
|---|---|---|
| Project | K37 | 99 mã môn / 76 điều kiện của khung gốc 2024; chưa đủ sửa đổi và toàn văn |
| Project | K36 | Có phạm vi nguồn chung S04 (TOEIC K36–K37); chưa có danh mục môn |
| Project | K38 | Có danh mục nguồn S12 ghi từ K38; chưa nhập đề cương chi tiết và ánh xạ chương trình |
| Project | K35, K39 | Chưa đủ ánh xạ chương trình và dữ liệu môn; không lấy K37 thay thế |
| Sample | K35–K37 | Chương trình giả lập sample-v1, PY201=3 TC, tối thiểu 12 TC |
| Sample | K38 | sample-v2, PY201=4 TC, tối thiểu 24 TC |
| Sample | K39 | Thiếu chương trình; vẫn tra được quy định giả lập dùng chung |

Văn bản dùng chung lưu **một bản**, khai báo danh sách khóa áp dụng. Trích dẫn có
khóa được chọn, mã chương trình, phiên bản chương trình, phiên bản văn bản và các
khóa áp dụng. Nguồn chưa xác minh phạm vi, hết hiệu lực hoặc không khớp chương
trình bị loại trước truy xuất. Chi tiết thêm dữ liệu: [docs/DATA_SCHEMA.md](docs/DATA_SCHEMA.md).

## Bật LLM và embedding

Sao chép `.env.example` thành `.env` (Windows: `Copy-Item .env.example .env`;
macOS/Linux: `cp .env.example .env`), rồi nhập:

```dotenv
RAG_PROVIDER=openai
RAG_RETRIEVER=hybrid
OPENAI_API_KEY=YOUR_KEY
OPENAI_MODEL=gpt-4.1-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
```

Khởi động lại server. Khóa chỉ được đọc ở backend và bị Git bỏ qua. ChatGPT Plus
không cung cấp khóa API cho repo này. `hybrid` dùng BM25 + embedding cosine và
RRF; vector cache gắn với fingerprint dữ liệu/mô hình. `bm25` vẫn dùng LLM nếu
provider=openai. Giao diện cho biết engine đang dùng; lỗi API được báo rõ, không
chuyển chế độ âm thầm. Cần có Internet/quyền mô hình/quota. Không có khóa API
trong phiên xây dựng nên tích hợp mạng thật chưa được xác minh; adapter được
kiểm thử với phản hồi giả lập.

Offline là demo **trích đoạn**, chưa phải kết quả sinh câu trả lời bằng LLM. Agent
hiện dùng router theo quy tắc và công cụ lập trình; không huấn luyện planner.
Kết quả tiên quyết được định dạng trực tiếp từ tool để giữ nguyên phép kiểm tra.

Tài liệu API tham chiếu: [Chat Completions](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create),
[Embeddings](https://developers.openai.com/api/reference/resources/embeddings/methods/create).
Quote được kiểm tra có trong excerpt, nhưng kiểm tra tự động này không chứng
minh kết luận của LLM được nguồn hỗ trợ; phần đó cần chấm theo đáp án chuẩn.

## Dữ liệu và phạm vi trả lời

- `data/project`: 99 mã học phần, 100 dòng nguồn, 76 điều kiện; giữ nguồn/trang,
  phiên bản, khóa, hiệu lực và phần thiếu. IT334 trùng vẫn có hai dòng raw.
- `data/sample`: 12 bản ghi thuộc 2 phiên bản chương trình + một quy định chung **hoàn toàn giả lập**; có AND/OR,
  điểm/tín chỉ/TBTL và trường hợp thiếu dữ liệu để kiểm tra.
- Hiện trích dẫn tới bản chép/bảng chuẩn hóa và danh mục, kèm liên kết PDF gốc;
  **chưa nhập toàn văn** các quy chế, thông báo và quyết định.
- Ô tiên quyết trống giữ null; mã môn đơn thuần không được tự diễn giải thành
  đạt môn/điểm >=4. Trả “chưa đủ căn cứ” nếu chưa xác minh quy tắc.
- Dữ liệu thật hiện chỉ đủ danh mục học phần snapshot khung gốc K37; chưa xác minh đầy đủ sửa đổi sau
  2024. Không xác nhận quyền đăng ký, miễn học hoặc đủ điều kiện tốt nghiệp.
- Không nối tài khoản, đăng ký học hay bảng điểm thật. Lịch sử lưu ở trình duyệt;
  chỉ dùng hồ sơ giả lập. Có nút xóa; lịch sử tách theo kho dữ liệu và khóa.

Để tái nhập bảng nguồn (chỉ bước này cần `openpyxl`):

```bash
python -m pip install openpyxl
python scripts/import_catalog.py PATH_TO_WORKBOOK.xlsx --output data/project
```

Không đưa đề cương có thông tin cá nhân vào repo. Manifest giữ tên/hash bản nguồn;
JSON giữ cả nội dung chuẩn hóa và dấu vết các trường chưa xác minh. Sau khi dữ
liệu thay đổi phải đối chiếu nguồn, chạy kiểm tra và cập nhật số lượng kỳ vọng.

## Cấu trúc mã

| File/thư mục | Vai trò |
|---|---|
| `src/agentic_rag/catalog.py` | Kho dữ liệu, chunk và trích dẫn |
| `retrieval.py` | BM25, vector cosine, hợp nhất RRF |
| `tools.py` | Tra môn; tiên quyết ba trạng thái AND/OR |
| `planner.py` | Định tuyến, nhận diện chứng cứ thiếu |
| `engine.py` | A/B/C; kiểm soát 1 hoặc 2 lượt; câu trả lời/metrics |
| `provider.py` | REST API LLM/embedding, usage |
| `server.py` | API + phục vụ giao diện local |
| `web/` | Hội thoại, hồ sơ mẫu, lịch sử, nguồn, nhật ký |
| `scripts/` | Nhập dữ liệu, fixture, smoke, xuất thực nghiệm |
| `tests/` | Kiểm tra đơn vị và end-to-end HTTP |

## Repository

Bản bàn giao kèm repository Git nhánh `main`, có các commit theo thứ tự chức
năng. Chưa gắn remote GitHub; có thể tạo repo trống và đưa lên sau khi nhận:

```bash
git remote add origin YOUR_REPOSITORY_URL
git push -u origin main
```

Không commit `.env`, vector cache hoặc log thực nghiệm. Bản này là prototype
nghiên cứu; công việc tiếp theo là nhập toàn văn đã kiểm chứng và xây bộ đánh giá
100–120 câu thật, không dùng smoke tests để công bố tỷ lệ đúng của hệ thống.
