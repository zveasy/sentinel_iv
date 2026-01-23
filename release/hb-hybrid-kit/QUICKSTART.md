# Quickstart

1) Create a virtual environment and install dependencies:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r hb/requirements.txt
```

2) Start the local UI:
```bash
./bin/hb ui
```
Then open: http://127.0.0.1:8765

3) CLI compare example:
```bash
./bin/hb compare --baseline ./examples/baseline/baseline_source.csv \
  --run ./examples/run_ok/current_source.csv \
  --out ./output
```

## Docker (cross-OS)

Build and run the local UI in a container:
```bash
docker build -t hb-hybrid-kit .
docker run --rm -p 8765:8765 hb-hybrid-kit
```
Then open: http://127.0.0.1:8765
