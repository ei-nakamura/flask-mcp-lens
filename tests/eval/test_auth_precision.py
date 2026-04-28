from pathlib import Path

import pytest
import yaml

import flask_mcp_lens.tools as tools
from flask_mcp_lens.index import IndexManager
from flask_mcp_lens.tools.find_potentially_unprotected_routes import (
    find_potentially_unprotected_routes,
)

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"
TRUTH_FILE = Path(__file__).parent / "truth_full_app.yaml"


@pytest.fixture
def full_app_manager():
    manager = IndexManager(FIXTURES_DIR / "full_app")
    tools.init(manager)
    return manager


def load_truth():
    return yaml.safe_load(TRUTH_FILE.read_text())


def test_unprotected_precision(full_app_manager):
    truth = load_truth()
    result = find_potentially_unprotected_routes()
    data = result["data"]
    flagged_endpoints = {
        r["endpoint"]
        for r in data["definitely_unprotected"] + data["likely_unprotected"]
    }
    true_unprotected = set(truth.get("unprotected", []))
    false_positives = [e for e in flagged_endpoints if e not in true_unprotected]
    total_flagged = len(flagged_endpoints)
    precision = 1.0 - len(false_positives) / max(total_flagged, 1)
    assert precision >= 0.7, (
        f"Precision {precision:.2%} < 70%. False positives: {false_positives}"
    )
