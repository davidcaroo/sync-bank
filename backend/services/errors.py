class ServiceError(Exception):
    """Base class for domain/service-level failures."""


class RemoteAPIError(ServiceError):
    """Raised when an external API call fails."""


class InvalidXMLError(ServiceError):
    """Raised when an XML payload cannot be parsed or validated."""


class AlegraDuplicateBillError(RemoteAPIError):
    """Raised when Alegra reports a duplicated bill/document."""
