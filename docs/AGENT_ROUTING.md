# Luồng dữ liệu và thiết kế đa agent (đề xuất)

Tài liệu mô tả đường đi của dữ liệu từ câu hỏi của sinh viên đến câu trả lời, và hai hướng chia
**agent điều phối (Orchestrator)** thành các **agent con**:

1. **Theo khóa** — mỗi khóa K35…K39 một agent.
2. **Theo cụm vấn đề** — 10 agent chuyên đề (điểm, kế hoạch học tập, quy chế…).

Cuối tài liệu là so sánh hai hướng và đề xuất kết hợp. Các khối Mermaid hiển thị trực tiếp trên
GitHub, VS Code (Markdown Preview Mermaid) hoặc https://mermaid.live.

> Trạng thái dữ liệu dùng trong sơ đồ là trạng thái hiện tại của kho (11/2026): K37 đã xác minh,
> K36 tạm thời (trích từ ảnh), K35/K38/K39 mới có thông tin phiên bản và toàn văn quy chế.

---

## 1. Luồng tổng quát: từ câu hỏi đến câu trả lời

```mermaid
flowchart TD
    U(["👤 Sinh viên"]) -->|"1. Chọn khóa K35–K39"| UI["Giao diện web<br/>(màn hình chọn khóa)"]
    U -->|"2. Gõ câu hỏi"| UI
    UI -->|"POST /api/chat<br/>question + cohort + history + profile"| API["Flask API"]

    subgraph G["① Hàng rào phạm vi — chạy TRƯỚC mọi lần gọi LLM"]
        API --> V{"Đã chọn khóa?"}
        V -- "Chưa" --> ASK["Hỏi lại: bạn thuộc khóa nào?"]
        V -- "Rồi" --> SC{"Câu hỏi nhắc khóa / ngành /<br/>phiên bản khác?"}
        SC -- "Có" --> OOS["Từ chối: ngoài phạm vi<br/>(gợi ý đổi khóa)"]
        SC -- "Không" --> MD{"Chủ đề chưa có dữ liệu?<br/>(lịch học, lớp mở, đủ ĐK<br/>tốt nghiệp của cá nhân…)"}
        MD -- "Có" --> GAP["Báo thiếu dữ liệu<br/>+ dẫn mục cần bổ sung"]
    end

    MD -- "Không" --> ORC

    subgraph O["② Agent điều phối (Orchestrator)"]
        ORC["Hiểu câu hỏi<br/>• gộp ngữ cảnh hội thoại ('môn đó')<br/>• tách câu hỏi nhiều ý"] --> RT{"Định tuyến"}
        RT -->|"1 ý"| SA1["Agent con A"]
        RT -->|"nhiều ý"| SA2["Agent con A + B<br/>(chạy song song)"]
    end

    subgraph T["③ Agent con: lấy bằng chứng (có giới hạn bước)"]
        SA1 & SA2 --> TOOLS["Công cụ có cấu trúc<br/>tra môn · chuỗi tiên quyết ·<br/>đối chiếu hồ sơ · thống kê danh mục"]
        SA1 & SA2 --> RET["Truy xuất văn bản (BM25)<br/>chỉ trong nguồn của khóa đã chọn"]
        TOOLS --> KB[("Kho dữ liệu theo khóa<br/>courses · conditions · sources<br/>documents (quy chế, học phí,<br/>chuẩn đầu ra) · gaps")]
        RET --> KB
        TOOLS --> EV["Bằng chứng<br/>đoạn nguồn + kết quả công cụ (TOOL-n)"]
        RET --> EV
    end

    EV --> GEN

    subgraph A["④ Tổng hợp và kiểm tra"]
        GEN["LLM viết câu trả lời<br/>chỉ từ bằng chứng"] --> CHK{"Mỗi kết luận có<br/>ID nguồn + trích nguyên văn?"}
        CHK -- "Không" --> BLOCK["Chặn kết luận<br/>→ 'chưa đủ căn cứ'"]
        CHK -- "Có" --> MERGE["Ghép câu trả lời các agent con<br/>+ cảnh báo (OCR, dữ liệu tạm thời)"]
    end

    MERGE --> OUT(["✅ Hiển thị cho sinh viên:<br/>câu trả lời + trích dẫn + nhật ký hành động"])
    ASK & OOS & GAP & BLOCK --> OUT2(["⚠️ Hiển thị cho sinh viên:<br/>hỏi lại / từ chối / báo thiếu dữ liệu"])
```

