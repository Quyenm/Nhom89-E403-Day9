"""
mcp_server.py — Real HTTP MCP Server (Advanced implementation)

Upgrade từ mock-class sang FastAPI HTTP server thực sự.
Implements MCP-compatible REST interface:
  GET  /          → health check
  GET  /tools     → list available tools
  POST /tools/call → execute a tool by name

Bug fix (NTD): phiên bản gốc import retrieve_dense ở module level:
    from workers.retrieval import retrieve_dense
Khi chạy `python mcp_server.py` từ thư mục khác hoặc spawn như subprocess,
Python không tìm thấy package 'workers' → ModuleNotFoundError.
Fix: dùng lazy import bên trong hàm tool_search_kb() sau khi sys.path đã
được thiết lập đúng.

Author: Nguyễn Tiến Đạt - 2A202600217
"""

from __future__ import annotations

import os
import sys
from datetime import datetime
from typing import Any

# ── Path setup (lazy-import fix) ─────────────────────────────────────────────
_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(
    title="Lab Day 09 — MCP Tool Server",
    description="HTTP MCP server exposing KB search, ticket lookup, and access permission check.",
    version="2.0.0",
)

TOOL_SCHEMAS: dict[str, dict] = {
    "search_kb": {
        "name": "search_kb",
        "description": "Search the internal Knowledge Base and return relevant document chunks.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "top_k": {"type": "integer", "default": 3},
            },
            "required": ["query"],
        },
    },
    "get_ticket_info": {
        "name": "get_ticket_info",
        "description": "Fetch details of an incident ticket from the mock ticket system.",
        "inputSchema": {
            "type": "object",
            "properties": {"ticket_id": {"type": "string"}},
            "required": ["ticket_id"],
        },
    },
    "check_access_permission": {
        "name": "check_access_permission",
        "description": "Evaluate access request requirements based on the Access Control SOP.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "access_level": {"type": "integer"},
                "requester_role": {"type": "string"},
                "is_emergency": {"type": "boolean", "default": False},
            },
            "required": ["access_level", "requester_role"],
        },
    },
    "create_ticket": {
        "name": "create_ticket",
        "description": "Create a mock Jira ticket for incident tracking.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "priority": {"type": "string"},
                "title": {"type": "string"},
                "description": {"type": "string", "default": ""},
            },
            "required": ["priority", "title"],
        },
    },
}

MOCK_TICKETS: dict[str, dict] = {
    "P1-LATEST": {
        "ticket_id": "IT-9847",
        "priority": "P1",
        "status": "in_progress",
        "assignee": "nguyen.van.a@company.internal",
        "created_at": "2026-04-13T22:47:00",
        "sla_deadline": "2026-04-14T02:47:00",
        "escalated": True,
        "escalated_to": "senior_engineer_team",
        "notifications_sent": [
            "slack:#incident-p1",
            "email:incident@company.internal",
            "pagerduty:oncall",
        ],
    },
    "IT-1234": {
        "ticket_id": "IT-1234",
        "priority": "P2",
        "status": "open",
        "assignee": None,
        "created_at": "2026-04-13T09:15:00",
        "sla_deadline": "2026-04-14T09:15:00",
        "notifications_sent": [],
    },
}

ACCESS_RULES: dict[int, dict] = {
    1: {
        "required_approvers": ["Line Manager"],
        "emergency_override": False,
        "notes": ["Level 1 follows the standard approval path."],
    },
    2: {
        "required_approvers": ["Line Manager", "IT Admin"],
        "emergency_override": True,
        "notes": [
            "Level 2 emergency access can be granted temporarily for up to 24 hours.",
            "The temporary grant must be audit logged.",
        ],
    },
    3: {
        "required_approvers": ["Line Manager", "IT Admin", "IT Security"],
        "emergency_override": False,
        "notes": ["Level 3 has no emergency bypass and still requires full approvals."],
    },
    4: {
        "required_approvers": ["IT Manager", "CISO"],
        "emergency_override": False,
        "notes": ["Level 4 requires security training and standard approval."],
    },
}


def tool_search_kb(query: str, top_k: int = 3) -> dict:
    # Lazy import: tránh ModuleNotFoundError khi server chạy như subprocess
    from workers.retrieval import retrieve_dense  # noqa: PLC0415
    chunks = retrieve_dense(query, top_k=top_k)
    return {
        "chunks": chunks,
        "sources": sorted({chunk["source"] for chunk in chunks}),
        "total_found": len(chunks),
    }


def tool_get_ticket_info(ticket_id: str) -> dict:
    result = MOCK_TICKETS.get(ticket_id.upper())
    if result is None:
        return {
            "error": f"Ticket '{ticket_id}' không tìm thấy.",
            "available_mock_ids": sorted(MOCK_TICKETS),
        }
    return result


