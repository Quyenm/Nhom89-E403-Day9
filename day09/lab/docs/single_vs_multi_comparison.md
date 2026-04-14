# Single Agent vs Multi-Agent Comparison — Lab Day 09

**Nhóm:** Nhóm 89  
**Ngày:** 14/04/2026

---

## 1. Metrics Comparison

| Metric | Day 08 (Single Agent) | Day 09 (Multi-Agent) | Delta | Ghi chú |
|--------|----------------------|---------------------|-------|---------|
| Avg confidence | N/A | 0.889 | N/A | Day 09 lấy từ grading trace mà nhóm chạy lúc 17:00 |
| Avg latency (ms) | N/A | 2014 | N/A | Câu đầu bị cold-start do load sentence-transformer |
| Abstain rate (%) | N/A | Chưa tốt | N/A | gq07 và case `ERR-403-AUTH` cho thấy còn thiếu guardrail |
| Multi-hop accuracy | N/A | Partial | N/A | gq09 chạy được nhưng trace chưa thể hiện 2 domain workers rõ |
| Routing visibility | ✗ Không có | ✓ Có `route_reason` | N/A | |
| Debug time (estimate) | 15–20 phút | 5–10 phút | giảm | Day 09 có trace + worker logs |

> Nhóm chưa có kết quả Day 08 chạy lại trên cùng bộ grading questions trong turn này, nên các ô Day 08 giữ `N/A` để tránh đoán số liệu.

---

## 2. Phân tích theo loại câu hỏi

### 2.1 Câu hỏi đơn giản (single-document)

| Nhận xét | Day 08 | Day 09 |
|---------|--------|--------|
| Accuracy | N/A | Tốt |
| Latency | N/A | Thấp sau cold-start |
| Observation | N/A | Các câu như đổi mật khẩu, remote work, SLA P1 đều route đúng và confidence ~0.88–0.89 |

**Kết luận:** Với câu hỏi một tài liệu, multi-agent không nhất thiết làm đúng hơn single-agent, nhưng nó làm câu trả lời dễ giải thích hơn vì biết rõ câu đó đi vào retrieval hay policy trước khi synthesis.

### 2.2 Câu hỏi multi-hop (cross-document)

| Nhận xét | Day 08 | Day 09 |
|---------|--------|--------|
| Accuracy | N/A | Partial |
| Routing visible? | ✗ | ✓ |
| Observation | N/A | gq09 route sang `policy_tool_worker`, có MCP call, nhưng chưa gọi thêm worker domain thứ hai rõ ràng |

**Kết luận:** Day 09 tốt hơn Day 08 ở khả năng nhìn thấy đường đi và lý do route, nhưng chưa tận dụng hết ưu thế multi-agent cho cross-document reasoning.

### 2.3 Câu hỏi cần abstain

| Nhận xét | Day 08 | Day 09 |
|---------|--------|--------|
| Abstain rate | N/A | Chưa đạt |
| Hallucination cases | N/A | Có nguy cơ partial answer |
| Observation | N/A | Case `ERR-403-AUTH` cho thấy route tốt nhưng synthesis vẫn trả lời từ chunk gần nhất |

**Kết luận:** Multi-agent giúp chèn HITL, nhưng nếu synthesis không có guardrail đủ mạnh thì vẫn chưa giải quyết triệt để bài toán abstain.

---

## 3. Debuggability Analysis

### Day 08 — Debug workflow
```text
Khi answer sai -> phải đọc toàn bộ RAG pipeline code -> tìm lỗi ở indexing/retrieval/generation
Không có trace -> không biết bắt đầu từ đâu
Thời gian ước tính: 15-20 phút
```

### Day 09 — Debug workflow
```text
Khi answer sai -> đọc trace -> xem supervisor_route + route_reason
  -> nếu route sai -> sửa supervisor routing logic
  -> nếu retrieval sai -> test retrieval_worker độc lập
  -> nếu synthesis sai -> test synthesis_worker độc lập
Thời gian ước tính: 5-10 phút
```

**Câu cụ thể nhóm đã debug:** case `ERR-403-AUTH`. Trace ghi rõ supervisor route vào `human_review`, sau đó `retrieval_worker` kéo nhầm chunk và `synthesis_worker` vẫn tạo answer. Nhờ đó nhóm xác định nhanh vấn đề nằm ở abstain logic, không nằm ở supervisor.

---

## 4. Extensibility Analysis

| Scenario | Day 08 | Day 09 |
|---------|--------|--------|
| Thêm 1 tool/API mới | Phải sửa toàn prompt | Thêm MCP tool + route rule |
| Thêm 1 domain mới | Phải retrain/re-prompt | Thêm 1 worker mới |
| Thay đổi retrieval strategy | Sửa trực tiếp trong pipeline | Sửa `retrieval_worker` độc lập |
| A/B test một phần | Khó — phải clone toàn pipeline | Dễ hơn — swap worker |

**Nhận xét:** Điểm mạnh nhất của Day 09 là khả năng thay đổi cục bộ. Ví dụ `mcp_server.py` thêm `get_ticket_info` mà không cần sửa core synthesis; trace sẽ tự ghi vào `mcp_tools_used`.

---

## 5. Cost & Latency Trade-off

| Scenario | Day 08 calls | Day 09 calls |
|---------|-------------|-------------|
| Simple query | 1 LLM call | 1 synthesis step, không cần MCP |
| Complex query | 1 LLM call | 1 policy step + 0-2 MCP calls + synthesis |
| MCP tool call | N/A | 1-2 tool calls tuỳ câu |

**Nhận xét về cost-benefit:** Day 09 tốn orchestration hơn, nhưng lợi ích lớn là trace, replaceability và tool integration. Ở grading run, nhiều câu policy chỉ mất `13–33ms`, còn latency trung bình bị đội lên chủ yếu vì cold-start của model embedding ở câu đầu tiên.

---

## 6. Kết luận

**Multi-agent tốt hơn single agent ở điểm nào?**

1. Có `route_reason`, `workers_called`, `mcp_tools_used` nên debug nhanh và có bằng chứng rõ.
2. Dễ mở rộng qua MCP hoặc thêm worker domain mà không phá toàn bộ pipeline.

**Multi-agent kém hơn hoặc không khác biệt ở điểm nào?**

1. Nếu synthesis chưa tốt, answer cuối vẫn có thể sai dù routing và trace đều đúng; tức là orchestration không tự động giải quyết hallucination.

**Khi nào KHÔNG nên dùng multi-agent?**

Khi bài toán chỉ là hỏi đáp một domain đơn giản, dữ liệu gọn và không cần tool integration hay observability sâu. Khi đó single-agent RAG đủ dùng và rẻ hơn.

**Nếu tiếp tục phát triển hệ thống này, nhóm sẽ thêm gì?**

Nhóm sẽ thêm guardrail abstain rõ ràng hơn trong synthesis, rerank ở retrieval, và route multi-hop thật sự giữa `retrieval_worker` và `policy_tool_worker` cho các câu như gq09.
