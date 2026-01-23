import json
import os
import time
from glob import glob

from hb import cli


def _default_workspace():
    return os.environ.get("HB_WORKSPACE", os.path.join(os.path.expanduser("~"), ".harmony_bridge"))


def _ensure_dirs(workspace):
    for name in ["baselines", "runs", "reports", "logs", "feedback"]:
        os.makedirs(os.path.join(workspace, name), exist_ok=True)


def _state_path(workspace):
    return os.path.join(workspace, "logs", "watch_state.json")


def _load_state(path):
    if not os.path.exists(path):
        return {"processed": []}
    with open(path, "r") as f:
        return json.load(f)


def _save_state(path, state):
    with open(path, "w") as f:
        json.dump(state, f, indent=2)


def _resolve_run_meta(run_meta_path, run_meta_dir, data_path):
    if run_meta_path:
        return run_meta_path
    if run_meta_dir:
        base = os.path.splitext(os.path.basename(data_path))[0]
        candidate = os.path.join(run_meta_dir, f"{base}.json")
        if os.path.exists(candidate):
            return candidate
    return None


def _iter_candidates(watch_dir, pattern):
    paths = glob(os.path.join(watch_dir, pattern))
    paths = [path for path in paths if os.path.isfile(path)]
    paths.sort(key=lambda p: os.path.getmtime(p))
    return paths


def run_watch(
    watch_dir,
    source,
    pattern="*",
    interval=60,
    workspace=None,
    run_meta=None,
    run_meta_dir=None,
    open_report=False,
    once=False,
):
    workspace = workspace or _default_workspace()
    _ensure_dirs(workspace)
    state_path = _state_path(workspace)
    state = _load_state(state_path)
    processed = set(state.get("processed") or [])

    reports_dir = os.path.join(workspace, "reports")
    db_path = os.path.join(workspace, "logs", "runs.db")

    while True:
        candidates = _iter_candidates(watch_dir, pattern)
        for path in candidates:
            if path in processed:
                continue
            run_meta_path = _resolve_run_meta(run_meta, run_meta_dir, path)
            args = cli.argparse.Namespace(
                source=source,
                path=path,
                run_meta=run_meta_path,
                out=None,
                stream=False,
                baseline_policy=os.environ.get("HB_BASELINE_POLICY", "baseline_policy.yaml"),
                metric_registry=os.environ.get("HB_METRIC_REGISTRY", "metric_registry.yaml"),
                db=db_path,
                reports=reports_dir,
                top=5,
                pdf=False,
                encrypt_key=None,
                sign_key=None,
                redaction_policy=None,
            )
            report_dir = cli.run(args)
            processed.add(path)
            state["processed"] = sorted(processed)
            _save_state(state_path, state)
            if open_report:
                report_path = os.path.join(report_dir, "drift_report.html")
                if os.path.exists(report_path):
                    if os.name == "posix" and os.path.exists("/usr/bin/open"):
                        os.system(f"open '{report_path}'")
                    elif os.system("command -v xdg-open >/dev/null 2>&1") == 0:
                        os.system(f"xdg-open '{report_path}'")
        if once:
            break
        time.sleep(interval)
