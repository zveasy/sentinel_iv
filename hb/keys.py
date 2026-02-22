"""
Abstract key provider: file, env, and optional KMS/Vault integration for signing and encryption.
"""
import os
from typing import Callable, Optional


def _read_file_key(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()


def _read_env_key(env_var: str) -> bytes:
    raw = os.environ.get(env_var)
    if not raw:
        raise ValueError(f"missing env {env_var}")
    return raw.encode("utf-8") if isinstance(raw, str) else raw


def get_key_provider(name: str = "file", path: Optional[str] = None, env_var: Optional[str] = None) -> Callable[[], bytes]:
    """
    Return a callable that returns key bytes. name: file | env | kms | vault.
    For file: path required. For env: env_var required. For kms: path or HB_KMS_KEY_ID; HB_KMS_CIPHERTEXT (b64). For vault: path or HB_VAULT_SECRET_PATH; env_var or HB_VAULT_MOUNT. KMS/Vault require boto3/hvac.
    """
    if name == "file":
        if not path:
            raise ValueError("path required for file key provider")
        return lambda: _read_file_key(path)
    if name == "env":
        if not env_var:
            raise ValueError("env_var required for env key provider")
        return lambda: _read_env_key(env_var)
    if name == "kms":
        return _kms_provider(path or os.environ.get("HB_KMS_KEY_ID"))
    if name == "vault":
        return _vault_provider(
            path or os.environ.get("HB_VAULT_PATH"),
            env_var or os.environ.get("HB_VAULT_MOUNT"),
        )
    raise ValueError(f"unknown key provider: {name}")


def _kms_provider(key_id: Optional[str] = None) -> Callable[[], bytes]:
    """Return callable that decrypts ciphertext from AWS KMS. key_id: KMS key ID or alias. Requires boto3."""
    if not key_id:
        raise ValueError("KMS key_id or HB_KMS_KEY_ID required")
    try:
        import boto3
        from botocore.exceptions import ClientError
    except ImportError:
        raise NotImplementedError("KMS provider requires boto3: pip install boto3")

    def _decrypt() -> bytes:
        ciphertext_b64 = os.environ.get("HB_KMS_CIPHERTEXT")
        if not ciphertext_b64:
            raise ValueError("HB_KMS_CIPHERTEXT (base64-encoded ciphertext) required for KMS decrypt")
        import base64
        try:
            kms = boto3.client("kms")
            out = kms.decrypt(CiphertextBlob=base64.b64decode(ciphertext_b64), KeyId=key_id)
            return out["Plaintext"]
        except ClientError as e:
            raise ValueError(f"KMS decrypt failed: {e}") from e
    return _decrypt


def _vault_provider(path: Optional[str] = None, mount: Optional[str] = None) -> Callable[[], bytes]:
    """Return callable that reads secret from Vault (kv v2 or transit). path: secret path; mount: mount point. Requires hvac."""
    path = path or os.environ.get("HB_VAULT_SECRET_PATH")
    mount = mount or os.environ.get("HB_VAULT_MOUNT", "secret")
    if not path:
        raise ValueError("Vault path or HB_VAULT_SECRET_PATH required")
    try:
        import hvac
    except ImportError:
        raise NotImplementedError("Vault provider requires hvac: pip install hvac")

    def _read() -> bytes:
        url = os.environ.get("VAULT_ADDR")
        token = os.environ.get("VAULT_TOKEN")
        if not url or not token:
            raise ValueError("VAULT_ADDR and VAULT_TOKEN required for Vault provider")
        client = hvac.Client(url=url, token=token)
        if not client.is_authenticated():
            raise ValueError("Vault authentication failed")
        try:
            # KV v2: path is secret/data/mykey; response has data["data"]
            r = client.secrets.kv.v2.read_secret_version(path=path, mount_point=mount)
            data = r.get("data", {}).get("data", r.get("data", {}))
            # Expect key material in a field (e.g. "key", "private_key", "signing_key")
            raw = data.get("key") or data.get("private_key") or data.get("signing_key") or data.get("value")
            if raw is None:
                raise ValueError("Vault secret must contain 'key', 'private_key', 'signing_key', or 'value'")
            return raw.encode("utf-8") if isinstance(raw, str) else raw
        except Exception as e:
            raise ValueError(f"Vault read failed: {e}") from e
    return _read
