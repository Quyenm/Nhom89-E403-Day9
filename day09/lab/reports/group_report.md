# Báo Cáo Nhóm — Lab Day 09: Multi-Agent Orchestration

**Tên nhóm:** Nhóm 89  
**Thành viên:**
| Tên | Vai trò | Email |
|-----|---------|-------|
| Hùng | Supervisor Owner / Sprint lead | tranngochungb046@gmail.com |
| An | Worker Owner | anduongtrinhhoai@gmail.com |
| Thắng | Worker Owner | buiducthang2005@gmail.com |
| Dũng | Worker Owner | vuquangdung71104@gmail.com |
| Nguyễn Đạt | MCP Owner | nguyendatdtqn@gmail.com |
| Nguyễn Mạnh Quyền | Trace & Docs Owner | mnquyen26@gmail.com |

**Ngày nộp:** 14/04/2026  
**Repo:** `Nhom89-E403-Day9/day09/lab`  
**Độ dài khuyến nghị:** 600–1000 từ

---

## 1. Kiến trúc nhóm đã xây dựng

Nhóm triển khai kiến trúc Supervisor-Worker gồm 1 supervisor và 3 worker chính: `retrieval_worker`, `policy_tool_worker`, `synthesis_worker`, kèm 1 nhánh `human_review` để xử lý trường hợp rủi ro cao. Luồng chạy trong `graph.py` bắt đầu từ `make_initial_state()` để tạo shared state, sau đó `supervisor_node()` gán `supervisor_route`, `route_reason`, `risk_high`, `needs_tool`, rồi route sang worker phù hợp. Sau khi worker domain xử lý, `synthesis_worker` luôn được gọi để tổng hợp `final_answer`, `sources` và `confidence`.  

Routing logic hiện tại là rule-based bằng keyword thay vì classifier bằng LLM. Câu chứa tín hiệu về policy hoặc access như “hoàn tiền”, “flash sale”, “level 3”, “contractor” sẽ đi vào `policy_tool_worker`; câu thiên về SLA/ticket như “P1”, “SLA”, “ticket”, “incident” đi vào `retrieval_worker`. Trường hợp chứa mã lỗi dạng `ERR-` sẽ bật `risk_high` và đi qua `human_review` trước khi tiếp tục retrieve. Ví dụ trace `run_20260414_155535_518408.json` cho câu `ERR-403-AUTH là lỗi gì và cách xử lý?` ghi rõ `route_reason = "unknown error code + risk_high → human review | human approved → retrieval"`.

MCP tools đã tích hợp:
- `search_kb`: được `policy_tool_worker` gọi để lấy top-k chunks khi `needs_tool=True`; ví dụ trace `run_20260414_155535_533941.json` có call `search_kb` cho câu về “Contractor cần Admin Access (Level 3)...`.
- `get_ticket_info`: cũng xuất hiện trong trace trên với input `ticket_id = "P1-LATEST"` và trả về `created_at = "2026-04-13T22:47:00"`, `notifications_sent = ["slack:#incident-p1", "email:incident@company.internal", "pagerduty:oncall"]`.
- `check_access_permission`: đã implement trong `mcp_server.py` để mở rộng cho các truy vấn access-control, dù trong trace grading hiện tại chưa phải tool được gọi thường xuyên nhất.

## 2. Quyết định kỹ thuật quan trọng nhất

**Quyết định:** Ưu tiên routing rule-based + fallback offline thay vì phụ thuộc hoàn toàn vào ChromaDB và LLM ngay từ đầu.

**Bối cảnh vấn đề:** Skeleton Day 09 yêu cầu hệ thống vừa route đúng, vừa trace được, vừa chạy end-to-end trong môi trường lab. Tuy nhiên lúc triển khai thực tế có hai rủi ro rõ ràng: phụ thuộc vào `chromadb`/embedding model có thể làm pipeline không chạy được trên máy chưa setup đủ; và nếu dùng LLM cho cả routing lẫn synthesis thì latency tăng mạnh, khó debug từng bước. Nhóm cần một thiết kế đủ ổn định để `python eval_trace.py` chạy được ngay khi grading file được public lúc 17:00.

**Các phương án đã cân nhắc:**

| Phương án | Ưu điểm | Nhược điểm |
|-----------|---------|-----------|
| Dùng ChromaDB + LLM hoàn toàn | Grounding và câu trả lời đẹp hơn khi môi trường đầy đủ | Dễ fail do thiếu dependency/API key; khó giữ latency ổn định |
| Rule-based routing + lexical retrieval fallback + synthesis grounded | Chạy ổn định offline, trace dễ đọc, debug nhanh | Chất lượng answer multi-hop và temporal scoping chưa thật sâu |

**Phương án đã chọn và lý do:** Nhóm chọn phương án thứ hai vì phù hợp mục tiêu lab: hoàn thiện flow Supervisor-Worker, MCP và trace trước, rồi mới tối ưu chất lượng answer. Kết quả grading thực tế 10/10 câu chạy thành công cho thấy lựa chọn này giữ hệ thống bền hơn trong môi trường thi.

**Bằng chứng từ trace/code:**

```text
graph.py:
- "task contains policy/access keyword" -> policy_tool_worker
- "task contains SLA/ticket keyword" -> retrieval_worker

