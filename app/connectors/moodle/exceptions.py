"""Shared exceptions for Moodle connectors."""


class MoodleAPIError(RuntimeError):
    """Raised when the Moodle API cannot be used or returns invalid data."""


__all__ = ["MoodleAPIError"]
