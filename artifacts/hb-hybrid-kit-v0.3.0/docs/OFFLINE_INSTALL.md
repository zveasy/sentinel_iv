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
