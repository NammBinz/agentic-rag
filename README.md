# Demo Flask · CNTT K35–K39

Bản v0.4: tra học phần, đọc điều kiện/chuỗi mã, RAG có dẫn chứng và Agent truy xuất
bổ sung tối đa **một lượt**. Người dùng **chọn khóa trước khi chat**; mỗi khóa chỉ dùng
chương trình và nguồn của khóa đó:

| Khóa | Dữ liệu trong demo |
|---|---|
| K37 — CNTT-2024 | 99 mã, 76 điều kiện; khung gốc S01 đã xác minh |
| K36 — CNTT-2023 | 72 mã, 82 điều kiện (có nhóm OR) trích từ ảnh S26; **tạm thời**, chưa đối chiếu QĐ gốc S15 |
| K35, K38, K39 | Chưa có bảng học phần; chỉ tra thông tin phiên bản chương trình và văn bản đúng khóa |

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

```powershell
# Chỉ sao chép lần đầu, khi chưa có .env.
Copy-Item .env.example .env
notepad .env
```

```dotenv
RAG_PROVIDER=openai
RAG_RETRIEVER=bm25
OPENAI_API_KEY=YOUR_KEY
OPENAI_MODEL=gpt-4.1-mini
```

Khởi động lại server. Model cấu hình được; BM25 không cần embedding/API embedding.
Muốn hybrid thì đặt `RAG_RETRIEVER=hybrid` và `OPENAI_EMBEDDING_MODEL` trong `.env`.
API key chỉ đọc ở backend, không commit. Cần quyền mô hình/quota tương ứng.
`python run.py` tự đọc `.env` ở gốc dự án; không cần cài `python-dotenv` hoặc OpenAI SDK.
Biến môi trường có sẵn trong terminal được ưu tiên hơn `.env`. Nếu cấu hình không đổi,
kiểm tra biến `RAG_PROVIDER`, `RAG_RETRIEVER`, `OPENAI_MODEL` và `OPENAI_API_KEY` của tiến trình.
Không đặt chú thích ở cuối dòng giá trị trong `.env`; dùng dòng chú thích riêng.

Sau khi dừng tiến trình cũ và chạy lại `python run.py`, kiểm tra:

```powershell
Invoke-RestMethod http://127.0.0.1:8765/api/health
```

Kỳ vọng `provider=openai`, `retriever=bm25`, `model=gpt-4.1-mini`, `demo_only=true`
và `scope=CNTT K35–K39`. Nhãn “LLM đã bật” và health chỉ xác nhận cấu hình;
chưa chứng minh khóa/quota hoặc kết nối API hoạt động. Hỏi `IT320 tên gì, mấy tín chỉ?`,
mở tab Hành động để kiểm tra bước LLM, token sinh và đối chiếu từng câu với nguồn.
Thiếu khóa làm server không khởi động; lỗi API trong yêu cầu được trả rõ với HTTP 502.

Trong phiên kiểm tra ban đầu ngày 27/10/2026 chưa có `.env` hoặc API key thật: kiểm thử LLM/embedding
dùng provider giả lập, chưa xác nhận REST adapter với dịch vụ thật.
Lỗi API được báo rõ, không ngầm chuyển sang câu trả lời giả.
Các biến đơn giá trong `.env.example` là tùy chọn cho ước tính chi phí; không cần để bật LLM.
Hybrid tạo cache vector trong `.runtime/vectors`, không sửa dữ liệu nguồn; chưa chạy hybrid
với API thật trong phiên này.

