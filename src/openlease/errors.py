from __future__ import annotations


class OpenLeaseError(RuntimeError):
    outcome = "invalid_request"
    exit_status = 2

    def __init__(self, message: str, *, details: object | None = None) -> None:
        super().__init__(message)
        self.details = details


class InvalidRequest(OpenLeaseError):
    pass


class ConfigurationError(InvalidRequest):
    """A public extension-configuration operation could not complete."""

    code = "configuration_error"


class ConfigurationReadOnly(ConfigurationError):
    code = "configuration_read_only"


class ConfigurationValidationFailed(ConfigurationError):
    code = "configuration_validation_failed"


class ConfigurationPathChanged(ConfigurationError):
    code = "configuration_path_changed"


class ConfigurationDecodeFailed(ConfigurationError):
    code = "configuration_decode_failed"


class ConfigurationConflict(ConfigurationError):
    code = "configuration_conflict"


class AuthorityConflict(OpenLeaseError):
    outcome = "authority_conflict"
    exit_status = 3


class OwnershipConflict(OpenLeaseError):
    outcome = "ownership_conflict"
    exit_status = 4


class PreparationFailed(OpenLeaseError):
    pass
