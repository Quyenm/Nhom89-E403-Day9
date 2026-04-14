"""
graph.py — Supervisor Orchestrator

Supervisor decides the main route, workers execute bounded tasks, and the full
state is preserved as a traceable run artifact.
"""

from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime
from typing import Literal, Optional, TypedDict

from workers.policy_tool import run as policy_tool_run
from workers.retrieval import run as retrieval_run
from workers.synthesis import run as synthesis_run


class AgentState(TypedDict):
    task: str
    route_reason: str
    risk_high: bool
    needs_tool: bool
    hitl_triggered: bool
    retrieved_chunks: list
    retrieved_sources: list
    policy_result: dict
    mcp_tools_used: list
    final_answer: str
    sources: list
    confidence: float
    history: list
    workers_called: list
    supervisor_route: str
    latency_ms: Optional[int]
    run_id: str
    worker_io_logs: list


POLICY_KEYWORDS = (
    "hoan tien",
    "refund",
    "flash sale",
    "store credit",
    "license",
    "subscription",
    "cap quyen",
    "access",
    "admin access",
    "level 2",
    "level 3",
    "level 4",
    "contractor",
)

RETRIEVAL_KEYWORDS = (
    "p1",
    "sla",
    "ticket",
    "escalation",
    "incident",
    "pagerduty",
    "mat khau",
    "password",
    "remote",
    "probation",
    "vpn",
)

HIGH_RISK_KEYWORDS = (
    "khan cap",
    "emergency",
    "2am",
    "ciso",
    "security",
)

ERR_PATTERN = re.compile(r"\berr[-\w]+\b", re.IGNORECASE)
TIME_PATTERN = re.compile(r"\b(\d{1,2}):(\d{2})\b")


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


def make_initial_state(task: str) -> AgentState:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    return {
        "task": task,
        "route_reason": "",
        "risk_high": False,
        "needs_tool": False,
        "hitl_triggered": False,
        "retrieved_chunks": [],
        "retrieved_sources": [],
        "policy_result": {},
        "mcp_tools_used": [],
        "final_answer": "",
        "sources": [],
        "confidence": 0.0,
        "history": [],
        "workers_called": [],
        "supervisor_route": "",
        "latency_ms": None,
        "run_id": f"run_{timestamp}",
        "worker_io_logs": [],
    }


def supervisor_node(state: AgentState) -> AgentState:
    task = state["task"]
    normalized = _normalize(task)
    route = "retrieval_worker"
    reasons = []
    needs_tool = False
    risk_high = False

    if any(keyword in normalized for keyword in POLICY_KEYWORDS):
        route = "policy_tool_worker"
        reasons.append("policy/access intent detected")
        needs_tool = True

    if any(keyword in normalized for keyword in RETRIEVAL_KEYWORDS) and route != "policy_tool_worker":
        route = "retrieval_worker"
        reasons.append("knowledge-base retrieval intent detected")

    if ERR_PATTERN.search(task):
        reasons.append("unknown error code detected")
        # Keep retrieval for abstainable lookup unless the question is explicitly high risk.
        if any(keyword in normalized for keyword in HIGH_RISK_KEYWORDS):
            route = "human_review"
            risk_high = True
            reasons.append("error code combined with high-risk context")

    if any(keyword in normalized for keyword in HIGH_RISK_KEYWORDS):
        risk_high = True
        reasons.append("high-risk operational context")

    if TIME_PATTERN.search(task) and ("p1" in normalized or "ticket" in normalized):
        reasons.append("time-sensitive incident question")

    if not reasons:
        reasons.append("default to retrieval for factual lookup")

    reasons.append("MCP enabled" if needs_tool else "no MCP required")
    route_reason = "; ".join(reasons)

    state["supervisor_route"] = route
    state["route_reason"] = route_reason
    state["needs_tool"] = needs_tool
    state["risk_high"] = risk_high
    state["history"].append(f"[supervisor] task={task}")
    state["history"].append(f"[supervisor] route={route} reason={route_reason}")
    return state


def route_decision(state: AgentState) -> Literal["retrieval_worker", "policy_tool_worker", "human_review"]:
    return state.get("supervisor_route", "retrieval_worker")  # type: ignore[return-value]


def human_review_node(state: AgentState) -> AgentState:
    state["hitl_triggered"] = True
    state["workers_called"].append("human_review")
    state["history"].append("[human_review] auto-approved in lab mode")
    state["supervisor_route"] = "retrieval_worker"
    state["route_reason"] += "; human review fallback approved -> retrieval_worker"
    return state


def _requires_cross_doc_support(task: str) -> bool:
    normalized = _normalize(task)
    return (
        ("p1" in normalized or "sla" in normalized or "ticket" in normalized)
        and ("access" in normalized or "cap quyen" in normalized or "level " in normalized)
    )


def retrieval_worker_node(state: AgentState) -> AgentState:
    return retrieval_run(state)


def policy_tool_worker_node(state: AgentState) -> AgentState:
    return policy_tool_run(state)


def synthesis_worker_node(state: AgentState) -> AgentState:
    return synthesis_run(state)


def build_graph():
    def run(state: AgentState) -> AgentState:
        start = time.time()

        state = supervisor_node(state)
        route = route_decision(state)

        if route == "human_review":
            state = human_review_node(state)
            route = route_decision(state)

        if route == "policy_tool_worker":
            # Multi-hop policy questions benefit from evidence first.
            if _requires_cross_doc_support(state["task"]):
                state = retrieval_worker_node(state)
            state = policy_tool_worker_node(state)
            if not state.get("retrieved_chunks"):
                state = retrieval_worker_node(state)
        else:
            state = retrieval_worker_node(state)

        state = synthesis_worker_node(state)
        state["latency_ms"] = int((time.time() - start) * 1000)
        state["history"].append(f"[graph] completed in {state['latency_ms']}ms")
        return state

    return run


_graph = build_graph()


def run_graph(task: str) -> AgentState:
    return _graph(make_initial_state(task))


def save_trace(state: AgentState, output_dir: str = "./artifacts/traces") -> str:
    os.makedirs(output_dir, exist_ok=True)
    filename = os.path.join(output_dir, f"{state['run_id']}.json")
    with open(filename, "w", encoding="utf-8") as handle:
        json.dump(state, handle, ensure_ascii=False, indent=2)
    return filename


if __name__ == "__main__":
    print("=" * 60)
    print("Day 09 Lab — Supervisor-Worker Graph")
    print("=" * 60)

    test_queries = [
        "SLA xử lý ticket P1 là bao lâu?",
        "Khách hàng Flash Sale yêu cầu hoàn tiền vì sản phẩm lỗi — được không?",
        "Ticket P1 lúc 2am. Cần cấp Level 2 access tạm thời cho contractor để emergency fix.",
    ]

    for query in test_queries:
        result = run_graph(query)
        print(f"\n▶ Query: {query}")
        print(f"  Route      : {result['supervisor_route']}")
        print(f"  Reason     : {result['route_reason']}")
        print(f"  Workers    : {result['workers_called']}")
        print(f"  Confidence : {result['confidence']}")
        print(f"  Answer     : {result['final_answer']}")
        print(f"  Trace      : {save_trace(result)}")
