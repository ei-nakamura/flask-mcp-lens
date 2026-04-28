import textwrap

from flask_mcp_lens.analyzer.ast_visitor import visit_file

METHODVIEW_SOURCE = textwrap.dedent("""
    from flask import Flask
    from flask.views import MethodView

    app = Flask(__name__)

    class UserView(MethodView):
        def get(self):
            pass

        def post(self):
            pass

    app.add_url_rule("/users", view_func=UserView.as_view("users"))
""")


def test_methodview_detected(tmp_path):
    py_file = tmp_path / "app.py"
    py_file.write_text(METHODVIEW_SOURCE)
    result = visit_file(py_file, tmp_path)
    assert result is not None
    route_methods = {r.methods[0] for r in result.routes}
    assert "GET" in route_methods
    assert "POST" in route_methods


def test_methodview_qualname(tmp_path):
    py_file = tmp_path / "app.py"
    py_file.write_text(METHODVIEW_SOURCE)
    result = visit_file(py_file, tmp_path)
    assert result is not None
    qualnames = {r.func_name for r in result.routes}
    assert "UserView.get" in qualnames
    assert "UserView.post" in qualnames
