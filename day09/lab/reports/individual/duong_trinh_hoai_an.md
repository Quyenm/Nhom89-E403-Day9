# Báo Cáo Cá Nhân — Lab Day 09: Multi-Agent Orchestration

**Họ và tên:** Dương Trịnh Hoài An 
**Vai trò trong nhóm:** Worker Owner  
**Ngày nộp:** 14/4/2026
**Độ dài yêu cầu:** 500–800 từ

---

## 1. Tôi phụ trách phần nào? (100–150 từ)

**Module/file tôi chịu trách nhiệm:**
- File chính: `day09/lab/workers/retrieval.py`
- Functions tôi implement: `_normalize`, `_tokenize`, `_load_chunks`, `_get_embedding_fn`, `_get_collection`, `_ensure_collection_populated`, `_score_chunk_lexical`, `_retrieve_lexical`, `retrieve_dense`, `run`

**Cách công việc của tôi kết nối với phần của thành viên khác:**

Tôi phụ trách `retrieval_worker`, tức worker lấy evidence từ knowledge base trước khi hệ thống tổng hợp câu trả lời. Trong `day09/lab/workers/retrieval.py`, tôi làm `retrieve_dense()` và các phần giúp worker chạy ổn định hơn như chuẩn hóa tiếng Việt, tách chunk từ tài liệu local, populate Chroma collection và ghi trace vào `worker_io_logs`. Phần của tôi nối trực tiếp với `day09/lab/contracts/worker_contracts.yaml`: supervisor route query sang retrieval, còn synthesis dùng `retrieved_chunks` và `retrieved_sources` do tôi trả về để tạo câu trả lời có căn cứ.

**Bằng chứng (commit hash, file có comment tên bạn, v.v.):**

Commit `b95b4c3 refactor(retrieval): submit retrieval workers`; diff cho thấy file `day09/lab/workers/retrieval.py` có `263 insertions` và `102 deletions`. Trong `run()` cũng có log `[retrieval_worker] retrieved ...` để trace đúng worker tôi phụ trách.

---

## 2. Tôi đã ra một quyết định kỹ thuật gì? (150–200 từ)

**Quyết định:** Tôi chọn hybrid retrieval: ưu tiên dense retrieval qua Chroma/embedding, nhưng luôn có lexical fallback thay vì phụ thuộc hoàn toàn vào embedding hoặc dùng random embeddings như bản cũ.

**Lý do:**

Tôi chọn cách này vì lab chạy trong môi trường không hoàn toàn ổn định: có lúc collection chưa build sẵn, có lúc embedding không sẵn ngay trên máy demo. Nếu retrieval phụ thuộc cứng vào Chroma thì chỉ cần một mắt xích lỗi là `retrieved_chunks` rỗng và synthesis mất evidence. Tôi cũng bỏ hướng random embeddings của bản cũ vì kết quả không deterministic. Với bộ tài liệu của lab chỉ có vài domain rõ như `sla`, `refund`, `access_control`, lexical fallback cộng `source_bonus` vẫn trả đúng file trong các query quan trọng.

**Trade-off đã chấp nhận:**

Trade-off tôi chấp nhận là logic lexical còn khá thủ công và hơi “biased” theo domain filename. Nó hợp với scope lab, nhưng nếu số tài liệu tăng thì scoring sẽ cần chỉnh lại.

**Bằng chứng từ trace/code:**

```
embed = _get_embedding_fn()
if embed is None:
    return _retrieve_lexical(query, top_k)

try:
    collection = _get_collection()
    ...
    if chunks:
        return chunks
except Exception:
    pass
return _retrieve_lexical(query, top_k)

Standalone test:
- "SLA ticket P1 là bao lâu?" -> `sla_p1_2026.txt` (score 0.634)
- "Điều kiện được hoàn tiền là gì?" -> `policy_refund_v4.txt` (score 0.716)
```

---

## 3. Tôi đã sửa một lỗi gì? (150–200 từ)

> Mô tả 1 bug thực tế bạn gặp và sửa được trong lab hôm nay.
> Phải có: mô tả lỗi, symptom, root cause, cách sửa, và bằng chứng trước/sau.

**Lỗi:** Ở phiên bản retrieval trước khi tôi refactor, worker có thể trả `retrieved_chunks=[]` hoặc cho ra evidence không ổn định khi collection chưa có data hoặc khi embedding không sẵn.

**Symptom (pipeline làm gì sai?):**

