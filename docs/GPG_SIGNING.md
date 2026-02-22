# Optional: GPG signing of release artifacts

For additional integrity assurance, you can sign the release zip (and checksums) with GPG so customers can verify the artifact was produced by you.

## Signing

1. Ensure you have a GPG key: `gpg --list-secret-keys`
2. Sign the kit zip after building:
   ```bash
   gpg --armor --detach-sig artifacts/hb-hybrid-kit-v0.3.0.zip
   ```
   This produces `artifacts/hb-hybrid-kit-v0.3.0.zip.asc`.

3. Optionally sign the checksums file:
   ```bash
   gpg --armor --detach-sig artifacts/checksums.txt
   ```

## Customer verification

Customers can verify with:

```bash
gpg --verify hb-hybrid-kit-v0.3.0.zip.asc hb-hybrid-kit-v0.3.0.zip
```

They must have your public key (e.g. from your support portal or keyserver). Document the key ID and where to obtain it in your release notes.

## CI

To sign in CI, add a step that uses a stored GPG secret (e.g. `GPG_PRIVATE_KEY` and `GPG_PASSPHRASE` in GitHub Actions secrets), imports the key, and runs the above commands. See GitHub Actions documentation for "Signing artifacts."
