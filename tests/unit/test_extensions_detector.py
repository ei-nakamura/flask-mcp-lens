

from flask_mcp_lens.extensions.detector import ExtensionDetector


def test_detect_flask_login_from_requirements(tmp_path):
    req = tmp_path / "requirements.txt"
    req.write_text("Flask-Login>=0.6.0\nFlask>=2.0\n")
    exts, unsupported = ExtensionDetector().detect(tmp_path)
    assert any(e.name == "flask_login" for e in exts)
    assert exts[0].confidence == "medium"
    assert "requirements.txt" in exts[0].declared_in


def test_detect_flask_jwt_from_pyproject(tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        '[project]\ndependencies = ["flask-jwt-extended>=4.0.0"]\n'
    )
    exts, unsupported = ExtensionDetector().detect(tmp_path)
    assert any(e.name == "flask_jwt_extended" for e in exts)


def test_unsupported_extension(tmp_path):
    req = tmp_path / "requirements.txt"
    req.write_text("flask-admin>=3.0\n")
    exts, unsupported = ExtensionDetector().detect(tmp_path)
    assert exts == []
    assert any(u["package"] == "flask-admin" for u in unsupported)


def test_no_manifests(tmp_path):
    exts, unsupported = ExtensionDetector().detect(tmp_path)
    assert exts == []
    assert unsupported == []
