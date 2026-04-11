"""Integration-layer exceptions."""


class IntegrationError(Exception):
    """Base integration error."""


class ProviderNotRegisteredError(IntegrationError):
    """Raised when no provider is registered for a required capability."""


class CapabilityNotSupportedError(IntegrationError):
    """Raised when a provider does not implement a requested capability."""


class ProviderHealthError(IntegrationError):
    """Raised when a provider health check fails."""
