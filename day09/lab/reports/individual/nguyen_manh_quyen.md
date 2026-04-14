# Báo Cáo Cá Nhân — Lab Day 09: Multi-Agent Orchestration

**Họ và tên:** Nguyễn Mạnh Quyền  
**MSSV:** 2A202600481  
**Vai trò trong nhóm:** Trace & Docs Owner  
**Ngày nộp:** 14/04/2026  
**Độ dài yêu cầu:** 500–800 từ

---

## 1. Tôi phụ trách phần nào?

Trong Lab Day 09, tôi phụ trách phần trace, tài liệu và tổng hợp kết quả nhóm. File chính tôi làm là `day09/lab/eval_trace.py`, cùng với ba file tài liệu trong `day09/lab/docs/` và phần báo cáo trong `day09/lab/reports/`. Ở `eval_trace.py`, tôi chịu trách nhiệm các hàm `run_test_questions()`, `run_grading_questions()`, `analyze_traces()`, `compare_single_vs_multi()` và `save_eval_report()`. Mục tiêu của phần tôi là biến kết quả chạy pipeline thành bằng chứng có thể đọc được: trace theo từng câu, phân bố route, mức confidence, latency, mức dùng MCP và báo cáo so sánh Day 08 với Day 09.

Công việc của tôi phụ thuộc trực tiếp vào phần của các bạn khác. Tôi chỉ có thể hoàn thiện trace khi supervisor đã ghi `route_reason`, worker đã append `workers_called`, và MCP đã log `mcp_tools_used`. Ngược lại, phần của tôi cũng kết nối ngược lại với toàn nhóm vì nếu `eval_trace.py` không chạy ổn thì nhóm không có grading log, không có số liệu để viết docs, và không có bằng chứng để giải thích vì sao một route hoặc worker là đúng/sai.

**Bằng chứng:** `day09/lab/eval_trace.py`, `day09/lab/docs/system_architecture.md`, `day09/lab/docs/routing_decisions.md`, `day09/lab/docs/single_vs_multi_comparison.md`, `day09/lab/reports/group_report.md`.

---

## 2. Tôi đã ra một quyết định kỹ thuật gì?

**Quyết định:** Tôi chọn chuẩn hoá output trace và đường dẫn file theo `day09/lab` thay vì để script phụ thuộc vào current working directory hoặc encoding mặc định của Windows.

Lý do tôi chọn cách này là vì phần trace/eval chỉ có giá trị khi chạy ổn định trong giờ grading. Nếu `eval_trace.py` chỉ chạy được ở một thư mục nhất định hoặc mở trace bằng encoding mặc định `cp1252`, pipeline rất dễ vỡ dù logic worker vẫn đúng. Trong quá trình kiểm thử thực tế, tôi gặp lỗi `UnicodeDecodeError` khi đọc lại trace JSON và phải sửa sang mở file bằng `encoding="utf-8"`. Tôi cũng chuẩn hóa các biến đường dẫn như `BASE_DIR`, `ARTIFACTS_DIR`, `TRACES_DIR` để script không bị lệch khi chạy từ root repo.

Trade-off tôi chấp nhận là file `eval_trace.py` dài hơn một chút và phải cẩn thận hơn về path management. Bù lại, phần trace trở nên ổn định và tái sử dụng được. Tác động của quyết định này thấy rõ ở chỗ sau khi sửa path + UTF-8, lệnh `python day09\lab\eval_trace.py` chạy hết `15/15` test questions và xuất được `day09/lab/artifacts/eval_report.json`.

**Bằng chứng từ trace/code:**

```python
BASE_DIR = os.path.dirname(__file__)
ARTIFACTS_DIR = os.path.join(BASE_DIR, "artifacts")
TRACES_DIR = os.path.join(ARTIFACTS_DIR, "traces")

with open(os.path.join(traces_dir, fname), encoding="utf-8") as f:
    traces.append(json.load(f))
```

---

