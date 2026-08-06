"""Start or resume a durable LangGraph human-approval workflow."""

from __future__ import annotations

import argparse
import shlex
from pathlib import Path
from typing import Any

from approval.models import ChangePlan, initial_state
from approval.storage import open_sqlite_graph
from langgraph.types import Command

DEFAULT_DATABASE = Path(__file__).resolve().parent / "data" / "approval.sqlite"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Durable human approval for a production scale change",
    )
    parser.add_argument("--db", type=Path, default=DEFAULT_DATABASE)
    parser.add_argument("--thread-id", default="approval-demo-1")
    subparsers = parser.add_subparsers(dest="command", required=True)

    start = subparsers.add_parser("start", help="create and assess a change request")
    start.add_argument("--service", default="checkout-api")
    start.add_argument(
        "--environment",
        choices=("staging", "production"),
        default="production",
    )
    start.add_argument("--replicas", type=int, default=6)

    resume = subparsers.add_parser("resume", help="resume a paused change request")
    resume.add_argument("decision", choices=("approve", "edit", "reject"))
    resume.add_argument("--reason", required=True)
    resume.add_argument("--environment", choices=("staging", "production"))
    resume.add_argument("--replicas", type=int)
    return parser.parse_args()


def graph_config(thread_id: str) -> dict[str, Any]:
    return {"configurable": {"thread_id": thread_id}}


def resume_payload(
    args: argparse.Namespace, current_plan: ChangePlan
) -> dict[str, Any]:
    payload: dict[str, Any] = {"action": args.decision, "reason": args.reason}
    if args.decision != "edit":
        if args.environment is not None or args.replicas is not None:
            raise SystemExit("--environment/--replicas are valid only for resume edit")
        return payload
    edited_plan = dict(current_plan)
    if args.environment is not None:
        edited_plan["environment"] = args.environment
    if args.replicas is not None:
        edited_plan["replicas"] = args.replicas
    if edited_plan == current_plan:
        raise SystemExit(
            "resume edit requires --environment or --replicas to change the plan"
        )
    payload["edited_plan"] = edited_plan
    return payload


def print_result(result: dict[str, Any], thread_id: str, database: Path) -> None:
    print(f"thread_id: {thread_id}")
    print(f"status: {result['status']}")
    print(f"revision: {result['revision']}")
    print("audit:")
    for event in result["audit_log"]:
        print(f"  - {event}")
    interrupts = result.get("__interrupt__", ())
    if interrupts:
        request = interrupts[0].value
        print("approval_request:")
        print(f"  risk: {request['risk_level']}")
        print(f"  reasons: {', '.join(request['risk_reasons'])}")
        print(f"  plan: {request['plan']}")
        print(
            "resume with: python main.py "
            f"--db {shlex.quote(str(database))} "
            f"--thread-id {shlex.quote(thread_id)} "
            "resume approve --reason '...'"
        )
    elif result["executed_plan"] is not None:
        print(f"executed_plan: {result['executed_plan']}")


def main() -> None:
    args = parse_args()
    config = graph_config(args.thread_id)
    with open_sqlite_graph(args.db) as graph:
        if args.command == "start":
            if graph.get_state(config).values:
                raise SystemExit(f"thread already exists: {args.thread_id}")
            plan: ChangePlan = {
                "action": "scale_service",
                "service": args.service,
                "environment": args.environment,
                "replicas": args.replicas,
            }
            result = graph.invoke(initial_state(plan), config)
        else:
            snapshot = graph.get_state(config)
            if not snapshot.values:
                raise SystemExit(f"thread not found: {args.thread_id}")
            if not snapshot.interrupts:
                raise SystemExit(f"thread is not awaiting a decision: {args.thread_id}")
            current_plan = snapshot.values["plan"]
            payload = resume_payload(args, current_plan)
            result = graph.invoke(Command(resume=payload), config)
    print_result(result, args.thread_id, args.db)


if __name__ == "__main__":
    main()
