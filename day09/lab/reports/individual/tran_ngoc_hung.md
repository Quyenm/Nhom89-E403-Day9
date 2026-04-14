# Báo Cáo Cá Nhân — Lab Day 09: Multi-Agent Orchestration

**Họ và tên:** Trần Ngọc Hùng  
**Vai trò trong nhóm:** Supervisor Owner  
**Ngày nộp:** 14/04/2026  

---

> **Lưu ý quan trọng:**
> - Viết ở ngôi **"tôi"**, gắn với chi tiết thật của phần bạn làm
> - Phải có **bằng chứng cụ thể**: tên file, đoạn code, kết quả trace, hoặc commit
> - Nội dung phân tích phải khác hoàn toàn với các thành viên trong nhóm
> - Deadline: Được commit **sau 18:00** (xem SCORING.md)
> - Lưu file với tên: `reports/individual/[ten_ban].md` (VD: `nguyen_van_a.md`)

---

## 1. Tôi phụ trách phần nào? (100–150 từ)

Tôi phụ trách **Sprint 1 — Supervisor Orchestrator**, với trách nhiệm xây dựng toàn bộ lớp điều phối trung tâm của hệ thống multi-agent. Ngoài ra tôi cũng hỗ trợ thiết lập **ChromaDB index** (`chroma_db/`) và chạy pipeline tạo **trace artifacts** (`artifacts/traces/`).

**Module/file tôi chịu trách nhiệm:**
- File chính: `graph.py`
- Functions tôi implement:
  - `AgentState` (TypedDict) — shared state toàn bộ graph với 17 fields
  - `make_initial_state(task)` — khởi tạo state với run_id theo timestamp
  - `supervisor_node(state)` — đọc task, áp dụng keyword matching trên normalized text, quyết định route sang 1 trong 3 hướng: `retrieval_worker`, `policy_tool_worker`, `human_review`
  - `route_decision(state)` — trả về route dạng Literal string
  - `human_review_node(state)` — xử lý HITL trong lab mode (auto-approve)
  - `_requires_cross_doc_support(task)` — detect câu hỏi multi-hop cần retrieval trước policy
  - `build_graph()` — lắp ráp toàn bộ flow: supervisor → route → [retrieval | policy_tool | human_review] → synthesis
  - `run_graph(task)` — entry point cho external callers
  - `save_trace(state)` — lưu state ra file JSON trong `artifacts/traces/`
- Hỗ trợ: thiết lập `chroma_db/` (ChromaDB index cho 5 tài liệu nội bộ) và chạy pipeline sinh 25 trace files trong `artifacts/traces/`

**Cách công việc của tôi kết nối với phần của thành viên khác:**

`graph.py` là entry point duy nhất của hệ thống. Tôi định nghĩa `AgentState` — contract chung mà tất cả workers phải đọc và ghi vào. Dương Trịnh Hoài An (Worker Owner) phụ trách `workers/retrieval.py`, Nguyễn Tiến Đạt (MCP Owner) refactor `_normalize()` từ graph.py thành `utils/normalize.py` để dùng chung — graph.py hiện import từ đó: `from utils.normalize import normalize as _normalize`. Nếu tôi thay đổi tên field trong `AgentState`, toàn bộ nhóm bị ảnh hưởng.

**Bằng chứng (commit hash, file có comment tên bạn, v.v.):**

 Trace thực tế được sinh từ `run_graph()`: `artifacts/traces/run_20260414_170002_971360.json` (grading query gq01: "Ticket P1 được tạo lúc 22:47...") và `run_20260414_170014_881931.json` (grading query gq09: multi-hop P1 + Level 2 access). ChromaDB index tại `chroma_db/chroma.sqlite3` (577KB, collection `45393e46`).

---

## 2. Tôi đã ra một quyết định kỹ thuật gì? (150–200 từ)

**Quyết định:** Dùng keyword-based routing kết hợp với Vietnamese text normalization thay vì gọi LLM để classify intent.

Khi thiết kế `supervisor_node()`, tôi có hai lựa chọn:

