"""test.py —— 不依赖外网的纯逻辑测试 + protocol 模型测试。"""
from __future__ import annotations

from protocol import AgentCard, AuthSpec, TaskRequest, TaskResponse
from util import extract_json_array


def t(label: str, cond: bool) -> bool:
    print(f"{'✓' if cond else '✗'} {label}")
    return cond


def main() -> None:
    # protocol：基本字段、auth 可选、state 限定 enum
    card = AgentCard(name="x", description="d", capabilities=["a"], endpoint="http://x")
    card_with_auth = AgentCard(name="x", description="d", capabilities=["a"],
                                endpoint="http://x", auth=AuthSpec(scheme="bearer"))
    req = TaskRequest(task_id="t1", task_type="a", input={"x": 1}, requester="me")
    resp_ok = TaskResponse(task_id="t1", state="completed", output={"y": 2})
    resp_err = TaskResponse(task_id="t1", state="failed", error="oops")

    passed = sum([
        t("AgentCard auth optional", card.auth is None and card_with_auth.auth.scheme == "bearer"),
        t("TaskRequest minimal", req.task_id == "t1" and req.input == {"x": 1}),
        t("TaskResponse completed", resp_ok.state == "completed" and resp_ok.output == {"y": 2}),
        t("TaskResponse failed", resp_err.state == "failed" and resp_err.error == "oops"),

        # extract_json_array
        t("extract picks last valid array", extract_json_array("noise [\"a\",\"b\"]") == ["a", "b"]),
        t("extract empty if no array", extract_json_array("no array") == []),
        t("extract handles nested arrays",
          extract_json_array("[[1,2],[3,4]]") == [[1, 2], [3, 4]]),
    ])
    print(f"\n{passed}/7 passed")


if __name__ == "__main__":
    main()
