# Deployment: OS Support Matrix and Upgrade Path

**Purpose:** Deterministic installers, OS support matrix (RHEL/Rocky, Ubuntu LTS), hardened containers/Helm, and upgrade/migration path so IT can install in an enclave with no internet and upgrades don’t break data.

**References:** `docs/OFFLINE_INSTALL.md`, `docs/SECURE_INSTALL.md`, `deploy/`, `helm/`, `docs/RELEASE_CHECKLIST.md`.

---

## 1. OS support matrix

| OS | Version | Notes |
|----|---------|--------|
| **RHEL / Rocky Linux** | 8.x, 9.x | Common in DoD labs; use `pip install` or offline wheelhouse; systemd unit in `deploy/`. |
| **Ubuntu LTS** | 20.04, 22.04 | Common in dev labs; same install path. |
| **Windows** | 10/11 | Docker only; no native daemon. |

---

## 2. Deterministic installers

- **Offline bundle:** Wheelhouse + HB package + configs; see `docs/OFFLINE_INSTALL.md`. Build on a clean host; checksum all artifacts.
- **Signed bundle:** Sign release zip (GPG/cosign); document in INTEGRITY_VERIFICATION and release process.
- **Checksum verification:** One-click (or one-command) verification: `tools/release_checksums.py` or `sha256sum -c checksums.txt`; document in customer docs.

---

## 3. Hardened container and Helm

- **Container:** Dockerfile runs as non-root where possible; use security defaults (read-only root, drop caps) in production overlay.
- **Helm:** `helm/sentinel-hb/` with securityContext (runAsNonRoot, readOnlyRootFilesystem where feasible); resource limits; no default admin credentials.
- **Secrets:** Use K8s secrets or Vault; never plaintext in values.yaml.

---

## 4. Upgrade and migration path

- **DB schema:** Registry uses additive migrations (ALTER TABLE ADD COLUMN when missing); see `hb/registry.py` init_db and column checks. New columns have defaults so old data still works.
- **Rollback:** Keep previous release package; restore DB from backup if needed. No destructive migrations in current design.
- **Version:** Bump version in CHANGELOG and release tag; document compatibility (e.g. “runs.db from 0.3.x is compatible with 0.4.x”).

---

## 5. Definition of done

- An IT admin can install in an enclave with no internet (offline bundle + checksums).
- Upgrades don’t break data: additive schema only; rollback procedure documented.
- OS matrix and hardened container/Helm defaults documented in this file and deploy/helm.
