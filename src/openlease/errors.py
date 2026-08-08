from __future__ import annotations


class OpenLeaseError(RuntimeError):
    outcome = "invalid_request"
    exit_status = 2

    def __init__(self, message: str, *, details: object | None = None) -> None:
        super().__init__(message)
        self.details = details


class InvalidRequest(OpenLeaseError):
    pass


class AuthorityConflict(OpenLeaseError):
    outcome = "authority_conflict"
    exit_status = 3


class OwnershipConflict(OpenLeaseError):
    outcome = "ownership_conflict"
    exit_status = 4


class PreparationFailed(OpenLeaseError):
    pass
