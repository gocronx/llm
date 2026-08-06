"""End-to-end approval workflow tests using an in-memory checkpointer."""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from approval.graph import build_graph
from approval.models import ChangePlan, initial_state
from approval.policy import DecisionError, validate_decision
from approval.storage import open_sqlite_graph
from langgraph.types import Command


def plan(*, environment: str = "production", replicas: int = 6) -> ChangePlan:
    return {
        "action": "scale_service",
        "service": "checkout-api",
        "environment": environment,
        "replicas": replicas,
    }


def config(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}}


class ApprovalWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.graph = build_graph()

    def test_low_risk_change_executes_without_interrupt(self) -> None:
        result = self.graph.invoke(
            initial_state(plan(environment="staging", replicas=2)),
            config("low-risk"),
        )

        self.assertEqual(result["status"], "completed")
        self.assertEqual(
            result["executed_plan"], plan(environment="staging", replicas=2)
        )
        self.assertNotIn("__interrupt__", result)
        self.assertTrue(any("LOW_RISK" in event for event in result["audit_log"]))

    def test_high_risk_change_pauses_then_approved_change_executes(self) -> None:
        cfg = config("approve")
        paused = self.graph.invoke(initial_state(plan()), cfg)

        self.assertEqual(paused["status"], "awaiting_approval")
        self.assertEqual(len(paused["__interrupt__"]), 1)
        request = paused["__interrupt__"][0].value
        self.assertEqual(request["risk_level"], "high")
        self.assertEqual(request["plan"], plan())

        result = self.graph.invoke(
            Command(resume={"action": "approve", "reason": "capacity change approved"}),
            cfg,
        )

        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["executed_plan"], plan())
        self.assertTrue(any("APPROVED" in event for event in result["audit_log"]))

    def test_rejected_change_never_executes(self) -> None:
        cfg = config("reject")
        self.graph.invoke(initial_state(plan()), cfg)

        result = self.graph.invoke(
            Command(resume={"action": "reject", "reason": "freeze window"}),
            cfg,
        )

        self.assertEqual(result["status"], "rejected")
        self.assertIsNone(result["executed_plan"])
        self.assertTrue(any("REJECTED" in event for event in result["audit_log"]))

    def test_edited_high_risk_change_is_assessed_and_paused_again(self) -> None:
        cfg = config("edit-high-risk")
        self.graph.invoke(initial_state(plan()), cfg)

        edited = plan(replicas=4)
        paused_again = self.graph.invoke(
            Command(
                resume={
                    "action": "edit",
                    "reason": "reduce requested capacity",
                    "edited_plan": edited,
                }
            ),
            cfg,
        )

        self.assertEqual(paused_again["status"], "awaiting_approval")
        self.assertEqual(paused_again["revision"], 1)
        self.assertEqual(paused_again["plan"], edited)
        self.assertEqual(paused_again["__interrupt__"][0].value["plan"], edited)

        result = self.graph.invoke(
            Command(resume={"action": "approve", "reason": "revised plan approved"}),
            cfg,
        )
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["executed_plan"], edited)

    def test_edited_low_risk_change_can_bypass_second_approval(self) -> None:
        cfg = config("edit-low-risk")
        self.graph.invoke(initial_state(plan()), cfg)
        edited = plan(environment="staging", replicas=2)

        result = self.graph.invoke(
            Command(
                resume={
                    "action": "edit",
                    "reason": "move experiment to staging",
                    "edited_plan": edited,
                }
            ),
            cfg,
        )

        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["revision"], 1)
        self.assertEqual(result["executed_plan"], edited)


class DecisionPolicyTests(unittest.TestCase):
    def test_edit_requires_a_complete_valid_plan(self) -> None:
        with self.assertRaises(DecisionError):
            validate_decision(
                {"action": "edit", "reason": "missing replacement"},
                current_plan=plan(),
            )

    def test_decision_rejects_unknown_fields(self) -> None:
        with self.assertRaises(DecisionError):
            validate_decision(
                {
                    "action": "approve",
                    "reason": "looks fine",
                    "admin": True,
                },
                current_plan=plan(),
            )

    def test_edit_cannot_change_the_operation_identity(self) -> None:
        changed_action = dict(plan())
        changed_action["action"] = "delete_service"
        with self.assertRaises(DecisionError):
            validate_decision(
                {
                    "action": "edit",
                    "reason": "change operation",
                    "edited_plan": changed_action,
                },
                current_plan=plan(),
            )


class DurableApprovalTests(unittest.TestCase):
    def test_sqlite_checkpointer_resumes_in_a_new_graph_instance(self) -> None:
        cfg = config("durable-approval")
        with TemporaryDirectory() as directory:
            database = Path(directory) / "approval.sqlite"
            with open_sqlite_graph(database) as first_process:
                paused = first_process.invoke(initial_state(plan()), cfg)
                self.assertEqual(paused["status"], "awaiting_approval")

            with open_sqlite_graph(database) as second_process:
                result = second_process.invoke(
                    Command(resume={"action": "approve", "reason": "on-call approved"}),
                    cfg,
                )

        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["executed_plan"], plan())


class CliSafetyTests(unittest.TestCase):
    def test_start_rejects_an_existing_thread_id(self) -> None:
        main = Path(__file__).resolve().parents[1] / "main.py"
        with TemporaryDirectory() as directory:
            command = [
                sys.executable,
                str(main),
                "--db",
                str(Path(directory) / "approval.sqlite"),
                "--thread-id",
                "duplicate",
                "start",
            ]
            first = subprocess.run(command, capture_output=True, text=True, check=False)
            second = subprocess.run(
                command, capture_output=True, text=True, check=False
            )

        self.assertEqual(first.returncode, 0)
        self.assertNotEqual(second.returncode, 0)
        self.assertIn("thread already exists", second.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
