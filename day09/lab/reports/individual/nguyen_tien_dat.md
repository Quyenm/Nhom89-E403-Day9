# Báo Cáo Cá Nhân — Lab Day 09: Multi-Agent Orchestration

**Họ và tên:** Nguyễn Tiến Đạt

**MSSV:** 2A202600217

**Vai trò trong nhóm:** MCP Owner

**Ngày nộp:** 2026-04-14

---

## 1. Tôi phụ trách phần nào?

Tôi đảm nhận vai trò **MCP Owner** với trách nhiệm chính là Sprint 3: thiết kế và triển khai MCP server, sau đó tích hợp vào `workers/policy_tool.py`.

**Module/file tôi chịu trách nhiệm:**

- File chính: `mcp_server.py` — nâng cấp từ mock Python class lên **FastAPI HTTP server thật** với ba endpoint: `GET /`, `GET /tools`, `POST /tools/call`
- File phụ: `workers/policy_tool.py` — cập nhật hàm `_call_mcp_tool()` để gọi MCP qua HTTP client (`httpx`), có fallback về direct dispatch khi server chưa chạy
- File mới: `utils/normalize.py` — tách hàm `_normalize()` dùng chung thành module riêng (xem Bug #1 bên dưới)

**Cách công việc của tôi kết nối với phần của thành viên khác:**

`policy_tool_worker` do Bùi Đức Thắng xây dựng gọi hàm `_call_mcp_tool()` mà tôi implement; Trace & Docs Owner đọc field `mcp_tools_used` trong state để tính `mcp_usage_rate`. Nếu tôi chưa xong Sprint 3, Sprint 4 sẽ không có dữ liệu MCP thực trong trace.

**Bằng chứng:**

Comment `# Author: Nguyễn Tiến Đạt - 2A202600217` trong `mcp_server.py` và `utils/normalize.py`. FastAPI routes xác nhận bằng lệnh:
```
python -c "from mcp_server import app; print([r.path for r in app.routes])"
# ['/openapi.json', '/docs', '/', '/tools', '/tools/call']
```

---

## 2. Tôi đã ra một quyết định kỹ thuật gì?

**Quyết định:** Dùng `httpx` HTTP client với env-var `MCP_SERVER_URL` để gọi MCP, thay vì giữ `from mcp_server import dispatch_tool` ở mọi nơi.

Khi bắt đầu Sprint 3, có hai hướng để `policy_tool.py` dùng MCP:

| Phương án | Mô tả | Trade-off |
|-----------|-------|-----------|
| **A — Direct import** | `from mcp_server import dispatch_tool` (cách gốc) | Đơn giản nhưng coupling cao; không thể swap MCP implementation mà không sửa worker |
| **B — HTTP client + fallback** | `httpx.post(MCP_URL/tools/call)`, fallback về direct call nếu không có URL | Loose coupling, đúng tinh thần MCP spec; cần handle timeout và lỗi mạng |

Tôi chọn phương án B vì MCP spec được thiết kế để tools chạy như **external service**, không phải library được import trực tiếp. Nếu giữ direct import, việc nâng cấp lên MCP server thật sau này sẽ cần sửa cả worker.

**Trade-off đã chấp nhận:** Phương án B phức tạp hơn một chút — cần xử lý `ConnectionRefusedError` khi server chưa chạy. Tôi giải quyết bằng fallback về `dispatch_tool()` local khi `MCP_SERVER_URL` không được set, nên `eval_trace.py` vẫn chạy được mà không cần khởi động HTTP server.

**Bằng chứng từ trace (câu gq-style q15):**

```json
{
  "mcp_tools_used": [
    {"tool": "search_kb",              "input": {"query": "...", "top_k": 4}},
    {"tool": "check_access_permission","input": {"access_level": 2, "requester_role": "contractor", "is_emergency": true}},
    {"tool": "get_ticket_info",         "input": {"ticket_id": "P1-LATEST"}}
  ],
  "supervisor_route": "policy_tool_worker",
  "route_reason": "policy/access intent detected; high-risk operational context; MCP enabled"
}
```

---

## 3. Tôi đã sửa một lỗi gì?

**Tôi gặp và sửa hai lỗi trong Sprint 3.**

### Bug #1 — `_normalize()` duplicated across 4 files

**Symptom:** Khi tôi cần chỉnh sửa logic normalize (thêm xử lý ký tự `ơ` variant bị thiếu), tôi nhận ra hàm này tồn tại nguyên xi trong `graph.py`, `workers/retrieval.py`, `workers/policy_tool.py` và `workers/synthesis.py`. Thay đổi ở một file không tự động áp dụng sang ba file kia.

**Root cause:** Copy-paste từ Sprint 1 sang Sprint 2 mà không tách module dùng chung.

**Cách sửa:** Tạo `utils/normalize.py` với hàm `normalize()` duy nhất, dùng pre-built `str.maketrans` table thay vì khởi tạo lại mỗi lần gọi.

**Bằng chứng trước/sau:**

Trước — mỗi file có ~30 dòng copy-paste giống nhau:
```python
# workers/policy_tool.py  (và 3 file khác)
def _normalize(text: str) -> str:
    replacements = str.maketrans({"à": "a", "á": "a", ...})  # 30+ dòng
    return re.sub(r"\s+", " ", text.lower().translate(replacements)).strip()
```

Sau — một source of truth:
```python
# utils/normalize.py
_VIET_TABLE = str.maketrans({"à": "a", "á": "a", ...})  # built once at import

def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().translate(_VIET_TABLE)).strip()
```

---

### Bug #2 — `ModuleNotFoundError` khi chạy `mcp_server.py` như subprocess

**Symptom:** Chạy `python mcp_server.py` từ terminal bình thường không lỗi, nhưng khi thử spawn server như một process con (hoặc chạy từ thư mục khác), nhận được:
```
ModuleNotFoundError: No module named 'workers'
```

**Root cause:** File gốc có `from workers.retrieval import retrieve_dense` ở **module level** (dòng 10). Khi Python khởi động `mcp_server.py` độc lập, `sys.path` chỉ include thư mục hiện tại, không phải thư mục gốc project.

**Cách sửa:** Hai bước — (1) thêm `sys.path` setup ở đầu file trước mọi import, (2) chuyển import `retrieve_dense` thành lazy import bên trong `tool_search_kb()`:

```python
# Fix ở đầu mcp_server.py
_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# Lazy import trong tool function
def tool_search_kb(query: str, top_k: int = 3) -> dict:
    from workers.retrieval import retrieve_dense  # import sau khi path đã setup
    chunks = retrieve_dense(query, top_k=top_k)
    ...
```

**Bằng chứng:** Sau fix, `python mcp_server.py` từ bất kỳ working directory nào đều start được:
```
Starting MCP HTTP server at http://127.0.0.1:8765
  GET  http://127.0.0.1:8765/          -> health
  GET  http://127.0.0.1:8765/tools     -> list tools
  POST http://127.0.0.1:8765/tools/call -> call tool
```

---

## 4. Tôi tự đánh giá đóng góp của mình

**Tôi làm tốt nhất ở điểm nào?**

Phần thiết kế interface HTTP cho MCP server. Việc giữ `dispatch_tool()` như backwards-compat shim giúp cả nhóm không phải refactor `eval_trace.py` và test cases — họ vẫn gọi như cũ trong khi server đã upgrade lên FastAPI.

**Tôi làm chưa tốt hoặc còn yếu ở điểm nào?**

Tôi chưa viết test tự động cho `_call_mcp_tool()` ở cả hai path (HTTP và fallback). Hiện tại chỉ test bằng tay qua `python workers/policy_tool.py`. Nếu có lỗi nhỏ trong HTTP response parsing, sẽ khó phát hiện sớm.

**Nhóm phụ thuộc vào tôi ở đâu?**

Field `mcp_tools_used` trong trace state là output trực tiếp từ `_call_mcp_tool()` mà tôi viết. Nếu format không đúng (thiếu key `tool`, `timestamp`, hoặc `output`), Trace & Docs Owner sẽ không thể tính `mcp_usage_rate` và Sprint 4 sẽ bị thiếu metrics.

**Phần tôi phụ thuộc vào thành viên khác:**

Tôi cần `workers/retrieval.py` (do Dương Trịnh Hoài An làm) để `tool_search_kb` có thể gọi `retrieve_dense`. Nếu interface của `retrieve_dense` thay đổi (signature hoặc return format), `tool_search_kb` cũng phải update theo.

---

## 5. Nếu có thêm 2 giờ, tôi sẽ làm gì?

Tôi sẽ thêm **retry logic với exponential backoff** vào `_call_mcp_tool()` cho HTTP path.

Lý do: trace của câu liên quan đến P1 (gq01, gq09) cho thấy policy worker gọi đồng thời 3 MCP tools (`search_kb`, `check_access_permission`, `get_ticket_info`). Trong môi trường production, nếu MCP server tạm thời quá tải ở tool đầu tiên, toàn bộ câu sẽ trả về `error: HTTP_MCP_CALL_FAILED` thay vì retry. Một đơn giản là thêm `max_retries=2, backoff=0.5s` — latency tăng tối đa ~1s trong worst case nhưng reliability tăng đáng kể cho câu multi-hop như gq09 (câu 16 điểm, đắt nhất trong grading).