1. **Gọi LLM để classify intent** — linh hoạt hơn, xử lý được câu hỏi mơ hồ, nhưng thêm ~800ms latency và một lần API call cho mỗi request.
2. **Keyword matching trên normalized text** — nhanh hơn (~0ms overhead), deterministic, dễ debug, nhưng cần maintain danh sách keyword thủ công.

Tôi chọn **phương án 2** vì trong bối cảnh CS + IT Helpdesk, các loại intent rất rõ ràng và có thể enumerate đầy đủ qua 3 tuple: `POLICY_KEYWORDS` (13 từ), `RETRIEVAL_KEYWORDS` (11 từ), `HIGH_RISK_KEYWORDS` (5 từ). Domain không phức tạp đến mức cần LLM để phân loại. Ban đầu tôi implement `_normalize()` inline trong graph.py (60+ ký tự Vietnamese mapping), sau đó Nguyễn Tiến Đạt tách ra `utils/normalize.py` để dùng chung — đây là cải tiến hợp lý vì tránh code duplication.

**Trade-off đã chấp nhận:** Sẽ miss-route nếu user dùng diễn đạt hoàn toàn ngoài danh sách keyword (ví dụ: câu hỏi ẩn dụ). Nhưng với 15 test questions + 10 grading questions, routing correct rate đạt 100%.

**Lý do:**  
Keyword routing nhanh hơn (~0ms routing vs ~800ms LLM call), chi phí zero, deterministic — và eval_report.json xác nhận routing distribution hợp lý: retrieval_worker 52%, policy_tool_worker 48%.

**Bằng chứng từ trace/code:**

```json
// trace: run_20260414_170002_971360.json (gq01)
{
  "task": "Ticket P1 được tạo lúc 22:47. Đúng theo SLA, ai nhận thông báo đầu tiên...",
  "supervisor_route": "retrieval_worker",
  "route_reason": "knowledge-base retrieval intent detected; time-sensitive incident question; no MCP required",
  "confidence": 0.89,
  "latency_ms": 11502
}

// trace: run_20260414_170014_881931.json (gq09 — multi-hop)
{
  "task": "Sự cố P1 xảy ra lúc 2am. Đồng thời cần cấp Level 2 access...",
  "supervisor_route": "policy_tool_worker",
  "route_reason": "policy/access intent detected; high-risk operational context; MCP enabled",
  "confidence": 0.95,
  "latency_ms": 33
}
```

Keyword "p1", "ticket" → `retrieval_worker` (gq01). Keyword "access", "level 2", "contractor" + "2am", "emergency" → `policy_tool_worker` với `risk_high=true` (gq09). Cả hai route đúng target worker.

---

## 3. Tôi đã sửa một lỗi gì? (150–200 từ)

**Lỗi:** Multi-hop query bị route sang `policy_tool_worker` mà không có evidence — policy worker không có chunks để evaluate, trả về `policy_applies=None`.

**Symptom (pipeline làm gì sai?):**

Query gq09: *"Sự cố P1 xảy ra lúc 2am. Đồng thời cần cấp Level 2 access tạm thời cho contractor để emergency fix..."*

Query này chứa cả `level 2`, `access`, `contractor` (policy keywords) lẫn `p1` (retrieval keyword), đồng thời có `2am` và `emergency` (high-risk keywords). Khi chỉ có policy worker chạy mà không có chunks từ retrieval trước, `policy_result` trả về rỗng và synthesis phải abstain vì không có evidence.

**Root cause (lỗi nằm ở đâu — routing logic):**

`supervisor_node()` ưu tiên policy route khi detect keyword "access"/"level 2", nhưng `build_graph()` ban đầu không có cơ chế nào đảm bảo policy worker nhận được evidence chunks trước khi chạy cho câu hỏi cần cả hai nguồn thông tin.

**Cách sửa:**

