import argparse
import json
import os
import shutil
import subprocess
import uuid
import time
import zipfile
from email.parser import BytesParser
from email.policy import default
from http.server import BaseHTTPRequestHandler, HTTPServer
from io import BytesIO
from urllib.parse import parse_qs, urlparse

import pandas as pd
import yaml

from hb import cli
from hb import watch


def _default_workspace():
    return os.environ.get("HB_WORKSPACE", os.path.join(os.path.expanduser("~"), ".harmony_bridge"))


def _ensure_dirs(workspace):
    paths = [
        os.path.join(workspace, "baselines"),
        os.path.join(workspace, "runs"),
        os.path.join(workspace, "reports"),
        os.path.join(workspace, "logs"),
        os.path.join(workspace, "feedback"),
        os.path.join(workspace, "schemas"),
    ]
    for path in paths:
        os.makedirs(path, exist_ok=True)


def _save_upload_bytes(data, filename, dest_dir, prefix):
    filename = os.path.basename(filename)
    ext = os.path.splitext(filename)[1]
    out_name = f"{prefix}_{uuid.uuid4().hex}{ext}"
    out_path = os.path.join(dest_dir, out_name)
    with open(out_path, "wb") as f:
        f.write(data)
    return out_path


def _parse_multipart(headers, body):
    content_type = headers.get("Content-Type")
    if not content_type:
        return {}, {}
    message = (
        f"Content-Type: {content_type}\r\n"
        "MIME-Version: 1.0\r\n\r\n"
    ).encode("utf-8") + body
    parsed = BytesParser(policy=default).parsebytes(message)
    form = {}
    files = {}
    for part in parsed.iter_parts():
        if part.get_content_disposition() != "form-data":
            continue
        name = part.get_param("name", header="Content-Disposition")
        filename = part.get_param("filename", header="Content-Disposition")
        payload = part.get_payload(decode=True)
        if filename:
            item = {"filename": filename, "data": payload or b""}
            if name in files:
                if isinstance(files[name], list):
                    files[name].append(item)
                else:
                    files[name] = [files[name], item]
            else:
                files[name] = item
        else:
            text = payload.decode(part.get_content_charset() or "utf-8") if payload else ""
            if name in form:
                if isinstance(form[name], list):
                    form[name].append(text)
                else:
                    form[name] = [form[name], text]
            else:
                form[name] = text
    return form, files


def _open_report(path):
    if shutil.which("open"):
        subprocess.run(["open", path], check=False)
    elif shutil.which("xdg-open"):
        subprocess.run(["xdg-open", path], check=False)


