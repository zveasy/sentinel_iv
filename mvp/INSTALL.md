# Install

Local install (recommended for lab MVP):

```
python -m venv .venv
source .venv/bin/activate
pip install -r mvp/requirements.txt
```

Makefile install (fast path):

```
make install
```

Run analyzer:

```
python mvp/analyze.py --run mvp/runs/current/current-run.csv --baseline mvp/runs/baseline/baseline-run.csv
```

Run single-command flow:

```
chmod +x sentinel
./sentinel analyze mvp/runs/current/current-run.csv --source basic_csv --baseline mvp/runs/baseline/baseline-run.csv
```
