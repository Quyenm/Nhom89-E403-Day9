"""
eval_trace.py — Trace Evaluation & Comparison
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
from collections import Counter
from datetime import datetime
from typing import Optional

sys.path.insert(0, os.path.dirname(__file__))
from graph import run_graph, save_trace


def run_test_questions(questions_file: str = "data/test_questions.json") -> list:
    with open(questions_file, encoding="utf-8") as handle:
        questions = json.load(handle)

    os.makedirs("artifacts/traces", exist_ok=True)
    results = []
    print(f"Running {len(questions)} questions from {questions_file}")

    for index, item in enumerate(questions, start=1):
        question = item["question"]
        result = run_graph(question)
        result["question_id"] = item.get("id", f"q{index:02d}")
        trace_file = save_trace(result, "artifacts/traces")
        print(
            f"[{index:02d}] {result['question_id']} route={result['supervisor_route']} "
            f"conf={result['confidence']:.2f} latency={result['latency_ms']}ms trace={trace_file}"
        )
        results.append({"question": item, "result": result})
    return results


def run_grading_questions(questions_file: str = "data/grading_questions.json") -> str:
    if not os.path.exists(questions_file):
        print(f"{questions_file} not found.")
        return ""

    with open(questions_file, encoding="utf-8") as handle:
        questions = json.load(handle)

    os.makedirs("artifacts", exist_ok=True)
    output_file = "artifacts/grading_run.jsonl"
    with open(output_file, "w", encoding="utf-8") as out:
        for item in questions:
            result = run_graph(item["question"])
            record = {
                "id": item["id"],
                "question": item["question"],
                "answer": result.get("final_answer", ""),
                "sources": result.get("sources", []),
                "supervisor_route": result.get("supervisor_route", ""),
                "route_reason": result.get("route_reason", ""),
                "workers_called": result.get("workers_called", []),
                "mcp_tools_used": [entry.get("tool") for entry in result.get("mcp_tools_used", [])],
                "confidence": result.get("confidence", 0.0),
                "hitl_triggered": result.get("hitl_triggered", False),
                "timestamp": datetime.now().isoformat(),
            }
            out.write(json.dumps(record, ensure_ascii=False) + "\n")
    print(output_file)
    return output_file


def analyze_traces(traces_dir: str = "artifacts/traces") -> dict:
    if not os.path.exists(traces_dir):
        return {}

    trace_files = sorted(
        os.path.join(traces_dir, name) for name in os.listdir(traces_dir) if name.endswith(".json")
    )
    traces = []
    for path in trace_files:
        with open(path, encoding="utf-8") as handle:
            traces.append(json.load(handle))
    if not traces:
        return {}

    routing_counter = Counter(trace.get("supervisor_route", "unknown") for trace in traces)
    source_counter = Counter()
    mcp_counter = Counter()
    confidences = []
    latencies = []
    hitl_count = 0
    abstain_count = 0
    multi_worker_count = 0

    for trace in traces:
        confidences.append(trace.get("confidence", 0.0))
        if trace.get("latency_ms") is not None:
            latencies.append(trace["latency_ms"])
        if trace.get("hitl_triggered"):
            hitl_count += 1
        if "Không đủ thông tin" in trace.get("final_answer", ""):
            abstain_count += 1
        if len(set(trace.get("workers_called", []))) >= 3:
            multi_worker_count += 1
        for source in trace.get("sources", []) or trace.get("retrieved_sources", []):
            source_counter[source] += 1
        for entry in trace.get("mcp_tools_used", []):
            mcp_counter[entry.get("tool", "unknown")] += 1

    total = len(traces)
    return {
        "generated_at": datetime.now().isoformat(),
        "total_traces": total,
        "routing_distribution": {
            route: {"count": count, "percent": round((count / total) * 100, 1)}
            for route, count in routing_counter.items()
        },
        "avg_confidence": round(statistics.mean(confidences), 3),
        "avg_latency_ms": round(statistics.mean(latencies), 1) if latencies else 0,
        "median_latency_ms": round(statistics.median(latencies), 1) if latencies else 0,
        "mcp_usage_rate": round((sum(1 for trace in traces if trace.get("mcp_tools_used")) / total) * 100, 1),
        "mcp_tool_counts": dict(mcp_counter),
        "hitl_rate": round((hitl_count / total) * 100, 1),
        "abstain_rate": round((abstain_count / total) * 100, 1),
        "multi_worker_rate": round((multi_worker_count / total) * 100, 1),
        "top_sources": source_counter.most_common(5),
    }


def compare_single_vs_multi(
    multi_traces_dir: str = "artifacts/traces", day08_results_file: Optional[str] = None
) -> dict:
    day09 = analyze_traces(multi_traces_dir)
    day08 = {
        "status": "N/A",
        "note": "Day 08 baseline file was not provided in this workspace.",
    }
    if day08_results_file and os.path.exists(day08_results_file):
        with open(day08_results_file, encoding="utf-8") as handle:
            day08 = json.load(handle)

    return {
        "generated_at": datetime.now().isoformat(),
        "day08_single_agent": day08,
        "day09_multi_agent": day09,
        "analysis": {
            "routing_visibility": "Day 09 records supervisor_route and route_reason for every run.",
            "debuggability": "Workers can be tested independently and each appends its own worker_io_logs entry.",
            "latency_tradeoff": "The multi-agent pipeline adds orchestration overhead but exposes where time is spent.",
            "mcp_benefit": "Policy questions can add tool capability without changing the graph core.",
        },
    }


def save_eval_report(comparison: dict) -> str:
    os.makedirs("artifacts", exist_ok=True)
    output_file = "artifacts/eval_report.json"
    with open(output_file, "w", encoding="utf-8") as handle:
        json.dump(comparison, handle, ensure_ascii=False, indent=2)
    return output_file


def print_metrics(metrics: dict) -> None:
    if not metrics:
        print("No traces available.")
        return
    print(json.dumps(metrics, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--grading", action="store_true")
    parser.add_argument("--analyze", action="store_true")
    parser.add_argument("--compare", action="store_true")
    parser.add_argument("--test-file", default="data/test_questions.json")
    parser.add_argument("--day08-file")
    args = parser.parse_args()

    if args.grading:
        run_grading_questions()
    elif args.analyze:
        print_metrics(analyze_traces())
    elif args.compare:
        report = compare_single_vs_multi(day08_results_file=args.day08_file)
        print_metrics(report)
        print(save_eval_report(report))
    else:
        run_test_questions(args.test_file)
        metrics = analyze_traces()
        print_metrics(metrics)
        report = compare_single_vs_multi(day08_results_file=args.day08_file)
        print(save_eval_report(report))
