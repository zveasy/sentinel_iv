# Offline Install (DoD Lab)

This MVP is designed to run without network access after dependencies are staged.

## 1) Build a wheelhouse (on a connected machine)

```
python -m venv .venv
source .venv/bin/activate
pip install -r hb/requirements.txt -r hb/requirements-dev.txt
pip download -r hb/requirements.txt -r hb/requirements-dev.txt -d wheelhouse/
```

Copy `wheelhouse/`, the repo, and any required keys to the offline lab.

## 2) Install from wheelhouse (offline lab)

```
python -m venv .venv
source .venv/bin/activate
pip install --no-index --find-links=wheelhouse -r hb/requirements.txt -r hb/requirements-dev.txt
```

## 3) Verify

```
python hb/cli.py --help
pytest -q
```

## 4) Signed bundles (air-gapped)

For air-gapped install from a signed release:

1. On a connected machine, build the release kit (`python tools/build_kit.py`) and sign the zip (see `docs/GPG_SIGNING.md`).
2. Transfer the signed zip and signature (or checksums) to the air-gapped environment via approved media.
3. Verify the signature or checksums before extracting (see `docs/INTEGRITY_VERIFICATION.md`).
4. Install from the extracted kit using the wheelhouse method above if dependencies are bundled, or from a pre-staged wheelhouse.
