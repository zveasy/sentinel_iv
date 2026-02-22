"""
RBAC: roles (viewer, operator, approver, admin), per-program access, and checks for sensitive ops.
"""
import os
from typing import Any

# Role hierarchy: admin > approver > operator > viewer
ROLES = {"viewer", "operator", "approver", "admin"}
SENSITIVE_OPS = {"baseline set", "baseline approve", "override", "export evidence-pack", "db encrypt", "db decrypt"}


def role_level(role: str) -> int:
    order = {"viewer": 0, "operator": 1, "approver": 2, "admin": 3}
    return order.get((role or "").strip().lower(), -1)


def has_permission(role: str, operation: str, program: str | None = None, program_scope: set | None = None) -> bool:
    """
    Check if role can perform operation. If program_scope is set, operator must have access to program.
    """
    if role not in ROLES:
        return False
    if operation in SENSITIVE_OPS:
        if role_level(role) < role_level("approver"):
            return False
        if operation in {"baseline approve", "override"} and role_level(role) < role_level("approver"):
            return False
    if program is not None and program_scope is not None and program and program not in program_scope:
        return False
    return True


def get_current_role() -> str:
    """From env or default (e.g. HB_ROLE=operator). Used when RBAC is enabled."""
    return (os.environ.get("HB_ROLE") or "viewer").strip().lower()


def require_role(operation: str, program: str | None = None) -> None:
    """Raise if current role cannot perform operation. Call before sensitive CLI/API."""
    role = get_current_role()
    program_scope = None  # TODO: load from DB or config per user
    if not has_permission(role, operation, program=program, program_scope=program_scope):
        raise PermissionError(f"role '{role}' cannot perform '{operation}'")
