import os

from ingest.parsers import smap_msl_telemetry


def parse(path):
    ext = os.path.splitext(path)[1].lower()
    if ext not in {".npy", ".csv"}:
        raise ValueError("SCHEMA_ERROR: SMAP/MSL expects .npy or .csv telemetry files")
    series = smap_msl_telemetry.load_series_from_path(path)
    return smap_msl_telemetry.metrics_from_series(series)