def tool_check_access_permission(
    access_level: int,
    requester_role: str,
    is_emergency: bool = False,
) -> dict:
    rule = ACCESS_RULES.get(access_level)
    if not rule:
        return {"error": f"Access level {access_level} không hợp lệ. Hợp lệ: 1-4."}
    notes = list(rule["notes"])
    if requester_role.lower() == "contractor":
        notes.append("Contractor requests must still be recorded in Jira and audit logs.")
    if is_emergency and rule["emergency_override"]:
        notes.append("Emergency route is allowed with concurrent approval from Line Manager and IT Admin on-call.")
    elif is_emergency and not rule["emergency_override"]:
        notes.append("Emergency context does not change the approval chain for this level.")
    return {
        "access_level": access_level,
        "can_grant": True,
        "required_approvers": rule["required_approvers"],
        "approver_count": len(rule["required_approvers"]),
        "emergency_override": bool(is_emergency and rule["emergency_override"]),
        "notes": notes,
        "source": "access_control_sop.txt",
    }


def tool_create_ticket(priority: str, title: str, description: str = "") -> dict:
    ticket_id = f"IT-{9900 + (abs(hash(title)) % 99)}"
    return {
        "ticket_id": ticket_id,
        "url": f"https://jira.company.internal/browse/{ticket_id}",
        "created_at": datetime.now().isoformat(),
        "priority": priority,
        "title": title,
        "description": description[:200],
        "note": "Mock ticket created for lab only.",
    }


TOOL_REGISTRY: dict[str, Any] = {
    "search_kb": tool_search_kb,
    "get_ticket_info": tool_get_ticket_info,
    "check_access_permission": tool_check_access_permission,
    "create_ticket": tool_create_ticket,
}


class ToolCallRequest(BaseModel):
    tool: str
    input: dict = {}


@app.get("/")
def health_check():
    """Health check."""
    return {
        "status": "ok",
        "server": "Lab Day 09 MCP Tool Server",
        "version": "2.0.0",
        "tools_available": list(TOOL_REGISTRY),
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/tools")
def list_tools_endpoint():
    """List available tools (MCP spec compatible)."""
    return {"tools": list(TOOL_SCHEMAS.values())}


@app.post("/tools/call")
def call_tool(req: ToolCallRequest):
    """
    Execute a tool by name.
    Body: {"tool": "search_kb", "input": {"query": "SLA P1", "top_k": 3}}
    """
    if req.tool not in TOOL_REGISTRY:
        raise HTTPException(
            status_code=404,
            detail={"error": f"Tool '{req.tool}' không tồn tại.", "available": sorted(TOOL_REGISTRY)},
        )
    error = None
    output = None
    try:
        output = TOOL_REGISTRY[req.tool](**req.input)
        if isinstance(output, dict) and "error" in output:
            error = output["error"]
    except TypeError as exc:
        error = {"code": "INVALID_INPUT", "reason": str(exc)}
    except Exception as exc:
        error = {"code": "TOOL_EXECUTION_FAILED", "reason": str(exc)}
    return {
        "tool": req.tool,
        "input": req.input,
        "output": output,
        "error": error,
        "timestamp": datetime.now().isoformat(),
    }


# ── Backwards-compat shim for eval_trace.py and tests ────────────────────────

def list_tools() -> list:
    return list(TOOL_SCHEMAS.values())


def dispatch_tool(tool_name: str, tool_input: dict) -> dict:
    """Direct Python call — no HTTP overhead. Used by eval_trace and standalone tests."""
    if tool_name not in TOOL_REGISTRY:
        return {"error": f"Tool '{tool_name}' không tồn tại.", "available": sorted(TOOL_REGISTRY)}
    try:
        return TOOL_REGISTRY[tool_name](**tool_input)
    except TypeError as exc:
        return {"error": f"Invalid input for tool '{tool_name}': {exc}"}
    except Exception as exc:
        return {"error": f"Tool '{tool_name}' execution failed: {exc}"}


MCP_HOST = os.getenv("MCP_HOST", "127.0.0.1")
MCP_PORT = int(os.getenv("MCP_PORT", "8765"))

if __name__ == "__main__":
    print(f"Starting MCP HTTP server at http://{MCP_HOST}:{MCP_PORT}")
    print(f"  GET  http://{MCP_HOST}:{MCP_PORT}/          -> health")
    print(f"  GET  http://{MCP_HOST}:{MCP_PORT}/tools     -> list tools")
    print(f"  POST http://{MCP_HOST}:{MCP_PORT}/tools/call -> call tool")
    uvicorn.run(app, host=MCP_HOST, port=MCP_PORT, log_level="info")