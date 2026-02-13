# Verifying Release Integrity

Before installing a Harmony Bridge release, verify that the artifact has not been modified in transit or storage.

## Checksums

Each release should include a checksum file (e.g. `hb-hybrid-kit-vX.Y.Z.zip.sha256` or `checksums.txt`) in the same location as the distribution zip.

### Verify the ZIP with SHA-256

If you have a `.sha256` file next to the zip:

**Linux / macOS:**
```bash
sha256sum -c hb-hybrid-kit-vX.Y.Z.zip.sha256
# or
shasum -a 256 -c hb-hybrid-kit-vX.Y.Z.zip.sha256
```

**Windows (PowerShell):**
```powershell
Get-FileHash -Algorithm SHA256 .\hb-hybrid-kit-vX.Y.Z.zip | Compare-Object (Get-Content .\hb-hybrid-kit-vX.Y.Z.zip.sha256)
```

### Generate checksums when building a release

From the project root, after building the kit:

```bash
python tools/release_checksums.py --kit artifacts/hb-hybrid-kit-v0.3.0.zip --out artifacts/
```

This writes `checksums.txt` and optionally `hb-hybrid-kit-v0.3.0.zip.sha256` in the output directory. Ship these next to the zip so customers can verify.

## Signed releases (optional)

If the vendor provides a GPG or other signature (e.g. `hb-hybrid-kit-vX.Y.Z.zip.asc` or `.sig`):

1. Import the vendor’s public key if you have not already.
2. Verify the signature against the zip file using the same tool (e.g. `gpg --verify ...`).
3. Then verify the checksum as above.

Signature verification steps will be documented in the release notes when signed releases are offered.

## After extraction

- Confirm the `VERSION` file inside the kit matches the version you downloaded.
- For maximum assurance, run the test suite from the extracted kit (see README) or run a known-good sample (see QUICKSTART).

## Reporting integrity issues

If a checksum or signature does not match, do not install the artifact. Contact support and report the download source and filename so the vendor can investigate.