## 3. Tôi đã sửa một lỗi gì?

**Lỗi:** `eval_trace.py` chạy xong phần pipeline nhưng fail ở bước phân tích trace do mở file JSON bằng encoding mặc định của Windows.

**Symptom:** Pipeline in ra `15 / 15 succeeded`, nhưng ngay sau đó văng lỗi `UnicodeDecodeError: 'charmap' codec can't decode byte ...` khi gọi `analyze_traces()`. Điều này nguy hiểm vì nhìn bên ngoài tưởng hệ thống đã chạy xong, nhưng thực ra phần báo cáo cuối không được tạo hoàn chỉnh.

**Root cause:** Root cause nằm ở phần trace reading chứ không phải ở routing hay worker logic. Các file trace được lưu UTF-8 bằng `json.dump(..., ensure_ascii=False)`, nhưng ở bước đọc lại tôi để `open()` không chỉ định encoding. Trên môi trường Windows console, Python dùng `cp1252`, dẫn đến lỗi khi gặp ký tự tiếng Việt.

**Cách sửa:** Tôi sửa `eval_trace.py` để luôn mở trace bằng `encoding="utf-8"`, đồng thời chuẩn hóa path theo `BASE_DIR` để tránh lỗi tương đối giữa root repo và thư mục lab. Sau đó tôi chạy lại `python day09\lab\eval_trace.py` và script hoàn thành toàn bộ, in được phần `Trace Analysis` và tạo report cuối.

**Bằng chứng trước/sau:**

- Trước khi sửa: `15 / 15 succeeded` nhưng fail ở `json.load()` với `UnicodeDecodeError`.
- Sau khi sửa: script in đầy đủ `avg_confidence`, `avg_latency_ms`, `mcp_usage_rate`, `top_sources`, rồi lưu `Eval report -> day09/lab/artifacts/eval_report.json`.

---

## 4. Tôi tự đánh giá đóng góp của mình

Điểm tôi làm tốt nhất là biến phần “chạy được” thành phần “có thể chứng minh được”. Với vai trò Trace & Docs Owner, tôi không tạo ra worker mới, nhưng tôi giúp cả nhóm có chỗ để nhìn lại route, trace, metrics và chuyển chúng thành tài liệu nộp. Tôi cũng khá mạnh ở việc nối code với evidence, nên khi nhóm cần viết report thì không phải mô tả chung chung.

Điểm tôi làm chưa tốt là chưa đẩy phần so sánh Day 08 vs Day 09 đến mức có số liệu đối chiếu đầy đủ cho cả hai phía. Trong tài liệu so sánh, một số ô vẫn phải ghi `N/A` vì chưa có run Day 08 tương ứng trong cùng turn. Nếu có thêm thời gian, tôi cần chủ động chạy lại baseline sớm hơn thay vì đợi sát giờ grading.

Nhóm phụ thuộc vào tôi ở phần grading log, `eval_report.json`, và các file docs/report. Nếu tôi chưa xong, nhóm vẫn có code nhưng rất khó nộp phần giải thích. Ngược lại, tôi phụ thuộc vào supervisor, worker và MCP của các bạn khác vì nếu state không log đúng thì phần trace của tôi cũng không phân tích được gì.

---

## 5. Nếu có thêm 2 giờ, tôi sẽ làm gì?

Tôi sẽ cải tiến đúng một điểm: thêm kiểm tra “abstain fidelity” vào `eval_trace.py` và scorecard. Lý do là trace của `ERR-403-AUTH` và confidence của `gq07` cho thấy hệ thống còn trả lời khi evidence không đủ khớp. Nếu tôi có thêm 2 giờ, tôi sẽ thêm một metric riêng để đánh dấu các câu đáng ra phải từ chối nhưng pipeline vẫn cố trả lời, vì đây là điểm nhóm còn yếu nhất khi nhìn từ trace.

---

*Lưu file này với tên: `reports/individual/nguyen_manh_quyen.md`*