Tôi thêm hàm `_requires_cross_doc_support(task)` để detect các câu hỏi multi-hop (có cả P1/SLA/ticket VÀ access/cấp quyền/level). Trong `build_graph()`, nếu route là `policy_tool_worker` và `_requires_cross_doc_support()` trả về `True`, pipeline sẽ chạy `retrieval_worker_node()` **trước** để cung cấp context chunks, sau đó mới chạy `policy_tool_worker_node()`. Thêm fallback: nếu sau policy worker mà `retrieved_chunks` vẫn rỗng, chạy retrieval bổ sung.

```python
if route == "policy_tool_worker":
    # Multi-hop policy questions benefit from evidence first.
    if _requires_cross_doc_support(state["task"]):
        state = retrieval_worker_node(state)
    state = policy_tool_worker_node(state)
    if not state.get("retrieved_chunks"):
        state = retrieval_worker_node(state)
```

**Bằng chứng trước/sau:**

```
# Trước khi sửa:
policy_result: {}
final_answer: "Tôi không đủ thông tin để trả lời câu hỏi này."
confidence: 0.1

# Sau khi sửa — trace run_20260414_170014_881931.json (gq09):
workers_called: ["retrieval_worker", "policy_tool_worker", "synthesis_worker"]
policy_result.policy_applies: true
policy_result.access_result.emergency_override: true
mcp_tools_used: 3 calls (search_kb, check_access_permission, get_ticket_info)
confidence: 0.95
```

---

## 4. Tôi tự đánh giá đóng góp của mình (100–150 từ)

**Tôi làm tốt nhất ở điểm nào?**

Tôi thiết kế `AgentState` như một contract rõ ràng từ đầu — mọi field đều có type annotation và được khởi tạo trong `make_initial_state()`. Điều này giúp các thành viên khác (Hoài An với retrieval, Tiến Đạt với MCP) implement worker mà không cần hỏi lại tôi về format. `build_graph()` với multi-hop support đảm bảo câu gq09 đạt confidence 0.95. Việc thiết lập ChromaDB index và chạy sinh traces giúp nhóm có dữ liệu thực để viết docs và eval.

**Tôi làm chưa tốt hoặc còn yếu ở điểm nào?**

Danh sách keyword hiện tại là static — nếu domain mở rộng, tôi cần update thủ công. Ban đầu tôi copy-paste `_normalize()` trong graph.py mà không tách module dùng chung — Tiến Đạt đã fix bằng `utils/normalize.py`.

**Nhóm phụ thuộc vào tôi ở đâu?** _(Phần nào của hệ thống bị block nếu tôi chưa xong?)_

Tất cả workers phụ thuộc vào `AgentState` TypedDict mà tôi define. Nếu tôi chưa xong, không ai có thể implement worker function với đúng signature. `eval_trace.py` cũng cần `run_graph()` và `save_trace()` từ file của tôi. ChromaDB index và artifacts traces do tôi tạo cũng là input cần thiết cho Sprint 4.

**Phần tôi phụ thuộc vào thành viên khác:** _(Tôi cần gì từ ai để tiếp tục được?)_

Tôi cần `workers/retrieval.py` (Hoài An), `workers/policy_tool.py` (Đức Thắng), và `workers/synthesis.py` có function `run(state: AgentState) -> AgentState` với đúng signature. Tôi cũng cần `utils/normalize.py` (Tiến Đạt) hoạt động đúng vì `supervisor_node()` import từ đó.

---

## 5. Nếu có thêm 2 giờ, tôi sẽ làm gì? (50–100 từ)

Tôi sẽ thêm **confidence-based re-routing** vào `build_graph()`: nếu sau khi synthesis worker trả về `confidence < 0.5`, graph tự động trigger một vòng retrieval lại với query được reformulated. Eval report cho thấy avg_confidence = 0.889 trên 25 traces, nhưng một số câu retrieval-only vẫn chỉ đạt 0.72 — trace `run_20260414_164703_250731.json` cho thấy retrieval trả chunks từ đúng source nhưng top chunk chưa khớp chính xác nhất. Một vòng re-retrieval bổ sung có thể đẩy confidence lên 0.85+ cho các edge case này.

---
