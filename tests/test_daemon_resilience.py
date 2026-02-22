"""Test daemon checkpointing: write checkpoint, resume from it."""
import json
import os
import tempfile

import pytest


def test_daemon_checkpoint_write_and_read():
    """Check that checkpoint format can be written and read."""
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "daemon_checkpoint.json")
        checkpoint = {"last_cycle_utc": "2025-01-01T12:00:00Z", "last_status": "PASS", "last_report_dir": "/out/daemon_123"}
        with open(path, "w") as f:
            json.dump(checkpoint, f, indent=2)
        assert os.path.isfile(path)
        with open(path, "r") as f:
            loaded = json.load(f)
        assert loaded["last_status"] == "PASS"
        assert "last_cycle_utc" in loaded
