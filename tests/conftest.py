from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"

@pytest.fixture
def single_app_root():
    return FIXTURES_DIR / "single_app"

@pytest.fixture
def factory_one_bp_root():
    return FIXTURES_DIR / "factory_one_bp"

@pytest.fixture
def factory_nested_bp_root():
    return FIXTURES_DIR / "factory_nested_bp"

@pytest.fixture
def full_app_root():
    return FIXTURES_DIR / "full_app"