Trace run_20260414_155535_533941.json:
- supervisor_route: "policy_tool_worker"
- mcp_tools_used: ["search_kb", "get_ticket_info"]
- latency_ms: 4
```

## 3. Kết quả grading questions

Theo log chạy lúc 17:00, pipeline xử lý thành công `10/10` grading questions và xuất `artifacts/grading_run.jsonl`. Ở mức vận hành, đây là tín hiệu tốt vì không có câu nào crash hoặc rơi vào `PIPELINE_ERROR`. Log phân tích trace đi kèm cho thấy `avg_confidence = 0.889`, `avg_latency_ms = 2014`, `mcp_usage_rate = 12/25 (48%)`, `retrieval_worker = 13/25`, `policy_tool_worker = 12/25`.  

**Tổng điểm raw ước tính:** UNCONFIRMED / 96. Nhóm chưa có script chấm raw chính thức, nên không thể điền số tuyệt đối mà không đoán. Tuy vậy, dựa trên việc 10/10 câu đều trả lời được, có thể xem đây là một run ổn định và có mức đúng dự kiến khá cao.

**Câu pipeline xử lý tốt nhất:**  
ID: `gq03` — Lý do tốt: route đúng sang `policy_tool_worker`, confidence `0.95`, và dạng truy vấn “Level 3 access” khớp rất rõ với logic access-control + MCP.

**Câu pipeline fail hoặc partial:**  
ID: `gq07` — Fail ở đâu: truy vấn hỏi “mức phạt tài chính cụ thể khi đội IT vi phạm SLA P1 resolution” nhiều khả năng không có dữ liệu trong tài liệu. Hệ thống vẫn trả lời với confidence `0.84`, nên đây là dấu hiệu abstain chưa đủ chặt.  
Root cause: lexical retrieval vẫn kéo được chunk liên quan đến SLA, nhưng synthesis chưa có luật từ chối đủ mạnh khi evidence không khớp hoàn toàn với yêu cầu “mức phạt tài chính”.

**Câu gq07 (abstain):** Nhóm hiện chưa abstain tốt. Trace từ case `ERR-403-AUTH` cũng cho thấy hệ thống có HITL nhưng synthesis vẫn cố trả lời từ chunk gần nhất thay vì từ chối rõ ràng.

**Câu gq09 (multi-hop khó nhất):** Hệ thống route sang `policy_tool_worker` và có gọi MCP, nhưng trace hiện chỉ ghi `policy_tool_worker -> synthesis_worker`, chưa có hai domain worker độc lập cùng xuất hiện. Kết quả vẫn chạy ổn định với confidence `0.95`, nhưng đây là điểm nhóm còn có thể cải thiện nếu muốn multi-hop thật sự rõ hơn.

## 4. So sánh Day 08 vs Day 09 — Điều nhóm quan sát được

Điểm thay đổi rõ nhất là khả năng quan sát route và worker-level trace. Day 08 là single-agent nên khi answer sai rất khó xác định lỗi nằm ở retrieve, policy hay synthesis. Sang Day 09, mỗi trace đều có `supervisor_route`, `route_reason`, `workers_called`, `mcp_tools_used`, `worker_io_logs`. Nhờ đó nhóm có thể giải thích ngay vì sao câu `Contractor cần Admin Access (Level 3)...` đi vào `policy_tool_worker` và vì sao `get_ticket_info` được gọi thêm.

Số liệu thực tế từ run grading cho thấy `avg_confidence = 0.889` và route phân bố khá cân bằng: `retrieval_worker 13/25 (52%)`, `policy_tool_worker 12/25 (48%)`. Điều nhóm bất ngờ nhất là multi-agent không nhất thiết chậm ở mỗi câu: nhiều câu policy chỉ mất `13–33ms`, trong khi câu đầu tiên phải load model mới lên tới hơn `11s`. Nút thắt chính vì thế không nằm ở routing logic mà ở cold-start của embedding stack.

Trường hợp multi-agent chưa giúp rõ là các câu cần abstain hoặc temporal scoping sâu. Ví dụ câu order ngày `31/01/2026` vẫn có nguy cơ bị kéo về rule Flash Sale nếu retrieval lấy chunk sai, và case `ERR-403-AUTH` cho thấy có HITL nhưng cuối cùng synthesis vẫn trả lời bằng chunk gần nhất. Điều này cho thấy thêm worker chưa đủ; cần thêm guardrail cho “không đủ thông tin”.

## 5. Phân công và đánh giá nhóm

**Phân công thực tế:**

| Thành viên | Phần đã làm | Sprint |
|------------|-------------|--------|
| Hùng | `graph.py`, supervisor routing, state orchestration | 1 |
| An | `workers/retrieval.py`, retrieval contract | 2 |
| Thắng | `workers/policy_tool.py`, policy analysis | 2 |
| Dũng | `workers/synthesis.py`, final answer generation | 2 |
| Nguyễn Đạt | `mcp_server.py`, MCP tools và tích hợp tool call | 3 |
| Nguyễn Mạnh Quyền | `eval_trace.py`, docs trong `day09/lab/docs`, reports | 4 |

**Điều nhóm làm tốt:** Phân vai theo sprint khá rõ, mỗi module đều có output kiểm tra được. Khi grading questions được public, nhóm chạy được ngay và có trace để nhìn lại.

**Điều nhóm làm chưa tốt hoặc gặp vấn đề về phối hợp:** Một số phần logic cross-document chưa thật sự nối với nhau; trace cho multi-hop còn thiên về “một worker chính + synthesis” hơn là hai worker domain phối hợp rõ ràng.

**Nếu làm lại, nhóm sẽ thay đổi gì trong cách tổ chức?** Nhóm sẽ chốt contract trace sớm hơn và có một bộ test grading-like trước 17:00 để phát hiện sớm lỗi abstain, temporal scoping và multi-hop.

## 6. Nếu có thêm 1 ngày, nhóm sẽ làm gì?

Nếu có thêm 1 ngày, nhóm sẽ ưu tiên 2 việc. Thứ nhất, siết điều kiện abstain trong `synthesis_worker` vì trace của `gq07` và `ERR-403-AUTH` cho thấy hệ thống còn trả lời khi evidence không đủ khớp. Thứ hai, bổ sung route từ `policy_tool_worker` sang `retrieval_worker` hoặc ngược lại cho các câu multi-hop như `gq09`, để trace thể hiện rõ hai worker domain cùng tham gia thay vì chỉ dựa vào một worker chính gọi MCP.

---

*File này lưu tại: `reports/group_report.md`*  

