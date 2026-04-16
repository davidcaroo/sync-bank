class ServiceError(Exception):
    """Base class for domain/service-level failures."""


class RemoteAPIError(ServiceError):
    """Raised when an external API call fails."""

    def __init__(self, message: str, *, status_code: int | None = None, payload: object | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


class InvalidXMLError(ServiceError):
    """Raised when an XML payload cannot be parsed or validated."""


class AlegraDuplicateBillError(RemoteAPIError):
    """Raised when Alegra reports a duplicated bill/document."""