Symptom rõ nhất là pipeline phía sau mất context để trả lời grounded. Ở bản cũ, nếu `collection.query()` lỗi thì worker trả luôn danh sách rỗng; còn nếu thiếu điều kiện embedding thì code rơi về random embeddings. Kết quả là synthesis hoặc không có gì để cite, hoặc retrieval cho ra kết quả không nhất quán giữa các lần chạy.

**Root cause (lỗi nằm ở đâu — indexing, routing, contract, worker logic?):**

Root cause nằm ở worker logic và indexing strategy. Bản cũ giả định collection `day09_docs` đã được build sẵn, nhưng `_get_collection()` chỉ cảnh báo chứ không tự nạp dữ liệu. Đồng thời `_get_embedding_fn()` còn giữ nhánh random embeddings, và `retrieve_dense()` có `except Exception as e: return []`.

**Cách sửa:**

Tôi sửa theo hướng làm worker tự đứng vững hơn. Tôi thêm `_load_chunks()` để đọc `day09/lab/data/docs/*.txt`, `_ensure_collection_populated()` để tự index local docs khi collection rỗng, bỏ random embeddings và thay bằng lexical fallback qua `_retrieve_lexical()`. Tôi cũng thêm `_normalize()` để scoring ổn định hơn với tiếng Việt và query không dấu. Sau khi sửa, worker vẫn trả được evidence ngay cả khi dense path không usable.

**Bằng chứng trước/sau:**
> Dán trace/log/output trước khi sửa và sau khi sửa.

Trước khi sửa (từ bản cũ của `retrieval.py`):

```python
# Fallback: random embeddings cho test
import random
def embed(text: str) -> list:
    return [random.random() for _ in range(384)]

except Exception as e:
    print(f"⚠️  ChromaDB query failed: {e}")
    return []
```

Sau khi sửa:

```text
▶ Điều kiện được hoàn tiền là gì?
  [0.716] policy_refund_v4.txt ...
  Sources: ['policy_refund_v4.txt']
```

---

## 4. Tôi tự đánh giá đóng góp của mình (100–150 từ)

> Trả lời trung thực — không phải để khen ngợi bản thân.

**Tôi làm tốt nhất ở điểm nào?**

Tôi làm tốt nhất ở chỗ biến một TODO worker thành module chạy độc lập và có trace rõ để nhóm dùng tiếp. Tôi cũng làm cho retrieval dễ debug hơn nhờ `worker_io_logs`, `history` và `sources` được chuẩn hóa.

**Tôi làm chưa tốt hoặc còn yếu ở điểm nào?**

Tôi chưa tối ưu tốt phần ranking ở mức chunk. Trace câu “Ai phải phê duyệt để cấp quyền Level 3?” đã vào đúng file `access_control_sop.txt`, nhưng top chunk đầu tiên vẫn là đoạn khá tổng quát về `Level 1`.

**Nhóm phụ thuộc vào tôi ở đâu?** _(Phần nào của hệ thống bị block nếu tôi chưa xong?)_

Nhóm phụ thuộc vào tôi ở chỗ mọi câu trả lời grounded đều cần evidence đầu vào. Nếu retrieval chưa xong thì synthesis không có chunk để cite.

**Phần tôi phụ thuộc vào thành viên khác:** _(Tôi cần gì từ ai để tiếp tục được?)_

Tôi phụ thuộc vào contract và routing của supervisor để query đi đúng worker, và phụ thuộc vào chất lượng tài liệu trong `data/docs` để retrieval có dữ liệu tốt.

---

## 5. Nếu có thêm 2 giờ, tôi sẽ làm gì? (50–100 từ)

> Nêu **đúng 1 cải tiến** với lý do có bằng chứng từ trace hoặc scorecard.
> Không phải "làm tốt hơn chung chung" — phải là:
> *"Tôi sẽ thử X vì trace của câu gq___ cho thấy Y."*

Nếu có thêm 2 giờ, tôi sẽ thêm một bước rerank nhẹ cho các query có entity cụ thể như `Level 3` và `phê duyệt`. Lý do là trace standalone cho thấy câu “Ai phải phê duyệt để cấp quyền Level 3?” đã vào đúng source `access_control_sop.txt`, nhưng chunk đứng đầu vẫn là đoạn `Level 1 — Read Only` với score `0.670`. Điều đó cho thấy worker đã tìm đúng document nhưng chưa ưu tiên đúng đoạn cần trả lời.

---