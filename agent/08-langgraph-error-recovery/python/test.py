"""Run the dependency-free recovery demo test suite."""

from tests.test_loop_guard import LOOP_GUARD_TESTS
from tests.test_recovery import RECOVERY_TESTS
from tests.test_tools import TOOL_TESTS


def main() -> None:
    tests = [*RECOVERY_TESTS, *LOOP_GUARD_TESTS, *TOOL_TESTS]
    passed = sum(test() for test in tests)
    print(f"\n{passed}/{len(tests)} passed")


if __name__ == "__main__":
    main()
