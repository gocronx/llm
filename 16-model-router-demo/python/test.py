"""Failover behaviour tests using mocked HTTP responses (no real LLM call)."""

from __future__ import annotations

import unittest
from unittest.mock import patch

import requests

import router
from models import BY_TIER


def _make_response(status_code: int, body: dict | None = None) -> requests.Response:
    resp = requests.Response()
    resp.status_code = status_code
    if body is not None:
        import json
        resp._content = json.dumps(body).encode("utf-8")
    return resp


def _ok_response(answer: str = "ok") -> requests.Response:
    return _make_response(200, {
        "choices": [{"message": {"content": answer}}],
        "usage": {"total_tokens": 10},
    })


def _http_error_response(status_code: int) -> requests.Response:
    return _make_response(status_code, {"error": f"simulated {status_code}"})


class FailoverTests(unittest.TestCase):
    """Each test mocks requests.post to control which tiers fail."""

    def test_no_failover_when_first_tier_succeeds(self) -> None:
        with patch("router.requests.post", return_value=_ok_response("hi")):
            result = router.route_always("cheap", "hello")

        self.assertEqual(result.chosen.tier, "cheap")
        self.assertEqual(result.failed_over_from, [])
        self.assertEqual(result.answer, "hi")

    def test_failover_skips_cheap_when_cheap_returns_500(self) -> None:
        calls: list[str] = []

        def fake_post(url, **kwargs):
            model_id = kwargs["json"]["model"]
            calls.append(model_id)
            if model_id == BY_TIER["cheap"].id:
                return _http_error_response(503)
            return _ok_response("from mid")

        with patch("router.requests.post", side_effect=fake_post):
            result = router.route_always("cheap", "hello")

        self.assertEqual(result.chosen.tier, "mid")
        self.assertEqual([m.tier for m in result.failed_over_from], ["cheap"])
        self.assertEqual(calls, [BY_TIER["cheap"].id, BY_TIER["mid"].id])
        # Cost reflects the tier that actually answered, not the failed one
        self.assertGreater(result.cost, 0)

    def test_failover_chains_cheap_then_mid_then_succeeds_on_premium(self) -> None:
        def fake_post(url, **kwargs):
            model_id = kwargs["json"]["model"]
            if model_id in (BY_TIER["cheap"].id, BY_TIER["mid"].id):
                return _http_error_response(503)
            return _ok_response("from premium")

        with patch("router.requests.post", side_effect=fake_post):
            result = router.route_always("cheap", "hello")

        self.assertEqual(result.chosen.tier, "premium")
        self.assertEqual([m.tier for m in result.failed_over_from], ["cheap", "mid"])

    def test_all_tiers_fail_raises_AllTiersFailed(self) -> None:
        with patch("router.requests.post",
                   return_value=_http_error_response(503)):
            with self.assertRaises(router.AllTiersFailed):
                router.route_always("cheap", "hello")

    def test_4xx_does_not_trigger_failover(self) -> None:
        """Bad request / auth errors aren't tier-specific — propagating is correct."""
        calls: list[str] = []

        def fake_post(url, **kwargs):
            calls.append(kwargs["json"]["model"])
            return _http_error_response(401)

        with patch("router.requests.post", side_effect=fake_post):
            with self.assertRaises(requests.HTTPError):
                router.route_always("cheap", "hello")

        # Only the first tier was tried — no failover loop for 401
        self.assertEqual(calls, [BY_TIER["cheap"].id])

    def test_network_timeout_triggers_failover(self) -> None:
        def fake_post(url, **kwargs):
            if kwargs["json"]["model"] == BY_TIER["cheap"].id:
                raise requests.Timeout("simulated timeout")
            return _ok_response("from mid")

        with patch("router.requests.post", side_effect=fake_post):
            result = router.route_always("cheap", "hello")

        self.assertEqual(result.chosen.tier, "mid")
        self.assertEqual([m.tier for m in result.failed_over_from], ["cheap"])

    def test_rules_strategy_uses_failover(self) -> None:
        def fake_post(url, **kwargs):
            if kwargs["json"]["model"] == BY_TIER["cheap"].id:
                return _http_error_response(503)
            return _ok_response("greetings")

        # 'hi' triggers the EASY keyword path → starting tier = cheap
        with patch("router.requests.post", side_effect=fake_post):
            result = router.route_rules("hi")

        self.assertEqual(result.chosen.tier, "mid")
        self.assertEqual([m.tier for m in result.failed_over_from], ["cheap"])
        self.assertIn("rules → cheap", result.rationale)

    def test_cascade_failover_then_escalation_both_recorded(self) -> None:
        """cheap fails → failover to mid → mid gives '' (weak) → escalate to premium."""
        def fake_post(url, **kwargs):
            mid = kwargs["json"]["model"]
            if mid == BY_TIER["cheap"].id:
                return _http_error_response(503)
            if mid == BY_TIER["mid"].id:
                return _ok_response("")
            return _ok_response("a real and decent premium answer goes here")

        with patch("router.requests.post", side_effect=fake_post):
            result = router.route_cascade("any prompt")

        self.assertEqual(result.chosen.tier, "premium")
        self.assertIsNotNone(result.escalated_from)
        # `failed_over_from` aggregates both the cheap failure and any premium-leg failover
        self.assertIn("cheap", [m.tier for m in result.failed_over_from])
        self.assertIn("cheap weak → premium", result.rationale)


if __name__ == "__main__":
    unittest.main(verbosity=2)