**Ý chính**

- Hàng rào ① luôn chạy bằng quy tắc Python, không phụ thuộc LLM: khóa sai hoặc dữ liệu thiếu thì dừng sớm,
  không tốn token và không có cơ hội bịa.
- Agent con chỉ được đọc **kho dữ liệu của khóa đã chọn** — khóa là tham số bắt buộc, LLM không tự đổi.
- Số liệu (đếm môn, so sánh ngưỡng điểm/tín chỉ) do **công cụ** tính; LLM chỉ diễn đạt.

---

## 2. Hướng 1 — Agent con theo khóa

Mỗi agent khóa sở hữu đúng chương trình, phiên bản và văn bản áp dụng cho khóa đó.

```mermaid
flowchart LR
    Q(["Câu hỏi + khóa đã chọn"]) --> ORC{"Orchestrator<br/>định tuyến theo khóa"}

    ORC -->|K35| A35
    ORC -->|K36| A36
    ORC -->|K37| A37
    ORC -->|K38| A38
    ORC -->|K39| A39

    subgraph A35["Agent K35 — CNTT-2022"]
        D35["Khung gốc S13 (chưa chuẩn hóa bảng môn)<br/>Quy chế 2024 (S03)<br/>Chuẩn đầu ra TA khóa ≥26 (N02)<br/>Học phí 2026–2027 (N03)"]
    end
    subgraph A36["Agent K36 — CNTT-2023 ⚠ tạm thời"]
        D36["72 môn, 82 điều kiện (ảnh S26, chưa đối chiếu S15)<br/>Quy chế 2024 (S03) · TOEIC quốc tế (S04)<br/>Chuẩn đầu ra TA (N02) · Học phí (N03)"]
    end
    subgraph A37["Agent K37 — CNTT-2024 ✔ đã xác minh"]
        D37["99 môn, 76 điều kiện (S01)<br/>Quy chế 2024 (S03) · TOEIC quốc tế (S04)<br/>Chuẩn đầu ra TA (N02) · Học phí (N03)"]
    end
    subgraph A38["Agent K38 — CNTT-2025"]
        D38["Bản mô tả CTĐT (S17/S18), chưa có bảng môn<br/>Quy chế 2025 (S05)<br/>Chuẩn đầu ra ngoại ngữ 2026 (N01) · Học phí (N03)"]
    end
    subgraph A39["Agent K39 — CNTT-2026"]
        D39["CTĐT K39 (S20/S21), chưa có bảng môn<br/>Quy chế 2026 (S06)<br/>Học phí Khóa 39 (N04)"]
    end

    A35 & A36 & A37 & A38 & A39 --> SHARED["Bộ công cụ dùng chung<br/>(cùng code, khác dữ liệu)"]
    SHARED --> ANS(["Câu trả lời đúng khóa"])
```

| Ưu điểm | Nhược điểm |
|---|---|
| Cô lập dữ liệu rất rõ: agent K38 không thể "mượn" quy chế K37 | 5 agent có **cùng logic**, chỉ khác dữ liệu → trùng lặp prompt và code |
| Dễ giải thích phạm vi cho người dùng và hội đồng | Khóa đã được chọn ở giao diện, nên Orchestrator **không có gì để quyết định** — định tuyến tầm thường |
| Dễ cập nhật từng khóa độc lập | Không giúp hiểu câu hỏi tốt hơn: câu "học phí" và "tiên quyết" vẫn đi chung một agent |

---

