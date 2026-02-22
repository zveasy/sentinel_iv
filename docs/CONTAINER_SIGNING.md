# Signed Container Images

Sign and verify container images (e.g. HB daemon image) in CI and at deploy for supply-chain assurance.

## Signing in CI

- **Cosign (Sigstore):** After `docker build`, sign the image with cosign:  
  `cosign sign --key cosign.key <image>@<digest>`  
  Push the signature to the registry (OCI artifact or attached to the image).
- **Notary / Docker Content Trust:** Enable DCT and use `docker push` with signing keys.
- **CI step:** In your release or build workflow, after building the image, run the signing command; store the signing key in a secret (e.g. GitHub Actions secret, Vault). Document the key lifecycle in KEY_MANAGEMENT.md.

## Verification at deploy

- Before deploying (e.g. in Kubernetes admission or a deploy script), verify the image signature:  
  `cosign verify --key cosign.pub <image>@<digest>`  
  Fail the deploy if verification fails.
- In Helm or K8s manifests, pin the image by digest (e.g. `image: myreg/sentinel-hb@sha256:...`) so the digest is immutable; then verify that digest with cosign.

## HB usage

- The HB Dockerfile and Helm chart reference an image (e.g. `sentinel-hb`). When you build and push that image in CI, add a signing step. When deploying with Helm or plain Kubernetes, run verification (or use a policy engine like Connaisseur) so only signed images are allowed.
