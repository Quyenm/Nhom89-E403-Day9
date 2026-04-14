"""
workers/retrieval.py — Retrieval Worker
Sprint 2: Implement retrieval từ ChromaDB, trả về chunks + sources.

Input (từ AgentState):
    - task: câu hỏi cần retrieve
    - (optional) retrieved_chunks nếu đã có từ trước

Output (vào AgentState):
    - retrieved_chunks: list of {"text", "source", "score", "metadata"}
    - retrieved_sources: list of source filenames
    - worker_io_log: log input/output của worker này

Gọi độc lập để test:
    python workers/retrieval.py
"""

from __future__ import annotations
import hashlib
import os
import re
from functools import lru_cache

WORKER_NAME = "retrieval_worker"
DEFAULT_TOP_K = 3
COLLECTION_NAME = "day09_docs"
CHROMA_PATH = "./chroma_db"
DOCS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "docs")
TOKEN_RE = re.compile(r"[a-z0-9#@:/.-]+", re.IGNORECASE)


def _normalize(text: str) -> str:
    replacements = str.maketrans(
        {
            "à": "a",
            "á": "a",
            "ạ": "a",
            "ả": "a",
            "ã": "a",
            "â": "a",
            "ầ": "a",
            "ấ": "a",
            "ậ": "a",
            "ẩ": "a",
            "ẫ": "a",
            "ă": "a",
            "ằ": "a",
            "ắ": "a",
            "ặ": "a",
            "ẳ": "a",
            "ẵ": "a",
            "è": "e",
            "é": "e",
            "ẹ": "e",
            "ẻ": "e",
            "ẽ": "e",
            "ê": "e",
            "ề": "e",
            "ế": "e",
            "ệ": "e",
            "ể": "e",
            "ễ": "e",
            "ì": "i",
            "í": "i",
            "ị": "i",
            "ỉ": "i",
            "ĩ": "i",
            "ò": "o",
            "ó": "o",
            "ọ": "o",
            "ỏ": "o",
            "õ": "o",
            "ô": "o",
            "ồ": "o",
            "ố": "o",
            "ộ": "o",
            "ổ": "o",
            "ỗ": "o",
            "ơ": "o",
            "ờ": "o",
            "ớ": "o",
            "ợ": "o",
            "ở": "o",
            "ỡ": "o",
            "ù": "u",
            "ú": "u",
            "ụ": "u",
            "ủ": "u",
            "ũ": "u",
            "ư": "u",
            "ừ": "u",
            "ứ": "u",
            "ự": "u",
            "ử": "u",
            "ữ": "u",
            "ỳ": "y",
            "ý": "y",
            "ỵ": "y",
            "ỷ": "y",
            "ỹ": "y",
            "đ": "d",
        }
    )
    lowered = text.lower().translate(replacements)
    return re.sub(r"\s+", " ", lowered).strip()


def _tokenize(text: str) -> set[str]:
    return set(TOKEN_RE.findall(_normalize(text)))