## 3. Hướng 2 — Agent con theo cụm vấn đề (10 agent)

Khóa trở thành **tham số phạm vi** truyền cho mọi agent; Orchestrator quyết định *loại câu hỏi*.

```mermaid
flowchart LR
    Q(["Câu hỏi + khóa đã chọn"]) --> ORC{"Orchestrator<br/>phân loại ý định<br/>(1 hoặc nhiều chủ đề)"}

    ORC --> C1["① Học phần & tín chỉ"]
    ORC --> C2["② Tiên quyết & lộ trình môn"]
    ORC --> C3["③ Kế hoạch học tập & đăng ký học"]
    ORC --> C4["④ Điểm & đánh giá"]
    ORC --> C5["⑤ Cảnh báo & xử lý học vụ"]
    ORC --> C6["⑥ Tốt nghiệp, thực tập, khóa luận"]
    ORC --> C7["⑦ Ngoại ngữ & chuẩn đầu ra"]
    ORC --> C8["⑧ Học phí & lệ phí"]
    ORC --> C9["⑨ Chuyển ngành, song ngành & thủ tục"]
    ORC --> C10["⑩ Chương trình đào tạo & phiên bản khóa"]
    ORC -.->|"lịch thi, TKB, lớp mở,<br/>câu hỏi cá nhân"| X["Thông tin theo thời điểm<br/>→ báo thiếu dữ liệu, trỏ kênh chính thức"]

    C1 & C2 & C10 --> TS[("Bảng học phần + điều kiện<br/>courses · conditions")]
    C3 & C4 & C5 & C6 & C9 --> RS[("Quy chế đào tạo theo khóa<br/>S03 / S05 / S06")]
    C6 & C7 --> LS[("Chuẩn đầu ra ngoại ngữ<br/>S04 · N01 · N02")]
    C8 --> FS[("Học phí<br/>N03 · N04")]
    C10 --> VS[("Phiên bản CTĐT<br/>VERSION-Kxx · S01/S13/S15/S17/S20")]
    C2 & C6 --> PT["Công cụ đối chiếu hồ sơ<br/>(AND/OR, ngưỡng điểm, tín chỉ)"]

    TS & RS & LS & FS & VS & PT --> EV["Bằng chứng (lọc theo khóa)"]
    EV --> ANS(["Câu trả lời ghép từ các chủ đề"])
```

### 3.1 Danh mục 10 chủ đề, dữ liệu và câu hỏi mẫu

