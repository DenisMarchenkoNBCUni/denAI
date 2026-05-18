"""Custom exceptions."""


class DenAIError(Exception):
    """Base error."""


class UnexpectedStopReason(DenAIError):
    """Claude returned an unexpected stop reason."""

    def __init__(self, reason: str) -> None:
        super().__init__(f"Unexpected stop reason: {reason}")
        self.reason = reason


class ToolIterationLimitExceeded(DenAIError):
    """Too many tool-use iterations."""

    def __init__(self, limit: int = 8) -> None:
        super().__init__(f"Tool iteration limit exceeded ({limit})")
        self.limit = limit
