from flask_mcp_lens.auth.detector import AuthDetector
from flask_mcp_lens.config import Config
from flask_mcp_lens.models import Decorator, Route, SourceLoc, ViewFunction


def _make_route(decorators: list[str], blueprint: str | None = None) -> Route:
    loc = SourceLoc(file="app.py", line=1)
    decs = tuple(Decorator(name=n, location=loc) for n in decorators)
    view = ViewFunction(
        name="view", qualname="view", location=loc, decorators=decs, source_excerpt=""
    )
    return Route(
        url="/test", methods=("GET",), endpoint="test",
        blueprint=blueprint, view=view, definition=loc,
    )


def test_high_confidence_decorator():
    route = _make_route(["login_required"])
    result = AuthDetector().evaluate(route, {}, Config())
    assert result.max_confidence == "high"
    assert len(result.signals) == 1
    assert result.signals[0].kind == "decorator"


def test_no_auth_signal():
    route = _make_route([])
    result = AuthDetector().evaluate(route, {}, Config())
    assert result.max_confidence == "none"
    assert result.signals == ()


def test_low_confidence_heuristic():
    route = _make_route(["check_auth_token"])
    result = AuthDetector().evaluate(route, {}, Config())
    assert result.max_confidence == "low"


def test_blacklist_skips_decorator():
    cfg = Config()
    cfg.auth.blacklist_decorators = ["login_required"]
    route = _make_route(["login_required"])
    result = AuthDetector().evaluate(route, {}, cfg)
    assert result.max_confidence == "none"


def test_extra_decorator_user_declared():
    cfg = Config()
    cfg.auth.extra_decorators = ["require_admin"]
    route = _make_route(["require_admin"])
    result = AuthDetector().evaluate(route, {}, cfg)
    assert result.max_confidence == "high"
    assert result.signals[0].kind == "user_declared"


def test_jwt_required_high():
    route = _make_route(["jwt_required"])
    result = AuthDetector().evaluate(route, {}, Config())
    assert result.max_confidence == "high"