| # | Agent chủ đề | Dữ liệu / công cụ | Câu hỏi sinh viên có thể hỏi |
|---|---|---|---|
| ① | **Học phần & tín chỉ** | Bảng học phần; công cụ tra môn, thống kê danh mục | "IT320 mấy tín chỉ?" · "Môn CSDL là môn nào?" · "Chương trình có bao nhiêu môn bắt buộc?" · "Nhóm lựa chọn ngành có những môn gì?" · "Học máy là môn bắt buộc hay tự chọn?" |
| ② | **Tiên quyết & lộ trình môn** | Bảng điều kiện; công cụ lần chuỗi, đối chiếu hồ sơ | "Muốn học Học máy phải qua môn gì?" · "Lộ trình để học Phân tích mã độc?" · "Tôi đạt CS122 rồi, học IT320 được chưa?" · "Rớt Giải tích 1 có học Giải tích 2 được không?" · "Học xong OOP thì học tiếp được môn nào?" |
| ③ | **Kế hoạch học tập & đăng ký học** | Quy chế (đăng ký học), kế hoạch đào tạo năm học, thông báo mẫu | "Một kỳ được đăng ký tối đa bao nhiêu tín chỉ?" · "Học kỳ phụ là gì, ai được đăng ký?" · "Kỳ đầu có phải tự đăng ký môn không?" · "Năm học 2026–2027 bắt đầu khi nào?" · "Nên phân bổ các môn cơ sở thế nào?" |
| ④ | **Điểm & đánh giá** | Quy chế (Điều đánh giá, thi lại, thang điểm) | "Điểm dưới bao nhiêu phải thi lại?" · "Điểm chữ B+ bằng bao nhiêu thang 4?" · "Điểm quá trình dưới 4 thì sao?" · "Học cải thiện điểm lấy điểm nào?" · "Phúc tra điểm thi nộp ở đâu, khi nào?" |
| ⑤ | **Cảnh báo & xử lý học vụ** | Quy chế (cảnh báo, buộc thôi học, nghỉ học tạm thời, bảo lưu) | "Khi nào bị cảnh báo học tập?" · "Nợ bao nhiêu tín chỉ thì bị buộc thôi học?" · "Bảo lưu kết quả học tập được bao lâu?" · "Nghỉ học tạm thời cần thủ tục gì?" · "Thời gian học tối đa là bao lâu?" |
| ⑥ | **Tốt nghiệp, thực tập, khóa luận** | Quy chế (công nhận, xếp hạng tốt nghiệp, khóa luận); điều kiện IP406/IT499; đối chiếu hồ sơ | "Điều kiện làm khóa luận là gì?" · "TBTL bao nhiêu thì tốt nghiệp loại giỏi?" · "Không làm khóa luận thì học gì thay?" · "Một năm xét tốt nghiệp mấy đợt?" · "Học lại nhiều có bị hạ hạng tốt nghiệp không?" |
| ⑦ | **Ngoại ngữ & chuẩn đầu ra** | TOEIC quốc tế (S04), chuẩn đầu ra 2023/2026 (N02/N01), quy đổi chứng chỉ | "Cần bao nhiêu điểm TOEIC để tốt nghiệp?" · "TOEIC 4 kỹ năng tính thế nào?" · "Chứng chỉ hết hạn có được xét không?" · "Có IELTS thì được miễn học tiếng Anh không?" · "K38 dùng chứng chỉ nào thay TOEIC được?" |
| ⑧ | **Học phí & lệ phí** | Học phí 2026–2027 (N03), học phí K39 (N04), học phí học lại, miễn giảm | "Học phí ngành CNTT K37 năm nay bao nhiêu?" · "Học phí K39 mỗi kỳ?" · "Học lại một môn tốn bao nhiêu?" · "Được miễn giảm học phí theo diện nào?" · "Lệ phí thi lại là bao nhiêu?" |
| ⑨ | **Chuyển ngành, song ngành & thủ tục** | Quy chế (chuyển ngành, học cùng lúc hai chương trình, trao đổi), thông báo thủ tục | "Muốn chuyển sang ngành Trí tuệ nhân tạo cần điều kiện gì?" · "Có được học song ngành không?" · "Môn đã học có được công nhận khi chuyển ngành?" · "Xin giấy xác nhận sinh viên ở đâu?" · "Chuyển trường có được không?" |
| ⑩ | **Chương trình đào tạo & phiên bản khóa** | VERSION-Kxx, khung CTĐT theo khóa, bản mô tả CTĐT | "Chương trình K38 bao nhiêu tín chỉ, học mấy năm?" · "Khung chương trình khóa mình theo quyết định nào?" · "K36 khác K37 ở những môn nào?" · "Chuẩn đầu ra của ngành CNTT là gì?" · "Dữ liệu của khóa mình đã đầy đủ chưa?" |
| — | *Thông tin theo thời điểm* (không phải agent trả lời) | Mục dữ liệu thiếu (gaps) | "Lịch thi kỳ này?" · "Lớp IT320 còn chỗ không?" · "Thầy nào dạy Python?" · "Em đủ điều kiện tốt nghiệp chưa?" (cần bảng điểm cá nhân) |

### 3.2 Ví dụ một câu hỏi nhiều ý đi qua hệ thống

> "Khai phá dữ liệu mấy tín, học trước môn gì, và nếu rớt thì học lại tốn bao nhiêu?" — sinh viên K37

