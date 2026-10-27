# Demo Flask · K37 — CNTT-2024

Bản v0.3: tra học phần, đọc điều kiện/chuỗi mã, RAG có dẫn chứng và Agent truy xuất
bổ sung tối đa **một lượt**. Chỉ mở dữ liệu K37 trong giao diện và API mặc định.
Phạm vi nghiên cứu CNTT toàn khóa, giai đoạn đầu K35–K39, vẫn giữ nguyên.

## Chạy trên Windows / VS Code

Cần Python 3.10+. Mở terminal tại thư mục `agentic-rag` vừa giải nén:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe run.py
```

Mở **http://127.0.0.1:8765**. Dừng bằng Ctrl+C. Đổi cổng: `python run.py --port 8888`.
Nếu đã có môi trường Python chứa Flask: `python run.py`.
Trên macOS/Linux: `python3 -m venv .venv`, `.venv/bin/python -m pip install -r requirements.txt`,
`.venv/bin/python run.py`. Máy chủ chạy cục bộ, debug tắt.

## Bật LLM để diễn đạt câu trả lời

Mặc định **offline = trích đoạn + công cụ**, chưa sinh câu trả lời bằng LLM.
Để chạy RAG + LLM, sao chép `.env.example` thành `.env` và điền khóa API:

```dotenv
RAG_PROVIDER=openai
RAG_RETRIEVER=bm25
OPENAI_API_KEY=YOUR_KEY
OPENAI_MODEL=gpt-4.1-mini
```

Khởi động lại server. Model cấu hình được; BM25 không cần embedding/API embedding.
Muốn hybrid thì đặt `RAG_RETRIEVER=hybrid` và `OPENAI_EMBEDDING_MODEL` trong `.env`.
API key chỉ đọc ở backend, không commit. Cần quyền mô hình/quota tương ứng.
Không có khóa API thật trong phiên xây dựng: chỉ kiểm tra adapter bằng mock.
Lỗi API được báo rõ, không ngầm chuyển sang câu trả lời giả.

Router hiện là **quy tắc lập trình**, chọn lookup_course / lookup_conditions hoặc
đối chiếu hồ sơ theo loại câu hỏi; không phải planner học được hay LLM tự chọn tool.
Các câu tương tự đi cùng pipeline, không có bảng câu trả lời viết sẵn theo demo.
LLM nhận những đoạn được chọn, không nhận toàn bộ Excel. ID và quote phải hợp lệ;
kiểm tra này không chứng minh mọi kết luận của LLM đều được nguồn hỗ trợ.
Kết quả kiểm tra điều kiện bằng chương trình được giữ riêng, không nhờ LLM tự tính.

## Nguồn dữ liệu dùng trong bản này

Đọc trực tiếp file `Danh_muc_nguon_va_hoc_phan_CNTT_K37.xlsx` người dùng đính kèm.
SHA-256: `0a8d80f0d04634f1335fd80aa29b6a3756a914b10cb5a195b681e0ee19a5db5c`.

- **99 mã học phần, 100 dòng gốc, 76 thành phần điều kiện, 31 SOURCE_BLANK**.
- File này có **5 tab, 12 nguồn**, không phải bản 9 tab/25 nguồn có SHA-256
  `ff3f55329e47175d8c842dd23c77169d85a0805ae3acb5d6cd4cf52002d4587a` ở mốc 24/10.
- Giữ nguyên bảng nguồn; không truy cập lại website/PDF hay mở rộng tìm nguồn.
- JSON có nguồn S01, trang PDF *được ghi trong bảng*, vị trí `Hoc phan!row` hoặc
  `Dieu kien!row`, phiên bản và nhãn thiếu. Không gọi đây là đọc trực tiếp PDF.
- `data/project/workbook_snapshot.json` giữ các bản ghi và vị trí của cả 5 tab;
  `raw_rows.json` giữ cả hai dòng IT334. Không có tab `Can bo sung` trong file này.
- SOURCE_BLANK không phải “không có tiên quyết”. Mã trần không tự chuyển thành
  đạt môn/điểm ≥4. Thiếu AD213, sửa đổi sau 2024, đối chiếu PG100/PG121, quy đổi GE,
  tổng tín chỉ và điều kiện tốt nghiệp vẫn được giữ là thiếu/chưa rõ.
- Không có lịch mở lớp, sĩ số/học phí hiện thời hoặc hồ sơ thật của người học.

## Công cụ và demo

1. Tra mã/tên: `IT320 tên gì, mấy tín chỉ?`.
2. Đọc điều kiện: `IS330 mấy tín chỉ và điều kiện gì?`.
3. Chuỗi mã: `IT320 yêu cầu môn nào? Môn đó yêu cầu gì?` → IT320 → CS122 → CS121.
4. Nhiều thành phần: `Điều kiện được ghi cho IT499 là gì?`.
5. Đối chiếu hồ sơ giả lập: `Kiểm tra tiên quyết IT499`; nhập tín chỉ/điểm/TBTL ở bên trái.
6. Mở thẻ nguồn để xem trang PDF ghi trong bảng, dòng Excel và phiên bản.
   Tab **Hành động** hiển thị công cụ, truy xuất và điểm dừng; không có suy luận nội bộ.

Chuỗi mã giới hạn hai cạnh tham chiếu, tối đa 25 nút, có kiểm tra chu trình và mã
thiếu. Tối đa hai lần gọi retriever tổng cộng. Nếu vẫn thiếu sau lượt bổ sung thì
nêu giới hạn, không đệ quy thêm. Các chức năng dùng cùng Engine với runner kiểm tra.

## Kiểm tra

Trong môi trường đã cài Flask, chạy:

```bash
python test.py
python scripts/run_demo_checks.py
```

Bản bàn giao đạt **44 bài kiểm tra** và **15/15 câu demo** qua Flask test client.
`scripts/run_demo_checks.py` xuất cả đầu vào, kỳ vọng, câu trả lời, nguồn và trace
vào `docs/demo_results.jsonl`. Đây là kiểm tra demo ban đầu, **không phải thực nghiệm
NCKH chính thức**. Mô tả chi tiết tại [docs/TESTING.md](docs/TESTING.md).

Fixture đa khóa được giữ trong `data/sample` chỉ cho kiểm thử hồi quy; API demo
không cho chọn hoặc nạp fixture đó. `python scripts/run_smoke.py` là 20 case hồi
quy của engine nghiên cứu, tách biệt với 15 câu demo K37.

## Tái nhập đúng workbook này (không bắt buộc khi chạy demo)

```bash
python -m pip install -r requirements-import.txt
python scripts/import_catalog.py data/input/Danh_muc_nguon_va_hoc_phan_CNTT_K37.xlsx --output .runtime/imported-project
```

Importer kiểm tra 99/100/76/31 trước khi xuất; không sửa workbook. Thử nhập ra
thư mục riêng trước khi thay `data/project`. Importer chỉ hỗ trợ schema snapshot
K37 hiện tại; không dùng để suy ra phạm vi cho workbook khóa khác.

## Mã nguồn

| Vị trí | Chức năng |
|---|---|
| `src/agentic_rag/server.py` | Flask factory `create_app`, API, chạy cục bộ |
| `demo.py` | Giới hạn tạm thời K37 — CNTT-2024; chặn khóa/phiên bản khác |
| `catalog.py` | Kho dữ liệu, lọc phạm vi/phiên bản, chunk, trích dẫn |
| `tools.py` | Tra môn; điều kiện và chuỗi; đối chiếu hồ sơ ba trạng thái |
| `planner.py`, `engine.py` | Chọn công cụ, RAG, tối đa một lượt bổ sung |
| `retrieval.py`, `provider.py` | BM25/hybrid; REST LLM và kiểm tra trích dẫn |
| `web/` | HTML/CSS/JS phục vụ qua Flask |
| `docs/` | Thiết kế, provenance, kiểm thử và kết quả 15 câu |

Repository Git giữ lịch sử, chưa gắn remote. Chưa kiểm tra bố cục/thao tác trong
trình duyệt thật và chưa gọi API LLM thật; xem [docs/VERIFICATION.md](docs/VERIFICATION.md).
