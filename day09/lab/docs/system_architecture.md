# System Architecture — Lab Day 09

**Nhóm:** Nhóm 89  
**Ngày:** 14/04/2026  
**Version:** 1.0

---

## 1. Tổng quan kiến trúc

**Pattern đã chọn:** Supervisor-Worker  
**Lý do chọn pattern này (thay vì single agent):**

Nhóm chọn Supervisor-Worker để tách rõ ba loại trách nhiệm: route quyết định ở supervisor, xử lý domain ở worker, và tổng hợp đầu ra ở synthesis. So với Day 08, cách tách này giúp trace tốt hơn và cho phép debug từng worker độc lập thay vì phải soi toàn bộ pipeline RAG như một khối đen. Mỗi câu hỏi đều đi qua `graph.py`, được gán `route_reason`, `supervisor_route`, `risk_high`, rồi mới chuyển tiếp sang worker tương ứng.

---

## 2. Sơ đồ Pipeline

**Sơ đồ thực tế của nhóm:**

```text
User Request
    |
    v
make_initial_state()
    |
    v
Supervisor (graph.py)
  - set supervisor_route
  - set route_reason
  - set risk_high / needs_tool
    |
    +--> human_review (neu task co ERR- va risk cao)
    |
    +--> retrieval_worker
    |      - lexical / dense retrieval
    |      - update retrieved_chunks, retrieved_sources
    |
    +--> policy_tool_worker
           - analyze policy exception
           - call MCP tools when needs_tool=True
           - update policy_result, mcp_tools_used
    |
    v
synthesis_worker
  - build grounded answer
  - add citations
  - set confidence
    |
    v
save_trace() / eval_trace.py
```

---

## 3. Vai trò từng thành phần

### Supervisor (`graph.py`)

| Thuộc tính | Mô tả |
|-----------|-------|
| **Nhiệm vụ** | Phân tích câu hỏi và chọn worker phù hợp |
| **Input** | `task` từ user |
| **Output** | `supervisor_route`, `route_reason`, `risk_high`, `needs_tool` |
| **Routing logic** | Rule-based bằng keyword: policy/access -> `policy_tool_worker`; SLA/ticket -> `retrieval_worker`; `ERR-` + risk -> `human_review` |
| **HITL condition** | Khi task chứa mã lỗi không rõ như `ERR-403-AUTH` và bị gắn `risk_high=True` |

### Retrieval Worker (`workers/retrieval.py`)

| Thuộc tính | Mô tả |
|-----------|-------|
| **Nhiệm vụ** | Tìm evidence từ `data/docs` và ghi vào state |
| **Embedding model** | Ưu tiên `sentence-transformers/all-MiniLM-L6-v2`, fallback lexical retrieval nếu thiếu dependency |
| **Top-k** | Mặc định `3` |
| **Stateless?** | Yes |

### Policy Tool Worker (`workers/policy_tool.py`)

| Thuộc tính | Mô tả |
|-----------|-------|
| **Nhiệm vụ** | Kiểm tra policy, phát hiện exception, gọi MCP tools khi cần |
| **MCP tools gọi** | `search_kb`, `get_ticket_info` |
| **Exception cases xử lý** | `flash_sale_exception`, `digital_product_exception`, `activated_exception`, temporal note cho order trước `01/02/2026` |

### Synthesis Worker (`workers/synthesis.py`)

| Thuộc tính | Mô tả |
|-----------|-------|
| **LLM model** | Ưu tiên `gpt-4o-mini` hoặc Gemini nếu có key; fallback rule-based grounded answer |
| **Temperature** | `0.1` khi gọi OpenAI |
| **Grounding strategy** | Chỉ dùng `retrieved_chunks` và `policy_result` trong state, thêm citation theo source |
| **Abstain condition** | Khi không có chunks hoặc answer phát hiện không đủ thông tin; hiện vẫn cần siết chặt thêm |

### MCP Server (`mcp_server.py`)

| Tool | Input | Output |
|------|-------|--------|
| search_kb | `query`, `top_k` | `chunks`, `sources`, `total_found` |
| get_ticket_info | `ticket_id` | ticket details |
| check_access_permission | `access_level`, `requester_role`, `is_emergency` | `can_grant`, `required_approvers`, `notes` |
| create_ticket | `priority`, `title`, `description` | `ticket_id`, `url`, `created_at` |

---

## 4. Shared State Schema

| Field | Type | Mô tả | Ai đọc/ghi |
|-------|------|-------|-----------|
| task | str | Câu hỏi đầu vào | supervisor đọc |
| supervisor_route | str | Worker được chọn | supervisor ghi |
| route_reason | str | Lý do route | supervisor ghi |
| risk_high | bool | Cờ rủi ro cao | supervisor ghi |
| needs_tool | bool | Có cần gọi MCP hay không | supervisor ghi |
| hitl_triggered | bool | Có đi qua HITL hay không | `human_review` ghi |
| retrieved_chunks | list | Evidence từ retrieval | retrieval/policy ghi, synthesis đọc |
| retrieved_sources | list | Danh sách nguồn tài liệu | retrieval ghi |
| policy_result | dict | Kết quả kiểm tra policy | policy_tool ghi, synthesis đọc |
| mcp_tools_used | list | Tool calls đã thực hiện | policy_tool ghi |
| final_answer | str | Câu trả lời cuối | synthesis ghi |
| sources | list | Nguồn dùng trong answer | synthesis ghi |
| confidence | float | Mức tin cậy | synthesis ghi |
| history | list | Dấu vết các bước | tất cả node append |
| workers_called | list | Trình tự worker đã gọi | workers append |
| latency_ms | int | Thời gian chạy của graph | graph ghi |
| run_id | str | ID duy nhất cho trace | graph ghi |
| timestamp | str | Mốc thời gian tạo run | graph ghi |

---

## 5. Lý do chọn Supervisor-Worker so với Single Agent (Day 08)

| Tiêu chí | Single Agent (Day 08) | Supervisor-Worker (Day 09) |
|----------|----------------------|--------------------------|
| Debug khi sai | Khó — không rõ lỗi ở đâu | Dễ hơn — test từng worker độc lập |
| Thêm capability mới | Phải sửa toàn prompt | Thêm worker hoặc MCP tool riêng |
| Routing visibility | Không có | Có `route_reason` trong trace |
| Tool integration | Hard-code trực tiếp | Gọi qua `mcp_server.py` và log trong `mcp_tools_used` |

**Nhóm điền thêm quan sát từ thực tế lab:**

Trong run grading, route phân bố khá cân bằng: `retrieval_worker 13/25 (52%)`, `policy_tool_worker 12/25 (48%)`. Điều này cho thấy pattern Supervisor-Worker phù hợp với bộ câu hỏi có cả SLA, refund, access-control và multi-hop.

---

## 6. Giới hạn và điểm cần cải tiến

1. Temporal scoping cho refund policy trước `01/02/2026` chưa đủ chặt; trace có thể vẫn kéo về chunk Flash Sale.
2. Abstain chưa mạnh: case `ERR-403-AUTH` vẫn trả lời từ chunk gần nhất thay vì từ chối rõ.
3. Multi-hop hiện thiên về một worker chính + MCP, chưa có nhiều trace thể hiện hai worker domain cùng phối hợp rõ ràng.