```mermaid
sequenceDiagram
    autonumber
    actor SV as Sinh viên K37
    participant G as Hàng rào phạm vi
    participant O as Orchestrator
    participant A1 as ① Học phần
    participant A2 as ② Tiên quyết
    participant A8 as ⑧ Học phí
    participant KB as Kho dữ liệu K37
    participant V as Kiểm tra trích dẫn

    SV->>G: câu hỏi + cohort=K37
    G->>G: đúng khóa, đúng ngành, có dữ liệu → cho qua
    G->>O: câu hỏi đã kiểm tra
    O->>O: tách 3 ý → chủ đề ①, ②, ⑧
    par Chạy song song
        O->>A1: "IS326 mấy tín?"
        A1->>KB: tra môn IS326
        KB-->>A1: COURSE-IS326 (3 tín chỉ)
    and
        O->>A2: "IS326 học trước môn gì?"
        A2->>KB: lần chuỗi điều kiện
        KB-->>A2: IS224 (ghi trong nguồn)
    and
        O->>A8: "học lại tốn bao nhiêu?"
        A8->>KB: tìm văn bản học phí học lại
        KB-->>A8: N03 + mục còn thiếu nếu không có mức K37
    end
    A1-->>O: kết luận + nguồn
    A2-->>O: kết luận + nguồn
    A8-->>O: kết luận hoặc "chưa đủ căn cứ"
    O->>V: ghép 3 phần
    V-->>SV: câu trả lời từng ý, mỗi ý có trích dẫn
```

---

## 4. So sánh và đề xuất cho đề tài

| Tiêu chí | Hướng 1: theo khóa | Hướng 2: theo chủ đề |
|---|---|---|
| Orchestrator có quyết định gì | Gần như không (khóa đã chọn ở UI) | Có: phân loại ý định, tách câu nhiều ý |
| Trùng lặp | Cao (5 agent cùng logic) | Thấp (mỗi agent một chuyên môn) |
| Prompt và công cụ | Chung chung | Chuyên biệt theo chủ đề → chính xác hơn |
| Cô lập dữ liệu theo khóa | Tự nhiên | Phải truyền khóa làm bộ lọc (đã có sẵn trong catalog) |
| Đánh giá trong NCKH | Khó tạo khác biệt | Đo được độ chính xác định tuyến theo chủ đề |

**Đề xuất: kết hợp — khóa là *phạm vi*, chủ đề là *agent*.**

```mermaid
flowchart LR
    Q(["Câu hỏi"]) --> K["Lớp 1 — Phạm vi khóa<br/>(quy tắc, không dùng LLM)<br/>chọn kho dữ liệu K35…K39"]
    K --> O{"Lớp 2 — Orchestrator<br/>(LLM hoặc quy tắc)<br/>chọn 1..n chủ đề"}
    O --> S["Lớp 3 — Agent chủ đề ①…⑩<br/>dùng công cụ + văn bản<br/>CỦA ĐÚNG KHÓA"]
    S --> C["Lớp 4 — Kiểm tra trích dẫn<br/>+ ghép câu trả lời"]
    C --> R(["Trả lời"])
```

- **Lớp 1** chính là hàng rào đã có (`DemoEngine`, `Catalog` theo khóa) — giữ nguyên.
- **Lớp 2** mở rộng `planner.py` / `llm_agent.py`: thay vì chọn công cụ trực tiếp, chọn chủ đề;
  có thể so sánh định tuyến bằng quy tắc với định tuyến bằng LLM như thực nghiệm đã làm.
- **Lớp 3** mỗi agent chỉ có 2–4 công cụ liên quan và prompt riêng (ví dụ agent ④ biết thang điểm
  10/4, agent ⑦ biết chứng chỉ phải còn hiệu lực) → ít nhầm công cụ hơn agent lớn duy nhất.
- **Thực nghiệm gợi ý:** gán nhãn chủ đề ①…⑩ cho bộ đánh giá, đo (a) độ đúng định tuyến,
  (b) độ đúng câu trả lời theo từng chủ đề, (c) chi phí — so với Agentic RAG một agent hiện tại.
