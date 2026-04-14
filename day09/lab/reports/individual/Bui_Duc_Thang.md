# Báo Cáo Cá Nhân — Lab Day 09: Multi-Agent Orchestration

**Họ và tên:** Bùi Đức Thắng  
**Vai trò trong nhóm:** Worker Owner 
**Ngày nộp:** 15/04/2026  
**Độ dài yêu cầu:** 500–800 từ

---

> **Lưu ý quan trọng:**
> - Viết ở ngôi **"tôi"**, gắn với chi tiết thật của phần bạn làm
> - Phải có **bằng chứng cụ thể**: tên file, đoạn code, kết quả trace, hoặc commit
> - Nội dung phân tích phải khác hoàn toàn với các thành viên trong nhóm
> - Deadline: Được commit **sau 18:00** (xem SCORING.md)
> - Lưu file với tên: `reports/individual/[ten_ban].md` (VD: `nguyen_van_a.md`)

---

## 1. Tôi phụ trách phần nào? (100–150 từ)

> Mô tả cụ thể module, worker, contract, hoặc phần trace bạn trực tiếp làm.
> Không chỉ nói "tôi làm Sprint X" — nói rõ file nào, function nào, quyết định nào.

**Module/file tôi chịu trách nhiệm:**
- File chính: `policy_tool`
- Functions tôi implement: `_normalize`, `_call_mcp_tool`, `_extract_access_level`, `_is_emergency`, `analyze_policy`, `run`

**Cách công việc của tôi kết nối với phần của thành viên khác:**


Phần việc của tôi kết nối chặt chẽ với supervisor node do thành viên khác phụ trách: supervisor quyết định route sang `policy_tool_worker`, còn tôi chịu trách nhiệm đảm bảo worker xử lý đúng policy và log đầy đủ `mcp_tools_used`, `route_reason` để phục vụ trace.


**Bằng chứng (commit hash, file có comment tên bạn, v.v.):**

file `workers/policy_tool.py` trong repo.

---

## 2. Tôi đã ra một quyết định kỹ thuật gì? (150–200 từ)

>Tôi chọn thiết kế `policy_tool` theo hướng **rule-based deterministic reasoning**, chỉ gọi MCP tool khi thật sự có tín hiệu cần thiết, thay vì phụ thuộc vào LLM để phân tích policy.
>
Cụ thể, trong `run()`, tôi chỉ gọi:
- `search_kb` khi `needs_tool=True` hoặc không có chunk,
- `check_access_permission` khi `_extract_access_level()` trả về access level,
- `get_ticket_info` khi task có token như `ticket`, `p1`, `incident`.

**Các lựa chọn thay thế:**  
Một lựa chọn khác là gọi MCP cho mọi câu hỏi policy hoặc dùng LLM để classify intent trước. Tuy nhiên, cách đó làm tăng latency và giảm khả năng debug.

**Lý do chọn cách này:**  
Rule-based giúp pipeline:
- Chạy nhanh và ổn định
- Dễ trace nguyên nhân – kết quả
- Phù hợp với policy nội bộ có cấu trúc rõ

**Trade-off:**  
Cách này có thể miss các phrasing lạ không chứa keyword, nhưng tôi chấp nhận trade-off đó để đổi lấy hiệu năng và tính xác định.






**Bằng chứng từ trace/code:**

```
[03] gq03 route=policy_tool_worker conf=0.95 latency=31ms
mcp_tools_used=["search_kb","check_access_permission"]
```

---

## 3. Tôi đã sửa một lỗi gì? (150–200 từ)

> Mô tả 1 bug thực tế bạn gặp và sửa được trong lab hôm nay.
> Phải có: mô tả lỗi, symptom, root cause, cách sửa, và bằng chứng trước/sau.

**Lỗi:** Logic ban đầu trong policy_tool khiến **MCP search_kb bị gọi ngay cả khi đã có retrieved_chunks**, làm tăng latency không cần thiết.


**Symptom (pipeline làm gì sai?):**

Trong các lần chạy đầu, nhiều câu policy đơn giản vẫn có `mcp_tools_used=["search_kb"]`, latency cao hơn mong đợi.


**Root cause (lỗi nằm ở đâu — indexing, routing, contract, worker logic?):**

Trong `analyze_policy`, điều kiện gọi `search_kb` là `if not retrieved_chunks or not retrieved_chunks[0].get("text")`. Điều này có nghĩa là ngay cả khi supervisor đã gọi `search_kb` và trả về chunks, worker vẫn gọi lại `search_kb` nếu không kiểm tra kỹ `retrieved_chunks`.
(Điều kiện gọi `search_kb` chưa kiểm tra đầy đủ trạng thái dữ liệu đầu vào).

**Cách sửa:**

Tôi chỉnh lại điều kiện trong `run()`:
```python
if needs_tool or not chunks:
    kb_call = _call_mcp_tool("search_kb", ...)
```

**Bằng chứng trước/sau:**
Trước sửa (test nội bộ):
mcp_tools_used=["search_kb"]
latency > 70ms

Sau sửa (trace chính thức):
[04] gq04 route=policy_tool_worker conf=0.95 latency=14ms
mcp_tools_used=[]

Latency giảm rõ rệt và behavior đúng hơn.

---

## 4. Tôi tự đánh giá đóng góp của mình (100–150 từ)

> Trả lời trung thực — không phải để khen ngợi bản thân.

Tôi làm tốt nhất ở điểm nào?
Tôi làm tốt ở việc thiết kế worker có reasoning rõ ràng, có log, có trace, và tránh lạm dụng MCP. Mọi quyết định trong policy_tool đều có thể giải thích ngược lại từ code và trace.
Tôi làm chưa tốt ở điểm nào?
Rule-based keyword matching vẫn còn giới hạn coverage (ví dụ các cách diễn đạt khác “hoàn tiền”, “refund”). Tôi chưa có thời gian cải thiện phần này.
Nhóm phụ thuộc vào tôi ở đâu?
Nếu policy_tool chưa xong, supervisor route đúng nhưng pipeline sẽ không xử lý được policy/access questions, làm hỏng gần nửa hệ thống.
Phần tôi phụ thuộc vào thành viên khác:
Tôi phụ thuộc vào supervisor để set đúng needs_tool và schema trace thống nhất.


---

## 5. Nếu có thêm 2 giờ, tôi sẽ làm gì? (50–100 từ)

> Nếu có thêm 2 giờ, tôi sẽ bổ sung cơ chế giảm confidence cho policy decisions thuần keyword. Dựa trên trace, nhiều câu policy có conf=0.95 dù không gọi MCP xác minh. Tôi sẽ gợi ý supervisor giảm confidence trong các tình huống này để phản ánh đúng mức độ chắc chắn của rule-based reasoning.

---

