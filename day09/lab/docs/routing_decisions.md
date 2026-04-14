# Routing Decisions Log — Lab Day 09

**Nhóm:** Nhóm 89  
**Ngày:** 14/04/2026

---

## Routing Decision #1

**Task đầu vào:**
> `Ticket P1 được tạo lúc 22:47. Ai sẽ nhận thông báo đầu tiên và qua kênh nào? Escalation xảy ra lúc mấy giờ?`

**Worker được chọn:** `retrieval_worker`  
**Route reason (từ trace):** `task contains SLA/ticket keyword`  
**MCP tools được gọi:** Không có  
**Workers called sequence:** `retrieval_worker -> synthesis_worker`

**Kết quả thực tế:**
- final_answer (ngắn): trích được chunk SLA P1, nêu first response 15 phút, resolution 4 giờ, escalation sau 10 phút
- confidence: `0.58`
- Correct routing? Yes

**Nhận xét:** Routing đúng vì câu hỏi bản chất là SLA/ticket lookup. Tuy nhiên retrieval còn kéo thêm `access_control_sop.txt` và `policy_refund_v4.txt`, nên synthesis có citation hơi dư. Đây là dấu hiệu retrieval nên có rerank tốt hơn.

---

## Routing Decision #2

**Task đầu vào:**
> `Contractor cần Admin Access (Level 3) để khắc phục sự cố P1 đang active. Quy trình cấp quyền tạm thời như thế nào?`

**Worker được chọn:** `policy_tool_worker`  
**Route reason (từ trace):** `task contains policy/access keyword`  
**MCP tools được gọi:** `search_kb`, `get_ticket_info`  
**Workers called sequence:** `policy_tool_worker -> synthesis_worker`

**Kết quả thực tế:**
- final_answer (ngắn): trả lời theo chunk escalation của `access_control_sop.txt`
- confidence: `0.59`
- Correct routing? Yes, nhưng chưa đủ

**Nhận xét:** Đây là routing đúng ở mức supervisor vì câu hỏi chứa access-control rõ ràng. Tuy vậy, đây cũng là ví dụ cho thấy route một worker là chưa đủ cho multi-hop: câu hỏi có cả SLA P1 và access tạm thời, nhưng trace chưa gọi thêm `retrieval_worker`. Nhóm coi đây là case cần cải thiện nếu có thêm thời gian.

---

## Routing Decision #3

**Task đầu vào:**
> `ERR-403-AUTH là lỗi gì và cách xử lý?`

**Worker được chọn:** `human_review`  
**Route reason (từ trace):** `unknown error code + risk_high → human review | human approved → retrieval`  
**MCP tools được gọi:** Không có  
**Workers called sequence:** `human_review -> retrieval_worker -> synthesis_worker`

**Kết quả thực tế:**
- final_answer (ngắn): trả về nội dung gần nhất từ refund/SLA thay vì abstain rõ ràng
- confidence: `0.50`
- Correct routing? Yes

**Nhận xét:** Đây là routing tốt nhất về mặt guardrail vì supervisor nhận diện đúng trường hợp thiếu context và kích hoạt HITL. Tuy nhiên sau khi auto-approve, retrieval vẫn tìm nhầm chunk gần nhất, nên answer cuối chưa đúng kỳ vọng. Root cause không nằm ở route mà ở logic abstain của synthesis.

---

## Routing Decision #4 (tuỳ chọn — bonus)

**Task đầu vào:**
> `Khách hàng Flash Sale yêu cầu hoàn tiền vì sản phẩm lỗi — được không?`

**Worker được chọn:** `policy_tool_worker`  
**Route reason:** `task contains policy/access keyword`

**Nhận xét: Đây là trường hợp routing khó nhất trong lab. Tại sao?**

Về routing thì case này không khó, nhưng nó là test tốt cho chất lượng policy exception. Trace cho thấy `policy_tool_worker` phát hiện đúng `flash_sale_exception` và synthesis trả về `Đơn hàng Flash Sale không được hoàn tiền (Điều 3, chính sách v4)`. Đây là ví dụ cho thấy route đúng + policy exception rõ sẽ cho answer gọn và confidence cao hơn.

---

## Tổng kết

### Routing Distribution

| Worker | Số câu được route | % tổng |
|--------|------------------|--------|
| retrieval_worker | 13 | 52% |
| policy_tool_worker | 12 | 48% |
| human_review | 0 trong grading run, 1 case ở test set | 0% grading / có xuất hiện ở test set |

### Routing Accuracy

- Câu route đúng: `10 / 10` grading questions ở mức supervisor chọn đúng nhánh domain chính
- Câu route sai (đã sửa bằng cách nào?): không thấy crash hoặc route lệch hoàn toàn trong grading run; vấn đề còn lại là answer quality sau route
- Câu trigger HITL: `0` trong grading run; `1` case trong test set (`ERR-403-AUTH`)

### Lesson Learned về Routing

1. Rule-based routing đủ tốt cho bộ câu hỏi hiện tại vì domain signal rất rõ: SLA/ticket khác hẳn refund/access.
2. `route_reason` cần ngắn nhưng cụ thể để debug nhanh; format hiện tại đã đủ dùng, nhưng có thể thêm `matched_keywords` để trace giải thích tốt hơn.

### Route Reason Quality

Nhìn chung `route_reason` hiện đủ để debug tầng supervisor. Ví dụ `task contains SLA/ticket keyword` và `task contains policy/access keyword` giúp nhóm biết ngay query đi đâu. Điểm còn thiếu là chưa log keyword cụ thể nào match, nên khi route chưa tối ưu cho câu multi-hop thì khó biết supervisor đã thiên về tín hiệu nào mạnh hơn.
