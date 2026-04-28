import textwrap
from pathlib import Path

from flask_mcp_lens.analyzer.ast_visitor import visit_file


def write_py(tmp_path: Path, name: str, source: str) -> Path:
    path = tmp_path / name
    path.write_text(textwrap.dedent(source))
    return path


class TestAppInstanceDetection:
    def test_module_level_flask_app(self, tmp_path):
        path = write_py(tmp_path, "app.py", """
            from flask import Flask
            app = Flask(__name__)
        """)
        result = visit_file(path, tmp_path)
        assert result is not None
        assert len(result.app_instances) == 1
        inst = result.app_instances[0]
        assert inst.var_name == "app"
        assert inst.is_factory is False

    def test_factory_function_flask_app(self, tmp_path):
        path = write_py(tmp_path, "factory.py", """
            from flask import Flask
            def create_app():
                app = Flask(__name__)
                return app
        """)
        result = visit_file(path, tmp_path)
        assert result is not None
        assert len(result.app_instances) == 1
        inst = result.app_instances[0]
        assert inst.is_factory is True
        assert inst.factory_func_name == "create_app"


class TestBlueprintDetection:
    def test_blueprint_assignment(self, tmp_path):
        path = write_py(tmp_path, "views.py", """
            from flask import Blueprint
            main_bp = Blueprint("main_bp", __name__)
        """)
        result = visit_file(path, tmp_path)
        assert result is not None
        assert len(result.blueprints) == 1
        bp = result.blueprints[0]
        assert bp.bp_name == "main_bp"
        assert bp.var_name == "main_bp"


class TestRouteDetection:
    def test_app_route_decorator(self, tmp_path):
        path = write_py(tmp_path, "app.py", """
            from flask import Flask
            app = Flask(__name__)

            @app.route("/hello")
            def hello():
                return "hello"
        """)
        result = visit_file(path, tmp_path)
        assert result is not None
        assert len(result.routes) == 1
        route = result.routes[0]
        assert route.url == "/hello"
        assert route.func_name == "hello"

    def test_add_url_rule(self, tmp_path):
        path = write_py(tmp_path, "app.py", """
            from flask import Flask
            app = Flask(__name__)

            def hello():
                return "hello"

            app.add_url_rule("/hello", view_func=hello)
        """)
        result = visit_file(path, tmp_path)
        assert result is not None
        assert len(result.add_url_rules) == 1
        rule = result.add_url_rules[0]
        assert rule.rule == "/hello"
        assert rule.view_func_name == "hello"


class TestRegisterBlueprintDetection:
    def test_register_blueprint_call(self, tmp_path):
        path = write_py(tmp_path, "app.py", """
            from flask import Flask
            from views import main_bp
            app = Flask(__name__)
            app.register_blueprint(main_bp, url_prefix="/main")
        """)
        result = visit_file(path, tmp_path)
        assert result is not None
        assert len(result.register_blueprints) == 1
        reg = result.register_blueprints[0]
        assert reg.parent_var == "app"
        assert reg.child_var == "main_bp"
        assert reg.url_prefix_override == "/main"


class TestBeforeRequestDetection:
    def test_before_request_decorator(self, tmp_path):
        path = write_py(tmp_path, "app.py", """
            from flask import Flask
            app = Flask(__name__)

            @app.before_request
            def check_auth():
                pass
        """)
        result = visit_file(path, tmp_path)
        assert result is not None
        assert len(result.before_requests) == 1
        hook = result.before_requests[0]
        assert hook.func_name == "check_auth"
        assert hook.owner_var == "app"


class TestImportAliasResolution:
    def test_blueprint_alias_detected(self, tmp_path):
        path = write_py(tmp_path, "views.py", """
            from flask import Blueprint as BP
            main_bp = BP("main_bp", __name__)
        """)
        result = visit_file(path, tmp_path)
        assert result is not None
        assert len(result.blueprints) == 1
        bp = result.blueprints[0]
        assert bp.bp_name == "main_bp"
