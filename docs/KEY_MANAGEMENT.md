# Key Management and Rotation

## Key provider

- **File:** Private key stored in a file; use `--sign-key <path>` or `HB_SIGN_KEY_PATH`. Restrict permissions (e.g. chmod 600).
- **Env:** Set key material in an env var (e.g. base64); use `HB_KEY_PROVIDER=env` and `HB_SIGN_KEY_ENV=MY_SIGN_KEY`. Prefer for CI; avoid in long-lived processes.
- **KMS/Vault:** Use `hb/keys.py` abstract provider. Implement `get_key_provider("kms", key_id=...)` with boto3 (AWS KMS Decrypt) or `get_key_provider("vault", path=...)` with hvac. Keys never leave the HSM/service.

## Key rotation for signing keys

1. Generate a new key pair (e.g. Ed25519).
2. Deploy the new key; start signing new manifests with it.
3. Record **signing_key_version** in the artifact manifest (e.g. `v2`) when signing, so verifiers know which key to use. Extend `write_artifact_manifest(..., signing_key_version="v2")` and have the signing step pass the version.
4. Keep old public keys available for verifying historical manifests; document the mapping (version -> public key or cert).
5. After a grace period, retire the old key.

## Encrypted DB and evidence packs

- **SQLCipher:** Use `bin/hb db encrypt/decrypt` or `tools/sqlcipher_encrypt_db.sh` to encrypt `runs.db` at rest. Document in deploy runbook.
- **Evidence packs:** Use `--encrypt-key` when generating evidence packs so the zip or directory is encrypted. Key can be file, env, or from KMS/Vault once implemented.
