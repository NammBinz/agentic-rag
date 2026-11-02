"use strict";
const $ = id => document.getElementById(id);
const sessionKey = () => `${state.dataset}:${state.cohort || "unknown"}`;
const state = {dataset: "project", cohort: null, cohorts: [], sessions: {}, current: null, catalog: null, busy: false};
const COHORT_KEY = "agentic-rag-cohort-v1";
const cohortStatus = {verified_snapshot: ["Đã xác minh khung gốc", "good"], provisional_snapshot: ["Tạm thời · trích từ ảnh", "warn"], insufficient_data: ["Chưa có bảng học phần", ""]};
const labels = {catalog_summary: "Kết quả từ danh mục học phần",recorded_conditions: "Điều kiện được ghi trong bảng", evidence_found: "Đã tìm thấy dẫn chứng", answered: "Đã trả lời có nguồn", insufficient_data: "Chưa đủ căn cứ", needs_input: "Cần bổ sung thông tin", out_of_scope: "Ngoài phạm vi dữ liệu", unavailable: "Chưa bật API", satisfied_in_snapshot: "Thỏa điều kiện trong snapshot", not_met_in_snapshot: "Chưa thỏa điều kiện trong snapshot", mixed_results: "Xem kết quả từng môn", not_found: "Chưa có mã môn"};
const actionLabels = {catalog_summary: "Thống kê toàn bộ danh mục",lookup_conditions: "Tra điều kiện và chuỗi mã", generate: "LLM diễn đạt theo nguồn", route: "Chọn cách xử lý", retrieve: "Truy xuất tài liệu", lookup_course: "Tra học phần", check_prerequisites: "Kiểm tra tiên quyết", check_evidence: "Kiểm tra bằng chứng còn thiếu", stop: "Kết thúc theo giới hạn"};
function el(tag, className, text) { const n = document.createElement(tag); if (className) n.className = className; if (text !== undefined) n.textContent = text; return n; }
function mode() { return document.querySelector('input[name="mode"]:checked').value; }
function save() { try { localStorage.setItem("agentic-rag-flask-v4", JSON.stringify(state.sessions)); } catch { $("history-label").textContent = "Không lưu được lịch sử; hội thoại vẫn dùng được"; } }
function load() { try { const s = JSON.parse(localStorage.getItem("agentic-rag-flask-v4") || "null"); if (s && typeof s === "object" && Object.values(s).every(Array.isArray)) state.sessions = s; } catch { /* A broken storage entry is not needed for a new conversation. */ } }
const cohortInfo = () => state.cohorts.find(c => c.cohort === state.cohort) || null;
const cohortLabel = c => `${c.cohort} — ${c.frame_version || c.curriculum_id || "chưa rõ phiên bản"}`;
function renderCohortOptions() {
  $("cohort-options").replaceChildren(); $("cohort").replaceChildren(new Option("Chọn khóa…", ""));
  for (const c of state.cohorts) {
    const [tag, tone] = cohortStatus[c.status] || [c.status, ""];
    const b = el("button", "cohort-option" + (c.cohort === state.cohort ? " selected" : "")); b.type = "button"; b.setAttribute("role", "listitem");
    b.append(el("strong", "", c.cohort), el("span", "cohort-meta", `Tuyển sinh ${c.admission_year ?? "?"} · ${c.frame_version || c.curriculum_id || "chưa rõ phiên bản"}`), el("span", "cohort-tag " + tone, tag), el("span", "cohort-desc", c.course_count ? `${c.course_count} học phần có nguồn. ${c.status === "provisional_snapshot" ? "Chưa đối chiếu với quyết định gốc." : "Tra môn, điều kiện và kiểm tra tiên quyết."}` : "Chỉ tra thông tin chương trình và văn bản đúng khóa."));
    b.addEventListener("click", () => chooseCohort(c.cohort)); $("cohort-options").append(b);
    $("cohort").append(new Option(cohortLabel(c), c.cohort));
  }
  $("cohort").value = state.cohort || "";
}
function openPicker() {
  $("cohort-picker").hidden = false; $("welcome").hidden = true; $("messages").hidden = true; $("data-notice").hidden = true; $("scope-badge").hidden = true;
  $("question").disabled = true; $("send").disabled = true; $("question").placeholder = "Chọn khóa của bạn để bắt đầu"; renderCohortOptions(); showEvidence(null);
}
function chooseCohort(cohort) {
  if (!state.cohorts.some(c => c.cohort === cohort)) return openPicker();
  state.cohort = cohort; state.catalog = null; try { localStorage.setItem(COHORT_KEY, cohort); } catch { /* Selection still works for this visit. */ }
  for (const id of ["completed", "grades", "credits", "average"]) $(id).value = "";
  $("cohort-picker").hidden = true; $("messages").hidden = false; $("question").disabled = false; $("send").disabled = state.busy;
  $("question").placeholder = `Hỏi về chương trình CNTT ${cohort}…`; $("error").textContent = "";
  renderCohortOptions(); updateNotice(); examples(); renderMessages(); showEvidence((state.sessions[sessionKey()] ||= []).at(-1)?.response || null); $("question").focus();
}
async function fetchJSON(url, options) { const r = await fetch(url, options); const data = await r.json(); if (!r.ok) throw new Error(data.error || `Lỗi HTTP ${r.status}`); return data; }
function examples() {
  const info = cohortInfo();
  const qs = state.dataset === "sample" ? ["PY201 có bao nhiêu tín chỉ?", "Kiểm tra tiên quyết PY201", "So sánh PY201 và CS101", "Đăng ký tối đa bao nhiêu tín chỉ mỗi kỳ?"]
    : info?.status === "verified_snapshot" ? ["IT320 có bao nhiêu tín chỉ và tiên quyết gì?", "Kiểm tra tiên quyết IT499", "IT320 yêu cầu môn nào? Môn đó yêu cầu gì?", "Điều kiện được ghi cho IT499 là gì?", "Học phí kỳ này là bao nhiêu?"]
    : info?.status === "provisional_snapshot" ? ["Học máy CS320 cần học môn nào trước?", "Kiểm tra tiên quyết IT320", "Nhóm lựa chọn ngành phải chọn bao nhiêu tín chỉ?", "Điều kiện làm khóa luận IT499 là gì?"]
    : [`Chương trình CNTT ${state.cohort} có bao nhiêu tín chỉ, học mấy năm?`, "Khung chương trình của khóa mình theo quyết định nào?", "Dữ liệu học phần của khóa mình đã có chưa?", "Quy chế đào tạo nào áp dụng cho khóa mình?"];
  $("examples").replaceChildren();
  for (const q of qs) { const b = el("button", "example", q); b.type = "button"; b.append(el("span", "", "↗")); b.addEventListener("click", () => { $("question").value = q; $("question").focus(); }); $("examples").append(b); }
}
function updateNotice() {
  const info = cohortInfo(); if (!info) return;
  $("scope-badge").hidden = false; $("data-notice").hidden = false;
  $("scope-badge").textContent = `${cohortLabel(info)} · Đổi khóa`; $("scope-badge").classList.toggle("provisional", info.status === "provisional_snapshot");
  const sample = state.dataset === "sample"; $("data-notice").classList.toggle("sample", sample);
  $("data-notice").classList.toggle("provisional", info.status === "provisional_snapshot"); $("data-notice").classList.toggle("limited", info.status === "insufficient_data");
  $("data-notice").lastElementChild.textContent = sample ? "DỮ LIỆU GIẢ LẬP — điều kiện và quy định chỉ dùng kiểm thử, không phải quy định TLU." : `${cohortLabel(info)} · ${info.message}`;
}
function appendAnswerText(container, answer, citations) {
  const known = new Map(citations.map(c => [c.id, c]));
  const parts = answer.split(/(\[[A-Z0-9_-]+\])/g);
  for (const part of parts) { const id = part.startsWith("[") ? part.slice(1, -1) : ""; if (known.has(id)) { const b = el("button", "citation-link", part); b.type = "button"; b.addEventListener("click", () => openSource(known.get(id))); container.append(b); } else container.append(document.createTextNode(part)); }
}
function renderMessages() {
  $("messages").replaceChildren();
  const entries = (state.sessions[sessionKey()] ||= []); $("welcome").hidden = entries.length > 0;
  for (const entry of entries) {
    const user = el("div", "message user-message"); user.append(el("div", "user-bubble", entry.question)); $("messages").append(user);
    const r = entry.response;
    const item = el("article", "message assistant-message"); const label = el("div", "assistant-label"); label.append(el("span", "mini-avatar", "↗"), document.createTextNode(r.mode === "agent" ? (r.config && r.config.planner === "llm" ? "Agentic RAG · LLM lập kế hoạch" : "Agentic RAG") : r.mode === "rag" ? "RAG một lượt" : "LLM đối chứng")); item.append(label);
    const bubble = el("div", "answer-bubble"); bubble.append(el("span", "status-label" + (["evidence_found", "answered", "catalog_summary", "satisfied_in_snapshot"].includes(r.status) ? " good" : ""), labels[r.status] || r.status));
    const text = el("p", "answer-text"); appendAnswerText(text, r.answer, r.citations || []); bubble.append(text); item.append(bubble);
    const meta = el("div", "response-meta"); meta.append(el("span", "", `${r.metrics.retrieval_rounds} lượt tra · ${r.metrics.tool_calls} công cụ · ${r.metrics.latency_ms} ms`)); const show = el("button", "", "Xem nguồn & hành động"); show.type = "button"; show.addEventListener("click", () => showEvidence(r)); meta.append(show); item.append(meta); $("messages").append(item);
  }
  if (state.busy) { const t = el("div", "thinking"); t.append(el("span"), document.createTextNode("Đang tra nguồn và kiểm tra điều kiện…")); $("messages").append(t); }
  $("conversation").scrollTop = $("conversation").scrollHeight;
}
function showEvidence(r) {
  state.current = r;
  $("stat-rounds").textContent = r ? r.metrics.retrieval_rounds : "—"; $("stat-tools").textContent = r ? r.metrics.tool_calls : "—";
  $("stat-time").textContent = r ? (r.metrics.latency_ms >= 1000 ? `${(r.metrics.latency_ms / 1000).toFixed(1)}s` : `${Math.round(r.metrics.latency_ms)}ms`) : "—";
  $("stat-tokens").textContent = r ? r.metrics.prompt_tokens + r.metrics.completion_tokens : "—";
  $("stat-tokens").parentElement.title = r ? `Embedding: ${r.metrics.embedding_tokens}; lập chỉ mục: ${r.metrics.index_embedding_tokens}; chi phí USD: ${r.metrics.estimated_cost_usd ?? "chưa cấu hình đơn giá"}` : "";
  const citations = r?.citations || []; $("source-count").textContent = citations.length; $("sources-view").replaceChildren();
  if (!citations.length) { const n = el("div", "empty-evidence"); n.append(el("span", "", "⌁"), el("p", "", "Chưa có đoạn nguồn được dùng cho câu trả lời này.")); $("sources-view").append(n); }
  for (const c of citations) { const b = el("div", "source-card"); b.tabIndex = 0; b.setAttribute("role", "button"); b.setAttribute("aria-label", `Mở dẫn chứng ${c.id}`); b.append(el("span", "source-id", c.id), el("h3", "", c.source_title), el("p", "", c.text), el("small", "", c.page ? `Trang PDF ${c.page} · ${c.cohort} ↗` : `${c.section} ↗`)); b.addEventListener("click", () => openSource(c)); b.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); openSource(c); } }); $("sources-view").append(b); }
  $("actions-view").replaceChildren();
  for (const a of r?.actions || []) { const n = el("div", "trace-item"); n.append(el("strong", "", actionLabels[a.action] || a.action)); let detail = ""; if (a.action === "route") detail = `${a.intent} · ${a.targets.join(", ") || "Câu hỏi thông tin"}`; else if (a.action === "retrieve") detail = `Lượt ${a.round}: ${a.query}\n${a.chunk_ids.join(", ")}`; else if (a.target) detail = `${a.target}: ${labels[a.status] || a.status}`; else if (a.action === "check_evidence") detail = a.missing_topic || (a.missing_course_records.length ? `Cần thêm: ${a.missing_course_records.join(", ")}` : "Đã có bản ghi được yêu cầu."); else detail = a.reason || ""; n.append(el("p", "", detail)); $("actions-view").append(n); }
  if (!r?.actions?.length) $("actions-view").append(el("p", "evidence-foot", "Các hành động sẽ xuất hiện sau khi đặt câu hỏi."));
}
function openSource(c) {
  $("dialog-title").textContent = c.source_title; const container = $("dialog-content"); container.replaceChildren();
  const dl = el("dl", "dialog-meta"); for (const [name, value] of [["Mã đoạn", c.id], ["Khóa / phiên bản", `${c.cohort} / ${c.curriculum_version || "Chưa xác minh"}; văn bản ${c.document_version}`], ["Các khóa áp dụng", (c.applicable_cohorts || []).join(", ")], ["Vị trí", c.page ? `Trang PDF ${c.page}; dòng ${c.section}` : c.section], ["Hiệu lực", c.effective_at || "Chưa xác minh"], ["Bản ghi Excel", `${c.workbook_sheet || "Danh mục nguồn"}${c.workbook_row ? "!" + c.workbook_row : ""}`], ["Mức chứng cứ", c.content_level], ["Trạng thái", c.verification]]) { dl.append(el("dt", "", name), el("dd", "", value)); } container.append(dl, el("blockquote", "", c.text), el("p", "source-note", c.evidence_note));
  const links = el("div", "source-links"); for (const [url, label] of [[c.url, "Trang công bố chính thức ↗"], [c.file_url, "Mở tài liệu tham chiếu ↗"]]) { if (url && /^https?:\/\//i.test(url)) { const a = el("a", "", label); a.href = url; a.target = "_blank"; a.rel = "noopener noreferrer"; links.append(a); } } container.append(links); $("source-dialog").showModal();
}
function profile() {
  const completed = $("completed-known").checked ? $("completed").value.split(/[,;\s]+/).filter(Boolean).map(x => x.toUpperCase()) : null;
  const grades = {}; for (const part of $("grades").value.split(/[,;]+/).filter(x => x.trim())) { const pair = part.trim().match(/^([A-Za-z]{2}\d{3})\s*:\s*(\d+(?:\.\d+)?)$/); if (!pair) throw new Error("Điểm có dạng GE111: 6.5; dùng dấu chấm cho phần thập phân."); grades[pair[1].toUpperCase()] = Number(pair[2]); }
  return {completed, grades, credits: $("credits").value === "" ? null : Number($("credits").value), average: $("average").value === "" ? null : Number($("average").value)};
}
function setBusy(value) { state.busy = value; $("send").disabled = value || !state.cohort; $("dataset").disabled = true; $("cohort").disabled = value; $("scope-badge").disabled = value; $("clear").disabled = value; renderMessages(); }
$("chat-form").addEventListener("submit", async e => {
  e.preventDefault(); if (state.busy) return; if (!state.cohort) return openPicker(); const question = $("question").value.trim(); if (!question) return; $("error").textContent = "";
  const controller = new AbortController(); const timeout = setTimeout(() => controller.abort(), 150000);
  try { const selected = mode(); const payload = {question, mode: selected === "agent-llm" ? "agent" : selected, planner: selected === "agent-llm" ? "llm" : undefined, dataset: state.dataset, cohort: state.cohort, profile: profile(), history: (state.sessions[sessionKey()] ||= []).slice(-6).map(x => ({question: x.question}))}; setBusy(true); const response = await fetchJSON("/api/chat", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(payload), signal: controller.signal}); (state.sessions[sessionKey()] ||= []).push({question, response}); state.sessions[sessionKey()] = (state.sessions[sessionKey()] ||= []).slice(-20); save(); $("question").value = ""; showEvidence(response); } catch (error) { $("error").textContent = error.name === "AbortError" ? "Yêu cầu quá thời gian; kiểm tra API rồi thử lại." : error.message; } finally { clearTimeout(timeout); setBusy(false); $("question").focus(); }
});
$("question").addEventListener("keydown", e => { if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); $("chat-form").requestSubmit(); } });
$("dataset").addEventListener("change", () => { state.dataset = $("dataset").value; state.catalog = null; $("error").textContent = ""; $("question").value = ""; for (const id of ["completed", "grades", "credits", "average"]) $(id).value = ""; updateNotice(); examples(); renderMessages(); showEvidence((state.sessions[sessionKey()] ||= []).at(-1)?.response || null); });
$("cohort").addEventListener("change", () => { $("question").value = ""; if ($("cohort").value) chooseCohort($("cohort").value); else openPicker(); });
$("scope-badge").addEventListener("click", openPicker);
$("clear").addEventListener("click", () => { state.sessions[sessionKey()] = []; save(); renderMessages(); showEvidence(null); });
$("sample-profile").addEventListener("click", () => { const sample = state.dataset === "sample", k36 = state.cohort === "K36"; $("completed-known").checked = true; $("completed").value = sample ? "PY101" : k36 ? "CS122, IP406" : "CS122, IS224"; $("grades").value = sample ? "PY101: 6, CS101: 7" : k36 ? "CS122: 6, IP406: 7" : "GE111: 6, IP406: 7"; $("credits").value = sample ? 12 : k36 ? 120 : 100; $("average").value = 7; });
for (const name of ["sources", "actions"]) $(name + "-tab").addEventListener("click", () => { for (const other of ["sources", "actions"]) { $(other + "-tab").setAttribute("aria-selected", String(other === name)); $(other + "-view").hidden = other !== name; } });
$("close-dialog").addEventListener("click", () => $("source-dialog").close()); $("close-catalog").addEventListener("click", () => $("catalog-dialog").close());
function renderCatalog() { const query = $("catalog-search").value.normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/đ/g, "d").toLowerCase(); $("catalog-content").replaceChildren(); $("catalog-content").append(el("p", "source-note", state.catalog?.context?.message || "")); for (const c of state.catalog?.courses || []) { const text = `${c.code} ${c.name}`.normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/đ/g, "d").toLowerCase(); if (!text.includes(query)) continue; const row = el("div", "catalog-row"); row.tabIndex = 0; row.setAttribute("role", "button"); row.setAttribute("aria-label", `Tra học phần ${c.code}`); const middle = el("div", "", c.name); middle.append(el("small", "", `Tiên quyết: ${c.prerequisite_raw ?? "Ô nguồn trống, chưa xác định"}`)); row.append(el("strong", "", c.code), middle, el("span", "", `${c.credits} TC`)); const choose = () => { $("question").value = `${c.code} có bao nhiêu tín chỉ và tiên quyết gì?`; $("catalog-dialog").close(); $("question").focus(); }; row.addEventListener("click", choose); row.addEventListener("keydown", e => { if (e.key === "Enter") choose(); }); $("catalog-content").append(row); } }
$("catalog-button").addEventListener("click", async () => { try { if (!state.cohort) return openPicker(); state.catalog = await fetchJSON(`/api/catalog?dataset=${state.dataset}&cohort=${encodeURIComponent(state.cohort)}`); $("catalog-search").value = ""; renderCatalog(); $("catalog-dialog").showModal(); } catch (error) { $("error").textContent = error.message; } }); $("catalog-search").addEventListener("input", renderCatalog);
load();
fetchJSON("/api/cohorts").then(data => { state.cohorts = data.cohorts; let saved = null; try { saved = localStorage.getItem(COHORT_KEY); } catch { /* No remembered cohort. */ } if (saved && state.cohorts.some(c => c.cohort === saved)) chooseCohort(saved); else openPicker(); }).catch(error => { $("cohort-options").replaceChildren(el("p", "cohort-loading", "Không tải được danh sách khóa; kiểm tra máy chủ rồi tải lại trang.")); $("cohort-picker").hidden = false; $("error").textContent = error.message; });
if (window.matchMedia("(max-width:620px)").matches) document.querySelector(".profile-panel").open = false;
fetchJSON("/api/health").then(data => { $("engine-status").textContent = data.provider === "offline" ? "Chế độ trích xuất · Offline" : `LLM đã bật · ${data.provider === "gemini" ? "Gemini" : "OpenAI"} · ${data.retriever}`; }).catch(error => { $("engine-status").textContent = "Chưa kết nối máy chủ"; $("error").textContent = error.message; });
