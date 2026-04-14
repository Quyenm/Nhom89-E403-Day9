# Báo Cáo Cá Nhân — Lab Day 09: Multi-Agent Orchestration

**Họ và tên:** Vũ Quang Dũng  
**Vai trò trong nhóm:** Worker Owner (Synthesis)  
**Ngày nộp:** 14/04/2026

---

## 1. Tôi phụ trách phần nào? (100–150 từ)

Tôi phụ trách chính file [day09/lab/workers/synthesis.py](day09/lab/workers/synthesis.py), là worker tổng hợp câu trả lời cuối cùng cho pipeline. Phần tôi làm nhận đầu vào từ state gồm `task`, `retrieved_chunks`, `policy_result`, sau đó trả ra `final_answer`, `sources`, `confidence` để supervisor ghi trace và hoàn tất vòng xử lý. Các hàm tôi trực tiếp implement gồm `_normalize`, `_find_time_plus_ten`, `_estimate_confidence`, `_answer_from_policy`, `_answer_from_retrieval`, `synthesize` và `run`. Vai trò của tôi kết nối trực tiếp với retrieval/policy worker: retrieval cung cấp chunks, policy cung cấp kết quả rule và exceptions, còn synthesis là lớp hợp nhất để câu trả lời có căn cứ và có trích dẫn nguồn. Bằng chứng code contribution là commit `0cbfa12` với message “synthesis worker”, thay đổi 1 file [day09/lab/workers/synthesis.py](day09/lab/workers/synthesis.py), tổng cộng +289/-175 dòng.

---

## 2. Tôi đã ra một quyết định kỹ thuật gì? (150–200 từ)

**Quyết định:** Tôi chọn hướng deterministic, rule-based synthesis thay cho cách gọi LLM trực tiếp ở worker tổng hợp.

Lúc triển khai, tôi có 2 lựa chọn: giữ `synthesis` phụ thuộc model bên ngoài (linh hoạt hơn), hoặc chuyển về logic thuần Python để đảm bảo tính ổn định và tái lập. Tôi chọn phương án thứ hai vì Day 09 chấm rất nặng yếu tố trace rõ ràng, anti-hallucination, và reproducibility. Trong code hiện tại, tôi đặt thứ tự xử lý rõ ràng: gọi `_answer_from_policy(...)` trước để xử lý các case có ràng buộc nghiệp vụ cao (refund exception, access level 2/3, emergency), sau đó fallback `_answer_from_retrieval(...)` cho FAQ/SLA/HR. Nếu vẫn không đủ điều kiện, worker trả về câu abstain có kiểm soát: “Không đủ thông tin...”.

**Trade-off tôi chấp nhận:** rule-based nhanh và ổn định nhưng độ phủ câu hỏi mở thấp hơn LLM; khi người dùng diễn đạt quá khác pattern, hệ thống có thể về nhánh abstain sớm. Dù vậy, trade-off này phù hợp với mục tiêu lab vì giảm rủi ro bịa thông tin và dễ debug. Bằng chứng nằm ngay trong [day09/lab/workers/synthesis.py](day09/lab/workers/synthesis.py): `synthesize(...)` luôn trả schema chuẩn và `_estimate_confidence(...)` giảm confidence khi thiếu evidence.

---

## 3. Tôi đã sửa một lỗi gì? (150–200 từ)

**Lỗi:** Worker synthesis từng phụ thuộc runtime LLM nên hành vi không ổn định theo môi trường chạy.

**Symptom:** Với phiên bản cũ, khi thiếu hoặc lỗi API key, worker dễ trả về thông báo lỗi kiểu `SYNTHESIS ERROR` thay vì câu trả lời nghiệp vụ. Ngay cả khi model gọi được, kết quả có thể dao động giữa các lần chạy cùng một câu hỏi, làm khó đối chiếu trace khi eval.

**Root cause:** Lớp tổng hợp cuối cùng phụ thuộc inference bên ngoài thay vì biến đổi có kiểm soát từ state nội bộ (`retrieved_chunks` + `policy_result`). Đây là lỗi ở worker logic, không phải ở routing hay indexing.

**Cách sửa:** Tôi bỏ hướng gọi model trong synthesis và thay bằng pipeline deterministic trong [day09/lab/workers/synthesis.py](day09/lab/workers/synthesis.py):
- chuẩn hóa tiếng Việt bằng `_normalize(...)` để matching ổn định,
- tách nhánh `_answer_from_policy(...)` và `_answer_from_retrieval(...)`,
- tính confidence theo bằng chứng bằng `_estimate_confidence(...)`,
- chuẩn hóa output trong `run(...)` gồm `final_answer`, `sources`, `confidence`, `worker_io_logs`, `history`.

**Bằng chứng trước/sau:** Commit `0cbfa12` thay đổi lớn cấu trúc worker theo hướng deterministic (+289/-175 dòng) và phiên bản hiện tại luôn có nhánh fallback “Không đủ thông tin...” thay vì đổ lỗi môi trường. Điều này giúp output tái lập tốt hơn khi chạy trace hàng loạt.

---

## 4. Tôi tự đánh giá đóng góp của mình (100–150 từ)

Điểm tôi làm tốt nhất là biến synthesis thành điểm chốt ổn định của hệ thống: câu trả lời có citation, có confidence, và có log đủ để debug. Nhờ đó, nhóm dễ truy vết vì sao một câu được trả lời theo hướng policy hay retrieval, thay vì chỉ nhìn đáp án cuối.

Điểm tôi còn hạn chế là coverage pattern chưa rộng; nhiều nhánh vẫn dựa keyword/intent cụ thể nên chưa tối ưu cho câu hỏi diễn đạt lạ. Về phụ thuộc nhóm, nếu synthesis chưa hoàn chỉnh thì pipeline khó đạt điểm cao ở các câu cần kết hợp nhiều nguồn vì thiếu lớp hợp nhất cuối. Ngược lại, phần tôi phụ thuộc vào chất lượng đầu vào từ retrieval/policy worker; nếu chunks yếu hoặc policy_result thiếu trường quan trọng thì confidence và độ chính xác câu trả lời sẽ giảm.

---

## 5. Nếu có thêm 2 giờ, tôi sẽ làm gì? (50–100 từ)

Tôi sẽ làm một cải tiến duy nhất: thêm lớp semantic fallback nhẹ trước khi vào rule cứng, ví dụ map một số cụm đồng nghĩa Việt/Anh cho cùng intent. Lý do là code hiện tại còn dựa khá nhiều vào token literal như `flash sale`, `store credit`, `level 2`, `2am`; khi người dùng đổi cách diễn đạt, worker dễ rơi vào abstain dù tài liệu có đủ thông tin. Cải tiến này vẫn giữ tính deterministic nhưng tăng coverage thực tế.