"""Custom exceptions for the Prevengos integration."""


class PrevengosIntegrationError(RuntimeError):
    """Base exception raised when the Prevengos integration fails."""


class PrevengosAPIError(PrevengosIntegrationError):
    """Raised when the Prevengos API returns an unexpected response."""


class PrevengosCSVError(PrevengosIntegrationError):
    """Raised when CSV operations fail or contain invalid data."""


class PrevengosDatabaseError(PrevengosIntegrationError):
    """Raised when database queries cannot be executed successfully."""