def _support_bundle(report_dir, out_dir):
    bundle_name = f"support_bundle_{os.path.basename(report_dir)}.zip"
    bundle_path = os.path.join(out_dir, bundle_name)
    files = [
        os.path.join(report_dir, "drift_report.json"),
        os.path.join(report_dir, "drift_report.html"),
        os.path.join(report_dir, "artifact_manifest.json"),
        os.path.join(report_dir, "audit_log.jsonl"),
    ]
    manifest_path = os.path.join(out_dir, f"support_manifest_{os.path.basename(report_dir)}.json")
    manifest = {"files": [path for path in files if os.path.exists(path)]}
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    with zipfile.ZipFile(bundle_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in manifest["files"]:
            zf.write(path, os.path.join(os.path.basename(report_dir), os.path.basename(path)))
        zf.write(manifest_path, os.path.basename(manifest_path))
    return bundle_path


def _custom_sources_path(workspace):
    return os.path.join(workspace, "schemas", "custom_sources.json")


def _load_custom_sources(workspace):
    path = _custom_sources_path(workspace)
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r") as f:
            return json.load(f) or []
    except (OSError, json.JSONDecodeError):
        return []


def _save_custom_sources(workspace, sources):
    path = _custom_sources_path(workspace)
    with open(path, "w") as f:
        json.dump(sources, f, indent=2)


def _default_run_meta(source, seed=None):
    seed = seed or {}
    return {
        "program": seed.get("program", "local_ui"),
        "subsystem": seed.get("subsystem", source),
        "test_name": seed.get("test_name", "default"),
        "scenario_id": seed.get("scenario_id", "default"),
        "operating_mode": seed.get("operating_mode", "default"),
        "environment": seed.get("environment", "local"),
        "environment_fingerprint": seed.get("environment_fingerprint", "local"),
        "sensor_config_id": seed.get("sensor_config_id", "default"),
        "input_data_version": seed.get("input_data_version", "1"),
    }


def _read_json_bytes(payload):
    if not payload:
        return {}
    try:
        return json.loads(payload.decode("utf-8"))
    except Exception:
        return {}


def _write_run_meta(run_meta, workspace, prefix):
    path = os.path.join(workspace, "logs")
    os.makedirs(path, exist_ok=True)
    out_path = os.path.join(path, f"{prefix}_{uuid.uuid4().hex}.json")
    with open(out_path, "w") as f:
        json.dump(run_meta, f, indent=2)
    return out_path


def _detect_delimiter(sample_bytes):
    sample = sample_bytes.splitlines()[0] if sample_bytes else b""
    tab_count = sample.count(b"\t")
    comma_count = sample.count(b",")
    return "\t" if tab_count > comma_count else ","


def _infer_column_types(df):
    types = {}
    for col in df.columns:
        series = df[col].astype(str).str.strip()
        non_empty = series[series != ""]
        if non_empty.empty:
            types[col] = "str"
            continue
        numeric = pd.to_numeric(non_empty, errors="coerce")
        if numeric.notna().all():
            if (numeric % 1 == 0).all():
                types[col] = "int"
            else:
                types[col] = "float"
        else:
            types[col] = "str"
    return types


def _build_schema_from_sample(schema_name, sample_bytes, workspace, require_all=False):
    delimiter = _detect_delimiter(sample_bytes)
    try:
        df = pd.read_csv(
            BytesIO(sample_bytes),
            sep=delimiter,
            dtype=str,
            keep_default_na=False,
            nrows=500,
            encoding_errors="replace",
        )
    except UnicodeDecodeError:
        df = pd.read_csv(
            BytesIO(sample_bytes),
            sep=delimiter,
            dtype=str,
            keep_default_na=False,
            nrows=500,
            encoding="latin1",
            encoding_errors="replace",
        )
    if df.empty or not df.columns.tolist():
        raise ValueError("No header row detected in sample file.")
    columns = df.columns.tolist()
    inferred_types = _infer_column_types(df)
    required = columns if require_all else []
    optional = [col for col in columns if col not in required]
    schema = {
        "name": schema_name,
        "format": "tabular",
        "delimiter": delimiter,
        "header": True,
        "required_columns": required,
        "optional_columns": optional,
        "column_types": inferred_types,
        "allow_extra_columns": True,
    }
    schema_path = os.path.join(workspace, "schemas", f"{schema_name}.yaml")
    with open(schema_path, "w") as f:
        yaml.safe_dump(schema, f, sort_keys=False)
    sources = _load_custom_sources(workspace)
    sources = [item for item in sources if item.get("name") != schema_name]
    sources.append({"name": schema_name, "schema_path": schema_path})
    _save_custom_sources(workspace, sources)
    return schema_path


class LocalUIHandler(BaseHTTPRequestHandler):
    def _set_headers(self, status=200, content_type="text/html; charset=utf-8"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

    def _render(self, body, status=200):
        self._set_headers(status)
        self.wfile.write(body.encode("utf-8"))

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            self._set_headers(200, "application/json")
            self.wfile.write(b'{"status":"ok"}')
            return
        if parsed.path == "/download":
            query = parse_qs(parsed.query or "")
            file_path = (query.get("file") or [None])[0]
            if not file_path or not os.path.exists(file_path):
                self._set_headers(404, "application/json")
                self.wfile.write(b'{"error":"not_found"}')
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Disposition", f'attachment; filename="{os.path.basename(file_path)}"')
            self.end_headers()
            with open(file_path, "rb") as f:
                shutil.copyfileobj(f, self.wfile)
            return
        if parsed.path in ("/", "/index.html"):
            self._render(self._page())
            return
        if parsed.path == "/watch/status":
            self._set_headers(200, "application/json")
            running = bool(getattr(self.server, "watch_active", False))
            payload = {"active": running}
            self.wfile.write(json.dumps(payload).encode("utf-8"))
            return
        self._set_headers(404, "application/json")
        self.wfile.write(b'{"error":"not_found"}')

    def do_POST(self):
        if self.path == "/watch/start":
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length)
            form, _ = _parse_multipart(self.headers, body)
            workspace = form.get("workspace") or _default_workspace()
            _ensure_dirs(workspace)
            watch_dir = form.get("watch_dir")
            source = form.get("source") or "pba_excel"
            pattern = form.get("pattern") or "*"
            interval = int(form.get("interval") or 604800)
            if not watch_dir:
                self._set_headers(400, "application/json")
                self.wfile.write(b'{"error":"missing_watch_dir"}')
                return
            if not os.path.isdir(watch_dir):
                self._set_headers(400, "application/json")
                self.wfile.write(b'{"error":"watch_dir_not_found"}')
                return
            if getattr(self.server, "watch_active", False):
                self._set_headers(200, "application/json")
                self.wfile.write(b'{"status":"already_running"}')
                return
            self.server.watch_active = True
            self.server.watch_config = {
                "watch_dir": watch_dir,
                "source": source,
                "pattern": pattern,
                "interval": interval,
                "workspace": workspace,
            }
            self._set_headers(200, "application/json")
            self.wfile.write(b'{"status":"started"}')
            return
        if self.path == "/watch/stop":
            if getattr(self.server, "watch_active", False):
                self.server.watch_active = False
                self._set_headers(200, "application/json")
                self.wfile.write(b'{"status":"stopped"}')
            else:
                self._set_headers(200, "application/json")
                self.wfile.write(b'{"status":"not_running"}')
            return
        if self.path == "/schema/build":
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length)
            form, files = _parse_multipart(self.headers, body)
            workspace = form.get("workspace") or _default_workspace()
            _ensure_dirs(workspace)
            name = (form.get("schema_name") or "").strip()
            sample_file = files.get("sample_file")
            if not name:
                self._render(self._page(error="Schema name is required."), status=400)
                return
            if not sample_file or not sample_file.get("filename"):
                self._render(self._page(error="Please upload a sample file."), status=400)
                return
            delimiter = _detect_delimiter(sample_file["data"])
            try:
                df = pd.read_csv(
                    BytesIO(sample_file["data"]),
                    sep=delimiter,
                    dtype=str,
                    keep_default_na=False,
                    nrows=500,
                )
            except Exception as exc:
                self._render(self._page(error=f"Unable to parse file: {exc}"), status=400)
                return
            if df.empty or not df.columns.tolist():
                self._render(self._page(error="No header row detected in sample file."), status=400)
                return
            inferred_types = _infer_column_types(df)
            columns = df.columns.tolist()
            payload = {
                "name": name,
                "delimiter": delimiter,
                "columns": columns,
                "types": inferred_types,
            }
            schema_builder = self._schema_confirm_block(payload, workspace)
            self._render(self._page(schema_builder_html=schema_builder))
            return
        if self.path == "/schema/confirm":
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length)
            form, _ = _parse_multipart(self.headers, body)
            workspace = form.get("workspace") or _default_workspace()
            _ensure_dirs(workspace)
            name = (form.get("schema_name") or "").strip()
            delimiter = form.get("delimiter") or ","
            columns = json.loads(form.get("columns") or "[]")
            types = json.loads(form.get("types") or "{}")
            required = form.get("required_cols") or []
            if isinstance(required, str):
                required = [required]
            required = [col for col in required if col in columns]
            optional = [col for col in columns if col not in required]
            if not name:
                self._render(self._page(error="Schema name is required."), status=400)
                return
            schema = {
                "name": name,
                "format": "tabular",
                "delimiter": delimiter,
                "header": True,
                "required_columns": required,
                "optional_columns": optional,
                "column_types": types,
                "allow_extra_columns": True,
            }
            schema_path = os.path.join(workspace, "schemas", f"{name}.yaml")
            with open(schema_path, "w") as f:
                yaml.safe_dump(schema, f, sort_keys=False)
            sources = _load_custom_sources(workspace)
            sources = [item for item in sources if item.get("name") != name]
            sources.append({"name": name, "schema_path": schema_path})
            _save_custom_sources(workspace, sources)
            message = f"Schema saved and registered: {schema_path}"
            self._render(self._page(success=message))
            return
        if self.path != "/run":
            self._set_headers(404, "application/json")
            self.wfile.write(b'{"error":"not_found"}')
            return

        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        form, files = _parse_multipart(self.headers, body)
        workspace = form.get("workspace") or _default_workspace()
        _ensure_dirs(workspace)
        mode = form.get("mode") or "current"
        source = form.get("source") or "pba_excel"
        custom_schema_path = None
        if source.startswith("custom|"):
            custom_schema_path = source.split("|", 1)[1]
            source = "custom_tabular"
        run_meta_field = files.get("run_meta")
        data_field = files.get("data_file")
        baseline_field = files.get("baseline_file")
        current_field = files.get("current_file")

        reports_dir = os.path.join(workspace, "reports")
        db_path = os.path.join(workspace, "logs", "runs.db")

        if mode == "compare":
            auto_schema = form.get("auto_schema") == "1"
            project_name = (form.get("project_name") or "project").strip().lower().replace(" ", "_")
            if isinstance(baseline_field, list):
                baseline_field = baseline_field[0] if baseline_field else None
            if not baseline_field or not baseline_field.get("filename"):
                self._render(self._page(error="Please upload a baseline file."), status=400)
                return
            current_fields = current_field if isinstance(current_field, list) else [current_field]
            current_fields = [item for item in current_fields if item and item.get("filename")]
            if not current_fields:
                self._render(self._page(error="Please upload a current file."), status=400)
                return
            baseline_path = _save_upload_bytes(
                baseline_field["data"], baseline_field["filename"], os.path.join(workspace, "baselines"), "baseline"
            )
            baseline_meta_path = None
            current_meta_path = None
            baseline_meta_payload = files.get("baseline_meta")
            current_meta_payload = files.get("current_meta")
            if baseline_meta_payload and baseline_meta_payload.get("filename"):
                baseline_meta_path = _save_upload_bytes(
                    baseline_meta_payload["data"],
                    baseline_meta_payload["filename"],
                    os.path.join(workspace, "logs"),
                    "baseline_meta",
                )
            if current_meta_payload and current_meta_payload.get("filename"):
                current_meta_path = _save_upload_bytes(
                    current_meta_payload["data"],
                    current_meta_payload["filename"],
                    os.path.join(workspace, "logs"),
                    "current_meta",
                )
            if not baseline_meta_path or not current_meta_path:
                baseline_seed = _read_json_bytes(
                    baseline_meta_payload["data"] if baseline_meta_payload else None
                )
                current_seed = _read_json_bytes(
                    current_meta_payload["data"] if current_meta_payload else None
                )
                seed = baseline_seed or current_seed
                fallback_meta = _default_run_meta(source, seed=seed)
                if not baseline_meta_path:
                    baseline_meta_path = _write_run_meta(fallback_meta, workspace, "baseline_meta")
                if not current_meta_path:
                    current_meta_path = _write_run_meta(fallback_meta, workspace, "current_meta")

            if auto_schema:
                schema_name = f"{project_name}_{time.strftime('%Y%m%d')}_{uuid.uuid4().hex[:6]}"
                try:
                    schema_path = _build_schema_from_sample(schema_name, baseline_field["data"], workspace)
                except Exception as exc:
                    self._render(self._page(error=f"Schema builder failed: {exc}"), status=400)
                    return
                custom_schema_path = schema_path
                source = "custom_tabular"

            previous_schema = os.environ.get("HB_CUSTOM_SCHEMA_PATH")
            if custom_schema_path:
                os.environ["HB_CUSTOM_SCHEMA_PATH"] = custom_schema_path
            elif "HB_CUSTOM_SCHEMA_PATH" in os.environ:
                del os.environ["HB_CUSTOM_SCHEMA_PATH"]
            try:
                baseline_args = argparse.Namespace(
                    source=source,
                    path=baseline_path,
                    run_meta=baseline_meta_path,
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
                cli.run(baseline_args)
                report_dirs = []
                for current_item in current_fields:
                    current_path = _save_upload_bytes(
                        current_item["data"],
                        current_item["filename"],
                        os.path.join(workspace, "runs"),
                        "current",
                    )
                    current_args = argparse.Namespace(
                        source=source,
                        path=current_path,
                        run_meta=current_meta_path,
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
                    report_dirs.append(cli.run(current_args))
            except Exception as exc:
                message = str(exc)
                if "schema error" in message.lower() or "schema_error" in message.lower():
                    message = f"Schema mismatch: {message}"
                self._render(self._page(error=message), status=400)
                return
            finally:
                if previous_schema:
                    os.environ["HB_CUSTOM_SCHEMA_PATH"] = previous_schema
                elif "HB_CUSTOM_SCHEMA_PATH" in os.environ:
                    del os.environ["HB_CUSTOM_SCHEMA_PATH"]
            report_links = []
            bundle_links = []
            for report_dir in report_dirs:
                report_path = os.path.join(report_dir, "drift_report.html")
                _open_report(report_path)
                bundle_path = _support_bundle(report_dir, os.path.join(workspace, "logs"))
                report_links.append(f"file://{report_path}")
                bundle_links.append(f"/download?file={bundle_path}")
            self._render(
                self._page(
                    success=f"Baseline + current compared. Reports generated: {len(report_dirs)}",
                    report_link=report_links,
                    bundle_link=bundle_links,
                )
            )
            return

        if isinstance(data_field, list):
            data_fields = [item for item in data_field if item and item.get("filename")]
        else:
            data_fields = [data_field] if data_field and data_field.get("filename") else []
        if not data_fields:
            self._render(self._page(error="Please upload a data file."), status=400)
            return

        run_meta_path = None
        if run_meta_field and run_meta_field.get("filename"):
            run_meta_path = _save_upload_bytes(
                run_meta_field["data"], run_meta_field["filename"], os.path.join(workspace, "logs"), "run_meta"
            )
        if not run_meta_path:
            run_meta_path = _write_run_meta(_default_run_meta(source), workspace, "run_meta")

        previous_schema = os.environ.get("HB_CUSTOM_SCHEMA_PATH")
        if custom_schema_path:
            os.environ["HB_CUSTOM_SCHEMA_PATH"] = custom_schema_path
        elif "HB_CUSTOM_SCHEMA_PATH" in os.environ:
            del os.environ["HB_CUSTOM_SCHEMA_PATH"]
        try:
            report_dirs = []
            dest_dir = os.path.join(workspace, "baselines" if mode == "baseline" else "runs")
            for data_item in data_fields:
                data_path = _save_upload_bytes(data_item["data"], data_item["filename"], dest_dir, mode)
                args = argparse.Namespace(
                    source=source,
                    path=data_path,
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
                report_dirs.append(cli.run(args))
        except Exception as exc:
            message = str(exc)
            if "schema error" in message.lower() or "schema_error" in message.lower():
                message = f"Schema mismatch: {message}"
            self._render(self._page(error=message), status=400)
            return
        finally:
            if previous_schema:
                os.environ["HB_CUSTOM_SCHEMA_PATH"] = previous_schema
            elif "HB_CUSTOM_SCHEMA_PATH" in os.environ:
                del os.environ["HB_CUSTOM_SCHEMA_PATH"]

        report_links = []
        bundle_links = []
        for report_dir in report_dirs:
            report_path = os.path.join(report_dir, "drift_report.html")
            _open_report(report_path)
            bundle_path = _support_bundle(report_dir, os.path.join(workspace, "logs"))
            report_links.append(f"file://{report_path}")
            bundle_links.append(f"/download?file={bundle_path}")
        self._render(
            self._page(
                success=f"Reports generated: {len(report_dirs)}",
                report_link=report_links,
                bundle_link=bundle_links,
            )
        )

    def _schema_confirm_block(self, payload, workspace):
        columns_json = json.dumps(payload["columns"]).replace("'", "&#39;")
        types_json = json.dumps(payload["types"]).replace("'", "&#39;")
        rows = []
        for col in payload["columns"]:
            col_type = payload["types"].get(col, "str")
            rows.append(
                f"<tr><td>{col}</td><td>{col_type}</td>"
                f"<td><input type='checkbox' name='required_cols' value='{col}' checked /></td></tr>"
            )
        rows_html = "\n".join(rows)
        delimiter_label = "Tab" if payload["delimiter"] == "\t" else "Comma"
        return f"""
        <div class="card">
          <div class="label">Schema Builder: Confirm Fields</div>
          <div class="muted">Detected delimiter: {delimiter_label}</div>
          <form method="post" enctype="multipart/form-data" action="/schema/confirm">
            <input type="hidden" name="workspace" value="{workspace}" />
            <input type="hidden" name="schema_name" value="{payload['name']}" />
            <input type="hidden" name="delimiter" value="{payload['delimiter']}" />
            <input type="hidden" name="columns" value='{columns_json}' />
            <input type="hidden" name="types" value='{types_json}' />
            <table style="width:100%; border-collapse: collapse; margin-top: 10px;">
              <thead>
                <tr>
                  <th style="text-align:left; border-bottom: 1px solid #e6e2d7;">Column</th>
                  <th style="text-align:left; border-bottom: 1px solid #e6e2d7;">Type</th>
                  <th style="text-align:left; border-bottom: 1px solid #e6e2d7;">Required</th>
                </tr>
              </thead>
              <tbody>
                {rows_html}
              </tbody>
            </table>
            <div class="actions" style="margin-top: 10px;">
              <button type="submit">Save Schema</button>
            </div>
          </form>
        </div>
        """

    def _page(self, error=None, success=None, report_link=None, bundle_link=None, schema_builder_html=None):
        workspace = _default_workspace()
        custom_sources = _load_custom_sources(workspace)
        sources = [
            ("pba_excel", "PBA Excel/CSV"),
            ("nasa_http_tsv", "NASA HTTP TSV"),
            ("cmapss_fd001", "CMAPSS FD001"),
            ("cmapss_fd002", "CMAPSS FD002"),
            ("cmapss_fd003", "CMAPSS FD003"),
            ("cmapss_fd004", "CMAPSS FD004"),
            ("smap_msl", "SMAP/MSL Telemetry"),
        ]
        for item in custom_sources:
            name = item.get("name")
            schema_path = item.get("schema_path")
            if name and schema_path:
                sources.append((f"custom|{schema_path}", f"Custom: {name}"))
        options = "\n".join([f'<option value="{key}">{label}</option>' for key, label in sources])
        previous_options = options
        notice = (
            "Local only. No data leaves this machine. Files are stored under the selected workspace."
        )
        status = ""
        if error:
            status = f"<div class='error'>Error: {error}</div>"
        elif success:
            status = f"<div class='success'>{success}</div>"
        report_html = ""
        if report_link:
            report_links = report_link if isinstance(report_link, list) else [report_link]
            items = "".join([f'<li><a href="{link}">{link}</a></li>' for link in report_links])
            report_html = f'<div class="link">Report links:<ul>{items}</ul></div>'
        bundle_html = ""
        if bundle_link:
            bundle_links = bundle_link if isinstance(bundle_link, list) else [bundle_link]
            items = "".join([f'<li><a href="{link}">Download ZIP</a></li>' for link in bundle_links])
            bundle_html = f'<div class="link">Support bundles:<ul>{items}</ul></div>'
        schema_html = schema_builder_html or ""

        return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Harmony Bridge Local UI</title>
  <style>
    :root {{
      --bg: #f6f2ec;
      --panel: #ffffff;
      --ink: #1f2a33;
      --muted: #5b6b76;
      --accent: #0e6f8a;
      --accent-2: #d9822b;
      --shadow: 0 12px 30px rgba(24, 39, 75, 0.12);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Avenir Next", "Trebuchet MS", "Gill Sans", sans-serif;
      background: radial-gradient(circle at top left, #fdf8f0, var(--bg));
      color: var(--ink);
    }}
    header {{
      padding: 28px 36px 18px;
      background: linear-gradient(120deg, #f7efe2 0%, #f3f7f9 100%);
      border-bottom: 1px solid #e6e2d7;
    }}
    header h1 {{ margin: 0 0 6px; font-size: 26px; }}
    header p {{ margin: 0; color: var(--muted); font-size: 14px; }}
    main {{ padding: 24px 36px 40px; display: grid; gap: 18px; }}
    .banner {{
      background: #e7f6ee;
      color: #2f855a;
      padding: 10px 14px;
      border-radius: 12px;
      font-size: 13px;
      font-weight: 600;
    }}
    .card {{
      background: var(--panel);
      border-radius: 14px;
      padding: 16px 18px;
      box-shadow: var(--shadow);
      border: 1px solid #edf0f3;
    }}
    .label {{
      text-transform: uppercase;
      font-size: 12px;
      letter-spacing: 1px;
      color: var(--muted);
      margin-bottom: 6px;
    }}
    .actions {{ display: flex; gap: 10px; flex-wrap: wrap; }}
    button {{
      border: none;
      border-radius: 10px;
      padding: 8px 12px;
      font-weight: 600;
      cursor: pointer;
      background: var(--accent);
      color: #fff;
    }}
    input, select {{
      width: 100%;
      padding: 8px 10px;
      border-radius: 10px;
      border: 1px solid #d7dde2;
      font-size: 14px;
    }}
    .grid {{
      display: grid;
      gap: 12px;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    }}
    .error {{ color: #b91c1c; font-weight: 600; }}
    .success {{ color: #2f855a; font-weight: 600; }}
    .link a {{ color: var(--accent); }}
    .muted {{ color: var(--muted); font-size: 13px; }}
  </style>
</head>
<body>
  <header>
    <h1>Harmony Bridge Local UI</h1>
    <p>Upload baseline + current files and generate drift reports locally.</p>
  </header>
  <main>
    <div class="banner">{notice}</div>
    {status}
    {report_html}
    {bundle_html}
    {schema_html}

    <div class="card">
      <div class="label">Project Type</div>
      <div class="muted">Is this a previous project or a new one?</div>
      <div class="actions" style="margin-top: 10px;">
        <label><input type="radio" name="project-mode" value="new" checked onclick="setProjectMode('new')" /> New project</label>
        <label><input type="radio" name="project-mode" value="previous" onclick="setProjectMode('previous')" /> Previous project</label>
      </div>
    </div>

    <div class="card">
      <div class="label">New Project: Baseline + Compare</div>
      <div class="muted">Auto-schema runs in the background based on your baseline file.</div>
      <form method="post" enctype="multipart/form-data" action="/run">
        <input type="hidden" name="mode" value="compare" />
        <input type="hidden" name="auto_schema" value="1" />
        <div class="grid">
          <div>
            <label>Workspace path</label>
            <input name="workspace" type="text" value="{workspace}" />
          </div>
          <div>
            <label>Project name</label>
            <input name="project_name" type="text" placeholder="nasa_logs" />
          </div>
          <div>
            <label>Baseline file</label>
            <input name="baseline_file" type="file" required />
          </div>
          <div>
            <label>Current file</label>
            <input name="current_file" type="file" multiple required />
            <div class="muted">Hold Cmd (Mac) or Ctrl (Windows) to select multiple files.</div>
          </div>
          <div>
            <label>Baseline run_meta.json (optional)</label>
            <input name="baseline_meta" type="file" />
          </div>
          <div>
            <label>Current run_meta.json (optional)</label>
            <input name="current_meta" type="file" />
          </div>
        </div>
        <div class="actions" style="margin-top: 10px;">
          <button type="submit">Install Baseline + Compare</button>
        </div>
      </form>
    </div>

    <div class="card">
      <div class="label">Previous Project: Compare (current only)</div>
      <div class="muted">Use this when a baseline is already installed.</div>
      <form method="post" enctype="multipart/form-data" action="/run">
        <input type="hidden" name="mode" value="current" />
        <div class="grid">
          <div>
            <label>Workspace path</label>
            <input name="workspace" type="text" value="{workspace}" />
          </div>
          <div>
            <label>Source type</label>
            <select name="source">{previous_options}</select>
          </div>
          <div>
            <label>Current run file</label>
            <input name="data_file" type="file" multiple required />
            <div class="muted">Hold Cmd (Mac) or Ctrl (Windows) to select multiple files.</div>
          </div>
          <div>
            <label>Current run_meta.json (optional)</label>
            <input name="run_meta" type="file" />
          </div>
        </div>
        <div class="actions" style="margin-top: 10px;">
          <button type="submit">Run Compare</button>
        </div>
      </form>
    </div>

    <div class="card">
      <div class="label">Advanced</div>
      <div class="muted">Optional tools for power users. Most users can skip this.</div>
      <div class="actions" style="margin-top: 10px;">
        <button type="button" onclick="toggleAdvanced()">Show Advanced</button>
      </div>
      <div id="advanced-panel" style="display:none; margin-top: 12px;">
        <div class="card" style="box-shadow:none; border:1px dashed #e6e2d7;">
          <div class="label">Feedback Hub</div>
          <div class="muted">Start the Local Feedback Service: <code>bin/hb feedback serve</code></div>
          <div class="muted">Open: <a href="http://127.0.0.1:8765/" target="_blank">http://127.0.0.1:8765/</a></div>
        </div>
        <div class="card" style="box-shadow:none; border:1px dashed #e6e2d7; margin-top: 10px;">
          <div class="label">Schema Builder</div>
          <div class="muted">Upload a CSV/TSV sample to infer columns and types.</div>
          <form method="post" enctype="multipart/form-data" action="/schema/build">
            <div class="grid" style="margin-top: 8px;">
              <div>
                <label>Workspace path</label>
                <input name="workspace" type="text" value="{workspace}" />
              </div>
              <div>
                <label>Schema name</label>
                <input name="schema_name" type="text" placeholder="my_dataset" required />
              </div>
              <div>
                <label>Sample file (CSV/TSV)</label>
                <input name="sample_file" type="file" required />
              </div>
            </div>
            <div class="actions" style="margin-top: 10px;">
              <button type="submit">Build Schema</button>
            </div>
          </form>
        </div>
        <div class="card" style="box-shadow:none; border:1px dashed #e6e2d7; margin-top: 10px;">
          <div class="label">Watch Folder</div>
          <div class="muted">Local only. Polls for new files on a timer.</div>
          <div class="grid" style="margin-top: 8px;">
            <div>
              <label>Workspace path</label>
              <input id="watch-workspace" type="text" value="{workspace}" />
            </div>
            <div>
              <label>Watch directory</label>
              <input id="watch-dir" type="text" placeholder="/path/to/incoming" />
            </div>
            <div>
              <label>Source type</label>
              <select id="watch-source">{options}</select>
            </div>
            <div>
              <label>File pattern</label>
              <input id="watch-pattern" type="text" value="*" />
            </div>
            <div>
              <label>Interval</label>
              <select id="watch-interval">
                <option value="604800" selected>Weekly</option>
                <option value="2592000">Monthly</option>
                <option value="31536000">Yearly</option>
              </select>
            </div>
          </div>
          <div class="actions" style="margin-top: 10px;">
            <button type="button" onclick="startWatch()">Start Watch</button>
            <button type="button" onclick="stopWatch()" style="background: #d9822b;">Stop Watch</button>
          </div>
          <div class="muted" id="watch-status" style="margin-top: 6px;"></div>
        </div>
      </div>
    </div>
  </main>
  <script>
    function setProjectMode(mode) {{
      const cards = document.querySelectorAll('.card');
      cards.forEach(card => {{
        const label = card.querySelector('.label');
        if (!label) return;
        if (label.textContent.startsWith('New Project')) {{
          card.style.display = mode === 'new' ? 'block' : 'none';
        }}
        if (label.textContent.startsWith('Previous Project')) {{
          card.style.display = mode === 'previous' ? 'block' : 'none';
        }}
      }});
    }}
    function toggleAdvanced() {{
      const panel = document.getElementById('advanced-panel');
      const visible = panel.style.display === 'block';
      panel.style.display = visible ? 'none' : 'block';
    }}
    setProjectMode('new');
    function startWatch() {{
      const form = new FormData();
      form.append('workspace', document.getElementById('watch-workspace').value);
      form.append('watch_dir', document.getElementById('watch-dir').value);
      form.append('source', document.getElementById('watch-source').value);
      form.append('pattern', document.getElementById('watch-pattern').value);
      form.append('interval', document.getElementById('watch-interval').value);
      fetch('/watch/start', {{method: 'POST', body: form}}).then(r => r.json()).then(data => {{
        document.getElementById('watch-status').textContent = 'Watch started.';
      }}).catch(() => {{
        document.getElementById('watch-status').textContent = 'Unable to start watch.';
      }});
    }}
    function stopWatch() {{
      fetch('/watch/stop', {{method: 'POST'}}).then(r => r.json()).then(data => {{
        document.getElementById('watch-status').textContent = 'Watch stopped.';
      }}).catch(() => {{
        document.getElementById('watch-status').textContent = 'Unable to stop watch.';
      }});
    }}
  </script>
</body>
</html>
"""


def serve_local_ui(port=8890):
    server = HTTPServer(("127.0.0.1", int(port)), LocalUIHandler)
    server.watch_active = False
    server.watch_config = {}
    server.timeout = 1
    last_watch = 0
    print(f"local UI listening on http://127.0.0.1:{port}")
    while True:
        server.handle_request()
        if getattr(server, "watch_active", False):
            config = server.watch_config or {}
            interval = int(config.get("interval", 120))
            now = time.time()
            if now - last_watch >= interval:
                last_watch = now
                watch_dir = config.get("watch_dir")
                source = config.get("source", "pba_excel")
                pattern = config.get("pattern", "*")
                workspace = config.get("workspace")
                watch.run_watch(
                    watch_dir=watch_dir,
                    source=source,
                    pattern=pattern,
                    interval=interval,
                    workspace=workspace,
                    run_meta=None,
                    run_meta_dir=None,
                    open_report=True,
                    once=True,
                )