@lru_cache(maxsize=1)
def _load_chunks() -> list[dict]:
    chunks: list[dict] = []

    for filename in sorted(os.listdir(DOCS_DIR)):
        if not filename.endswith(".txt"):
            continue

        path = os.path.join(DOCS_DIR, filename)
        with open(path, encoding="utf-8") as handle:
            raw = handle.read().strip()

        sections = [section.strip() for section in re.split(r"\n(?=== )", raw) if section.strip()]
        for section_idx, section in enumerate(sections, start=1):
            blocks = [block.strip() for block in re.split(r"\n\s*\n", section) if block.strip()]
            for block_idx, block in enumerate(blocks, start=1):
                chunk_id = hashlib.md5(
                    f"{filename}:{section_idx}:{block_idx}:{block}".encode("utf-8")
                ).hexdigest()
                chunks.append(
                    {
                        "id": chunk_id,
                        "text": block,
                        "source": filename,
                        "metadata": {
                            "source": filename,
                            "path": path,
                            "section": section_idx,
                            "block": block_idx,
                        },
                    }
                )
    unique = []
    seen = set()
    for chunk in chunks:
        key = (chunk["source"], chunk["text"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(chunk)
    return unique

# ─────────────────────────────────────────────
# Worker Contract (xem contracts/worker_contracts.yaml)
# Input:  {"task": str, "top_k": int = 3}
# Output: {"retrieved_chunks": list, "retrieved_sources": list, "error": dict | None}
# ─────────────────────────────────────────────

@lru_cache(maxsize=1)
def _get_embedding_fn():
    """
    Trả về embedding function theo đúng TODO gốc:
    - ưu tiên Sentence Transformers
    - fallback sang OpenAI embeddings
    """
    try:
        from sentence_transformers import SentenceTransformer

        model = SentenceTransformer("all-MiniLM-L6-v2", local_files_only=True)

        def embed(text: str) -> list:
            return model.encode([text])[0].tolist()
        embed.provider = "sentence_transformers"  # type: ignore[attr-defined]
        return embed
    except Exception:
        pass

    try:
        from openai import OpenAI

        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        def embed(text: str) -> list:
            response = client.embeddings.create(input=text, model="text-embedding-3-small")
            return response.data[0].embedding
        embed.provider = "openai"  # type: ignore[attr-defined]
        return embed
    except Exception:
        return None


@lru_cache(maxsize=1)
def _get_collection():
    """
    Kết nối ChromaDB collection. Nếu collection trống thì tự index local docs.
    """
    import chromadb

    client = chromadb.PersistentClient(path=CHROMA_PATH)
    collection = client.get_or_create_collection(
        COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )
    _ensure_collection_populated(collection)
    return collection

def _ensure_collection_populated(collection) -> None:
    if collection.count() > 0:
        return

    embed = _get_embedding_fn()
    if embed is None:
        return

    chunks = _load_chunks()
    if not chunks:
        return

    collection.add(
        ids=[chunk["id"] for chunk in chunks],
        documents=[chunk["text"] for chunk in chunks],
        embeddings=[embed(chunk["text"]) for chunk in chunks],
        metadatas=[chunk["metadata"] for chunk in chunks],
    )


def _score_chunk_lexical(query: str, chunk_text: str, source: str) -> float:
    normalized_query = _normalize(query)
    query_tokens = _tokenize(query)
    chunk_tokens = _tokenize(chunk_text)
    if not query_tokens or not chunk_tokens:
        return 0.0

    overlap = len(query_tokens & chunk_tokens) / max(1, len(query_tokens))
    source_bonus = 0.0
    if "refund" in normalized_query and "refund" in source:
        source_bonus = 0.15
    elif "p1" in normalized_query and "sla" in source:
        source_bonus = 0.15
    elif ("access" in normalized_query or "level" in normalized_query) and "access_control" in source:
        source_bonus = 0.15
    elif ("remote" in normalized_query or "probation" in normalized_query) and "hr_leave" in source:
        source_bonus = 0.15
    elif ("mat khau" in normalized_query or "password" in normalized_query) and "it_helpdesk" in source:
        source_bonus = 0.15
    return min(1.0, round(overlap + source_bonus, 4))


def _retrieve_lexical(query: str, top_k: int) -> list:
    scored = []
    for chunk in _load_chunks():
        score = _score_chunk_lexical(query, chunk["text"], chunk["source"])
        if score <= 0:
            continue
        scored.append(
            {
                "text": chunk["text"],
                "source": chunk["source"],
                "score": score,
                "metadata": chunk["metadata"],
            }
        )

    scored.sort(key=lambda item: item["score"], reverse=True)
    return scored[:top_k]


def retrieve_dense(query: str, top_k: int = DEFAULT_TOP_K) -> list:
    """
    Dense retrieval theo TODO gốc:
    - embed query
    - query collection với n_results=top_k
    - format thành list of dict
    """
    embed = _get_embedding_fn()
    if embed is None:
        return _retrieve_lexical(query, top_k)

    try:
        collection = _get_collection()
        results = collection.query(
            query_embeddings=[embed(query)],
            n_results=top_k,
            include=["documents", "distances", "metadatas"],
        )

        documents = results.get("documents", [[]])[0]
        distances = results.get("distances", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]

        chunks = []
        for doc, dist, metadata in zip(documents, distances, metadatas):
            metadata = metadata or {}
            similarity = max(0.0, min(1.0, round(1 - float(dist), 4)))
            chunks.append(
                {
                    "text": doc,
                    "source": metadata.get("source", "unknown"),
                    "score": similarity,
                    "metadata": metadata,
                }
            )
        if chunks:
            return chunks
    except Exception:
        pass
    return _retrieve_lexical(query, top_k)


def run(state: dict) -> dict:
    task = state.get("task", "")
    top_k = state.get("retrieval_top_k", DEFAULT_TOP_K)

    state.setdefault("workers_called", [])
    state.setdefault("history", [])
    state.setdefault("worker_io_logs", [])
    state["workers_called"].append(WORKER_NAME)

    worker_io = {
        "worker": WORKER_NAME,
        "input": {"task": task, "top_k": top_k},
        "output": None,
        "error": None,
    }
    try:
        chunks = retrieve_dense(task, top_k=top_k)
        sources = sorted({chunk["source"] for chunk in chunks})
        state["retrieved_chunks"] = chunks
        state["retrieved_sources"] = sources
        worker_io["output"] = {
            "chunks_count": len(chunks),
            "sources": sources,
            "embedding_provider": getattr(_get_embedding_fn(), "provider", "lexical_fallback")
            if _get_embedding_fn()
            else "lexical_fallback",
        }
        state["history"].append(f"[{WORKER_NAME}] retrieved {len(chunks)} chunks from {sources}")
    except Exception as exc:
        state["retrieved_chunks"] = []
        state["retrieved_sources"] = []
        worker_io["error"] = {"code": "RETRIEVAL_FAILED", "reason": str(exc)}
        state["history"].append(f"[{WORKER_NAME}] ERROR: {exc}")

    state["worker_io_logs"].append(worker_io)
    return state


# ─────────────────────────────────────────────
# Test độc lập
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 50)
    print("Retrieval Worker — Standalone Test")
    print("=" * 50)

    tests = [
        "SLA ticket P1 là bao lâu?",
        "Điều kiện được hoàn tiền là gì?",
        "Ai phải phê duyệt để cấp quyền Level 3?",
    ]
    for test in tests:
        result = run({"task": test})
        print(f"\n▶ {test}")
        for chunk in result.get("retrieved_chunks", [])[:2]:
            print(f"  [{chunk['score']:.3f}] {chunk['source']}: {chunk['text'][:90]}...")
        print(f"  Sources: {result.get('retrieved_sources', [])}")
