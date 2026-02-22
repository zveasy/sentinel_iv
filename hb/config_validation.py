"""
Secure defaults: reject plaintext secrets in config (require env or file references).
Enable with HB_REJECT_PLAINTEXT_SECRETS=1.
"""
import os
import re
from typing import Any


_SENSITIVE_KEYS = frozenset({
    "password", "passwd", "secret", "api_key", "apikey", "token",
    "private_key", "privatekey", "auth_key", "signing_key",
})
_SENSITIVE_NORMALIZED = frozenset(s.replace("-", "").replace("_", "") for s in _SENSITIVE_KEYS)


def _key_looks_sensitive(key: str) -> bool:
    k = key.lower().replace("-", "").replace("_", "")
    return any(n in k or k in n for n in _SENSITIVE_NORMALIZED)


def _is_env_ref(value: str) -> bool:
    return bool(re.match(r"^\$\{[A-Za-z_][A-Za-z0-9_]*\}$", value.strip()))


def _is_file_ref(value: str) -> bool:
    s = value.strip()
    if not s:
        return False
    return s.startswith("/") or "\\" in s or (len(s) > 1 and s[1] == ":")


def reject_plaintext_secrets(payload: Any, path: str = "") -> None:
    """
    Recursively check for sensitive keys with plaintext string values.
    Accepts: env refs (${VAR}), file paths (e.g. /path/to/key).
    Raises ValueError if a sensitive key has a non-empty string that is neither.
    """
    if payload is None:
        return
    if isinstance(payload, dict):
        for k, v in payload.items():
            p = f"{path}.{k}" if path else k
            if isinstance(v, str) and v and _key_looks_sensitive(k):
                if _is_env_ref(v) or _is_file_ref(v):
                    continue
                raise ValueError(
                    f"plaintext secret not allowed at {p}: use env ref (e.g. ${{VAR}}) or file path"
                )
            reject_plaintext_secrets(v, p)
        return
    if isinstance(payload, list):
        for i, v in enumerate(payload):
            reject_plaintext_secrets(v, f"{path}[{i}]")
        return


def should_reject_plaintext_secrets() -> bool:
    return os.environ.get("HB_REJECT_PLAINTEXT_SECRETS", "").strip() in ("1", "true", "yes")
