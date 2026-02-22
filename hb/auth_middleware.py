"""
API auth stub for mTLS + JWT/OPA or mTLS + signed tokens (roadmap 4.1.3).
Config-driven; full mTLS typically at load balancer; JWT/OPA validation can be wired here.
"""
from dataclasses import dataclass
from typing import Callable, Optional


@dataclass
class AuthConfig:
    """Auth configuration for API/health endpoints."""
    require_mtls: bool = False
    jwt_audience: Optional[str] = None
    jwt_issuer: Optional[str] = None
    # Header set by reverse proxy when client cert is verified (e.g. X-Client-DN)
    mtls_dn_header: str = "X-Client-DN"
    # Env fallback for development when mTLS not in use
    allow_no_auth_env: str = "HB_ALLOW_NO_AUTH"


def get_auth_config(config_dict: Optional[dict] = None) -> AuthConfig:
    """Build AuthConfig from daemon/API config. config_dict may have auth.mtls_required, auth.jwt_audience, etc."""
    config_dict = config_dict or {}
    auth = config_dict.get("auth") or {}
    return AuthConfig(
        require_mtls=bool(auth.get("mtls_required", False)),
        jwt_audience=auth.get("jwt_audience") or None,
        jwt_issuer=auth.get("jwt_issuer") or None,
        mtls_dn_header=auth.get("mtls_dn_header", "X-Client-DN"),
        allow_no_auth_env=auth.get("allow_no_auth_env", "HB_ALLOW_NO_AUTH"),
    )


def check_request_auth(
    headers: dict,
    config: Optional[AuthConfig] = None,
) -> tuple[bool, Optional[str]]:
    """
    Stub: check request for auth. Returns (allowed, error_message).
    When require_mtls: True, allows if mtls_dn_header is set (proxy set it) or HB_ALLOW_NO_AUTH=1.
    JWT/OPA: not implemented; extend here or at LB.
    """
    import os
    cfg = config or get_auth_config()
    if cfg.require_mtls:
        dn = (headers.get(cfg.mtls_dn_header) or "").strip()
        if dn:
            return True, None
        if os.environ.get(cfg.allow_no_auth_env, "").strip() == "1":
            return True, None
        return False, "mtls_required"
    return True, None


def wrap_handler_with_auth(
    handler: Callable,
    config: Optional[AuthConfig] = None,
    get_headers: Optional[Callable[[], dict]] = None,
) -> Callable:
    """
    Return a wrapper that runs check_request_auth before calling handler.
    get_headers() should return the request headers dict (e.g. from BaseHTTPRequestHandler).
    If check fails, wrapper can raise or return 401; default stub just calls handler.
    Extend to return 401 response when check_request_auth returns (False, msg).
    """
    cfg = config or get_auth_config()
    if not cfg.require_mtls:
        return handler

    def wrapped(*args, **kwargs):
        headers = get_headers() if get_headers else {}
        ok, err = check_request_auth(headers, cfg)
        if not ok:
            # Caller (e.g. health_server) should send 401 and body; for now we only support require_mtls
            raise PermissionError(err or "auth_required")
        return handler(*args, **kwargs)
    return wrapped
