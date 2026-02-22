# Evidence Signing (Ed25519 / Org PKI)

Signed reports and manifests provide integrity and non-repudiation for DoD evidence.

## Current behavior

- **CLI:** `hb analyze --run <dir> --sign-key <path>` signs the artifact manifest after the run. The manifest lists all report artifacts and their SHA-256 hashes; the signature file is `artifact_manifest.json.sig`.
- **Verification:** `hb verify --report-dir <dir> --sign-key <path>` checks the signature against the manifest.

## Key formats

- **Ed25519 (recommended):** Generate with `openssl genpkey -algorithm Ed25519 -out signing.key`. The current implementation accepts PEM private keys; the signature is written as a single line (base64 or hex).
- **Org PKI:** Use your organization’s PKI-issued key pair. Ensure the key format is PEM and the signing code uses the same digest/signature scheme (e.g. Ed25519 or ECDSA). Replace the key file path with the path to your issued private key; document the public key/certificate distribution for verification.

## Standardizing on Ed25519

1. Generate: `openssl genpkey -algorithm Ed25519 -out signing.key`.
2. Store the key in a secure location (KMS/Vault or restricted file); do not commit.
3. Use `--sign-key signing.key` (or `HB_SIGN_KEY` env) for analyze/run.
4. For verification, use the corresponding public key; extend `hb verify` to accept `--sign-key` as public key when the file contains `PUBLIC KEY` (or add `--public-key`).

## Certificate-based (org PKI)

When using an org-issued certificate:

1. Sign with the private key corresponding to the certificate.
2. Attach or reference the certificate in the evidence pack (e.g. `config_snapshot/` or manifest) so verifiers can validate the chain.
3. Document the root CA and any intermediates in your deployment guide.
