"""Structured domain errors shared by tools and recovery orchestration."""


class ToolExecutionError(Exception):
    """A structured, recoverable tool failure."""

    def __init__(self, code: str, message: str, *, retryable: bool) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable
