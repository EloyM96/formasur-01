"""Moodle connectors exposed for reuse across the application."""
from .rest import MoodleRESTClient
from .soap import MoodleSOAPClient
from .exceptions import MoodleAPIError

__all__ = [
    "MoodleAPIError",
    "MoodleRESTClient",
    "MoodleSOAPClient",
]
