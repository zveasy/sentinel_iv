# Secure Coding Standards

Baseline standards for this repo:

- Follow least-privilege defaults (local-only services bind to 127.0.0.1).
- Validate inputs and fail fast with actionable errors.
- Avoid storing secrets in source control; use environment variables or protected files.
- Encrypt artifacts at rest when required (`--encrypt-key`) and verify integrity via manifests/signatures.
- Prefer explicit schemas and type checks for ingest/config.
- Redact sensitive fields before report output when policy is provided.

Review checklist for changes touching security-sensitive areas:

- Input validation (paths, schema, payloads)
- Logging (avoid secrets; use redaction where applicable)
- Permissions (files written as 0600 when containing sensitive info)
- Integrity (artifact manifests + signatures updated)