Mã hiện dùng Chat Completions và Structured Outputs. Model mặc định được giữ theo dự án;
[OpenAI Docs về GPT-4.1 mini](https://developers.openai.com/api/docs/models/gpt-4.1-mini)
liệt kê hai khả năng này. Quyền truy cập và quota của tài khoản vẫn cần kiểm tra bằng yêu cầu thật.

### Dùng khóa Gemini từ Google AI Studio

Đã có adapter Gemini qua [endpoint tương thích của Google](https://ai.google.dev/gemini-api/docs/openai/).
Trong `.env`, đặt:

```dotenv
RAG_PROVIDER=gemini
RAG_RETRIEVER=bm25
GEMINI_API_KEY=DIEN_KHOA_GEMINI_TAI_DAY
GEMINI_MODEL=gemini-3.8-flash
```

Chỉ dùng khóa thật trong `.env` cục bộ; không gửi khóa qua chat, không commit.
Gemini đọc `GEMINI_API_KEY` và `GEMINI_MODEL`, không đọc hai biến tương ứng của OpenAI.
Model mặc định lấy theo [danh mục model của Google](https://ai.google.dev/gemini-api/docs/models);
quyền model/quota của dự án vẫn phải kiểm tra bằng yêu cầu thật. Có thể đổi `GEMINI_MODEL`
sang model văn bản tương thích mà tài khoản được phép gọi.

Lưu `.env`, dừng server cũ và chạy lại `python run.py`. Health phải hiện
`provider=gemini`, `retriever=bm25`, model đã cấu hình và `demo_only=true`.
Giao diện hiện “LLM đã bật · Gemini · bm25”. Đây chỉ là nhãn cấu hình, không phải
kiểm tra kết nối. Hỏi IT320, mở Hành động và kiểm tra token/nguồn để xác nhận luồng thật.

Bản Gemini chỉ bật BM25, không tạo embedding hay xây lại dữ liệu. `hybrid` với Gemini
bị từ chối rõ ràng. Công cụ, phạm vi K37 — CNTT-2024, giới hạn truy xuất và kiểm tra
ID/quote dùng cùng pipeline hiện tại. Không có fallback sang OpenAI hoặc offline khi API lỗi.
76 bài kiểm tra đạt, gồm 12 bài Gemini dùng HTTP giả lập và 20 bài về thống kê/ngữ cảnh; xem
[trạng thái kiểm chứng Gemini](docs/GEMINI.md) trước khi coi là đã gọi API thật.

Router hiện là **quy tắc lập trình**, chọn lookup_course / lookup_conditions hoặc
đối chiếu hồ sơ theo loại câu hỏi; không phải planner học được hay LLM tự chọn tool.
Các câu tương tự đi cùng pipeline, không có bảng câu trả lời viết sẵn theo demo.
LLM nhận những đoạn được chọn, không nhận toàn bộ Excel. ID và quote phải hợp lệ;
kiểm tra này không chứng minh mọi kết luận của LLM đều được nguồn hỗ trợ.
Kết quả kiểm tra điều kiện bằng chương trình được giữ riêng, không nhờ LLM tự tính.

## Nguồn dữ liệu dùng trong bản này

Đọc trực tiếp file `data/input/CNTT_K35-K39_nguon_phien_ban.xlsx` (bản 02/11/2026, 26 nguồn).
SHA-256: `2799cf5938f8a3b73eaa09903ba3f1274fc9d518cc7b91a8207ab058483d0396`.
Dữ liệu K37 nhập từ workbook này trùng khớp từng trường với bản K37 trước đó
(`Danh_muc_nguon_va_hoc_phan_CNTT_K37.xlsx` vẫn giữ trong `data/input` để đối chiếu).

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

## Thống kê và liệt kê toàn bộ học phần

Câu hỏi “ngành CNTT cần học những môn bắt buộc nào”, “có mấy môn”, “là những môn gì”
được xử lý bằng công cụ đọc toàn bộ danh mục đúng khóa, không nhờ LLM đếm vài đoạn top-k.
Trong bảng K37 — CNTT-2024 có **99 mã học phần phân biệt**, trong đó **45 mã** ghi đúng
quy tắc “Bắt buộc theo mục khung”: 21 Đại cương, 13 Cơ sở khối ngành, 10 Bắt buộc ngành,
1 Tốt nghiệp. Đây không phải số môn mà mọi sinh viên phải học để tốt nghiệp.
CS223/CS224 là chọn 1 trong 2; ngoại ngữ, nhóm lựa chọn và nhánh KLTN/IT486 được ghi riêng.

Câu hỏi tiếp nối giữ cùng bộ lọc trong 6 câu hỏi gần nhất; đổi chủ đề hoặc thiếu ngữ cảnh
thì yêu cầu làm rõ. Câu hỏi này có trạng thái `catalog_summary`, ghi rõ hành động thống kê,
0 lượt retriever và 0 token LLM; mỗi môn liệt kê có dẫn chứng riêng. Cả hai chế độ trên UI
đều dùng báo cáo danh mục cho loại câu hỏi này, nên không coi chúng là ca đối chứng RAG
thuần không dùng công cụ. Các câu hỏi khác giữ pipeline RAG/Agent hiện có.
Chi tiết và bằng chứng tại [docs/CATALOG_REPORTS.md](docs/CATALOG_REPORTS.md).

## Kiểm tra

Trong môi trường đã cài Flask, chạy:

```bash
python test.py
python scripts/run_demo_checks.py
```

Bản bàn giao đạt **76 bài kiểm tra** và **15/15 câu demo** qua Flask test client.
`scripts/run_demo_checks.py` xuất cả đầu vào, kỳ vọng, câu trả lời, nguồn và trace
vào `docs/demo_results.jsonl`. Đây là kiểm tra demo ban đầu, **không phải thực nghiệm
NCKH chính thức**. Mô tả chi tiết tại [docs/TESTING.md](docs/TESTING.md).

Fixture đa khóa được giữ trong `data/sample` chỉ cho kiểm thử hồi quy; API demo
không cho chọn hoặc nạp fixture đó. `python scripts/run_smoke.py` là 20 case hồi
quy của engine nghiên cứu, tách biệt với 15 câu demo K37.

## Tái nhập đúng workbook này (không bắt buộc khi chạy demo)

```bash
python -m pip install -r requirements-import.txt
python scripts/import_catalog.py data/input/CNTT_K35-K39_nguon_phien_ban.xlsx --output .runtime/imported-project
```

Importer kiểm tra mốc từng khóa trước khi xuất (K37: 99/99/76/100/31; K36: 72/72/82/72/17);
không sửa workbook. Thử nhập ra thư mục riêng trước khi thay `data/project`; test
`test_cohorts` xác nhận nhập lại cho ra đúng dữ liệu đã commit.

## Mã nguồn

| Vị trí | Chức năng |
|---|---|
| `src/agentic_rag/server.py` | Flask factory `create_app`, API, chạy cục bộ |
| `demo.py` | Bắt buộc chọn khóa K35–K39; chặn câu hỏi nhắc khóa/ngành/phiên bản khác |
| `catalog.py` | Kho dữ liệu, lọc phạm vi/phiên bản, chunk, trích dẫn |
| `tools.py` | Tra môn; điều kiện và chuỗi; đối chiếu hồ sơ ba trạng thái |
| `planner.py`, `engine.py` | Chọn công cụ, RAG, tối đa một lượt bổ sung |
| `retrieval.py`, `provider.py` | BM25/hybrid; REST LLM và kiểm tra trích dẫn |
| `web/` | HTML/CSS/JS phục vụ qua Flask |
| `docs/` | Thiết kế, provenance, kiểm thử và kết quả 15 câu |

Repository Git giữ lịch sử tại [NammBinz/agentic-rag](https://github.com/NammBinz/agentic-rag). Đã kiểm tra Chrome headless với bố cục
desktop/mobile và thao tác cảm ứng mô phỏng; còn khác biệt D08 giữa hồ sơ trống trên UI
và payload API bỏ trường hồ sơ. Đã gọi Gemini thật thành công cho IT320; hai lần thử
UI sau đó gặp HTTP 503 từ Google. Xem [kiểm chứng ban đầu](docs/VERIFICATION.md) và
[kiểm chứng Gemini](docs/GEMINI.md).
