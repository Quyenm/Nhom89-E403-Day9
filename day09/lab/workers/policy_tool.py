"""
workers/policy_tool.py — Policy & Tool Worker

Policy decisions remain grounded in local documents while external capability is
accessed through the mock MCP server.
"""

from __future__ import annotations

import os
import re
import sys
from datetime import datetime

WORKER_NAME = "policy_tool_worker"


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
    return re.sub(r"\s+", " ", text.lower().translate(replacements)).strip()


####################################################################################################################################
def _call_mcp_tool(tool_name: str, tool_input: dict) -> dict:
    """
    <Modded by NGUYỄN TIẾN ĐẠT - 2A202600217 - ENHANCE CALL MCP TOOL FUNCTION>
    Call MCP tool via HTTP if server is running, else fall back to direct dispatch.

    NTD: phiên bản gốc dùng dynamic sys.path + `from mcp_server import dispatch_tool`
    mỗi lần gọi. Khi mcp_server.py được nâng lên HTTP server thật, cách import trực tiếp
    không còn đúng với kiến trúc nữa. Thay bằng httpx HTTP client, với fallback về
    dispatch_tool() khi server chưa chạy (dùng trong unit test hoặc eval_trace).
    """
    mcp_url = os.getenv("MCP_SERVER_URL", "")

    if mcp_url:
        # ── HTTP path: gọi FastAPI MCP server ────────────────────────────────
        try:
            import httpx  # noqa: PLC0415
            response = httpx.post(
                f"{mcp_url}/tools/call",
                json={"tool": tool_name, "input": tool_input},
                timeout=5.0,
            )
            response.raise_for_status()
            data = response.json()
            return {
                "tool": data.get("tool", tool_name),
                "input": data.get("input", tool_input),
                "output": data.get("output"),
                "error": data.get("error"),
                "timestamp": data.get("timestamp", datetime.now().isoformat()),
            }
        except Exception as exc:
            return {
                "tool": tool_name,
                "input": tool_input,
                "output": None,
                "error": {"code": "HTTP_MCP_CALL_FAILED", "reason": str(exc)},
                "timestamp": datetime.now().isoformat(),
            }

    # ── Fallback: direct Python dispatch (no HTTP server required) ───────────
    workspace_root = os.path.dirname(os.path.dirname(__file__))
    if workspace_root not in sys.path:
        sys.path.insert(0, workspace_root)
    from mcp_server import dispatch_tool  # noqa: PLC0415

    try:
        result = dispatch_tool(tool_name, tool_input)
        return {
            "tool": tool_name,
            "input": tool_input,
            "output": result,
            "error": result.get("error") if isinstance(result, dict) else None,
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as exc:
        return {
            "tool": tool_name,
            "input": tool_input,
            "output": None,
            "error": {"code": "MCP_CALL_FAILED", "reason": str(exc)},
            "timestamp": datetime.now().isoformat(),
        }

####################################################################################################################################

def _extract_access_level(task: str) -> int | None:
    normalized = _normalize(task)
    match = re.search(r"level\s*(\d)", normalized)
    if match:
        return int(match.group(1))
    if "admin access" in normalized:
        return 3
    return None


def _is_emergency(task: str) -> bool:
    normalized = _normalize(task)
    return any(token in normalized for token in ("khan cap", "emergency", "p1", "incident", "2am"))


def analyze_policy(task: str, chunks: list, mcp_context: dict | None = None) -> dict:
    task_lower = _normalize(task)
    context_text = " ".join(chunk.get("text", "") for chunk in chunks)
    context_lower = _normalize(context_text)
    sources = sorted({chunk.get("source", "unknown") for chunk in chunks if chunk})

    exceptions_found = []
    policy_name = "general_policy_lookup"
    explanation = []
    policy_applies = True
    policy_version_note = ""

    if any(token in task_lower for token in ("refund", "hoan tien", "store credit", "flash sale", "license", "subscription")):
        policy_name = "refund_policy_v4"
        if "flash sale" in task_lower:
            exceptions_found.append(
                {
                    "type": "flash_sale_exception",
                    "rule": "Đơn hàng Flash Sale thuộc ngoại lệ không được hoàn tiền.",
                    "source": "policy_refund_v4.txt",
                }
            )
        if any(token in task_lower for token in ("license", "subscription", "ky thuat so", "digital")):
            exceptions_found.append(
                {
                    "type": "digital_product_exception",
                    "rule": "Sản phẩm kỹ thuật số như license key hoặc subscription không được hoàn tiền.",
                    "source": "policy_refund_v4.txt",
                }
            )
        if any(token in task_lower for token in ("da kich hoat", "da dang ky", "da su dung")):
            exceptions_found.append(
                {
                    "type": "activated_product_exception",
                    "rule": "Sản phẩm đã kích hoạt hoặc đăng ký tài khoản không được hoàn tiền.",
                    "source": "policy_refund_v4.txt",
                }
            )
        if any(token in task_lower for token in ("31/01/2026", "31/01", "truoc 01/02/2026", "truoc 01/02")):
            policy_applies = False
            policy_version_note = (
                "Đơn hàng được đặt trước ngày hiệu lực 01/02/2026 nên phải áp dụng policy v3, "
                "trong khi tài liệu hiện tại chỉ có v4."
            )
            explanation.append("temporal scoping requires v3 confirmation")
        if exceptions_found:
            policy_applies = False
            explanation.append("refund exception detected")
        if not explanation:
            explanation.append("refund request meets v4 rule set")

    access_level = _extract_access_level(task)
    if access_level:
        policy_name = f"access_control_level_{access_level}"
        access_result = (mcp_context or {}).get("access_result", {})
        if access_result:
            explanation.append("access rule evaluated via MCP check_access_permission")
            if access_result.get("emergency_override"):
                explanation.append("emergency override available")
            elif _is_emergency(task):
                explanation.append("no emergency override for this access level")
            if access_result.get("required_approvers"):
                sources = sorted(set(sources + [access_result.get("source", "access_control_sop.txt")]))
        else:
            explanation.append("access question without MCP context")

        if access_level >= 3 and _is_emergency(task):
            policy_applies = False
        if access_level == 2 and _is_emergency(task):
            policy_applies = True

    ticket_result = (mcp_context or {}).get("ticket_result", {})
    if ticket_result and not ticket_result.get("error"):
        explanation.append("ticket context fetched via MCP get_ticket_info")

    return {
        "policy_applies": policy_applies,
        "policy_name": policy_name,
        "exceptions_found": exceptions_found,
        "source": sources,
        "policy_version_note": policy_version_note,
        "rule": "; ".join(explanation) if explanation else "rule lookup complete",
        "explanation": "; ".join(explanation) if explanation else "no policy interpretation required",
        "access_result": (mcp_context or {}).get("access_result"),
        "ticket_result": ticket_result,
    }


def run(state: dict) -> dict:
    task = state.get("task", "")
    chunks = list(state.get("retrieved_chunks", []))
    needs_tool = state.get("needs_tool", False)

    state.setdefault("workers_called", [])
    state.setdefault("history", [])
    state.setdefault("mcp_tools_used", [])
    state.setdefault("worker_io_logs", [])
    state["workers_called"].append(WORKER_NAME)

    worker_io = {
        "worker": WORKER_NAME,
        "input": {"task": task, "chunks_count": len(chunks), "needs_tool": needs_tool},
        "output": None,
        "error": None,
    }

    try:
        normalized = _normalize(task)
        mcp_context: dict = {}

        if needs_tool or not chunks:
            kb_call = _call_mcp_tool("search_kb", {"query": task, "top_k": 4})
            state["mcp_tools_used"].append(kb_call)
            state["history"].append(f"[{WORKER_NAME}] MCP search_kb called")
            kb_output = kb_call.get("output") or {}
            kb_chunks = kb_output.get("chunks") or []
            if kb_chunks:
                existing = {(chunk["source"], chunk["text"]) for chunk in chunks}
                for chunk in kb_chunks:
                    key = (chunk["source"], chunk["text"])
                    if key not in existing:
                        chunks.append(chunk)
                        existing.add(key)
                state["retrieved_chunks"] = chunks
                state["retrieved_sources"] = sorted({chunk["source"] for chunk in chunks})

        access_level = _extract_access_level(task)
        if access_level:
            access_call = _call_mcp_tool(
                "check_access_permission",
                {
                    "access_level": access_level,
                    "requester_role": "contractor" if "contractor" in normalized else "employee",
                    "is_emergency": _is_emergency(task),
                },
            )
            state["mcp_tools_used"].append(access_call)
            state["history"].append(f"[{WORKER_NAME}] MCP check_access_permission called")
            mcp_context["access_result"] = access_call.get("output")

        if any(token in normalized for token in ("ticket", "p1", "incident")):
            ticket_call = _call_mcp_tool("get_ticket_info", {"ticket_id": "P1-LATEST"})
            state["mcp_tools_used"].append(ticket_call)
            state["history"].append(f"[{WORKER_NAME}] MCP get_ticket_info called")
            mcp_context["ticket_result"] = ticket_call.get("output")

        policy_result = analyze_policy(task, chunks, mcp_context=mcp_context)
        state["policy_result"] = policy_result

        worker_io["output"] = {
            "policy_applies": policy_result["policy_applies"],
            "exceptions_count": len(policy_result.get("exceptions_found", [])),
            "mcp_calls": len(state.get("mcp_tools_used", [])),
            "sources": policy_result.get("source", []),
        }
        state["history"].append(
            f"[{WORKER_NAME}] policy_applies={policy_result['policy_applies']} "
            f"exceptions={len(policy_result.get('exceptions_found', []))}"
        )
    except Exception as exc:
        worker_io["error"] = {"code": "POLICY_CHECK_FAILED", "reason": str(exc)}
        state["policy_result"] = {"error": str(exc)}
        state["history"].append(f"[{WORKER_NAME}] ERROR: {exc}")

    state["worker_io_logs"].append(worker_io)
    return state


if __name__ == "__main__":
    tests = [
        "Khách hàng Flash Sale yêu cầu hoàn tiền vì sản phẩm lỗi.",
        "Contractor cần Level 3 access để xử lý P1 khẩn cấp.",
        "Ticket P1 lúc 2am cần cấp Level 2 access tạm thời cho contractor.",
    ]
    for test in tests:
        result = run({"task": test, "needs_tool": True})
        print(f"\n▶ {test}")
        print(result["policy_result"])
