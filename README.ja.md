# flask-mcp-lens

[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![Status](https://img.shields.io/badge/status-Phase%201%20MVP-orange)](docs/design-phase1.md)
[![License](https://img.shields.io/badge/license-MIT-green)](#ライセンス)

> English version: [README.md](README.md)

[Flask](https://flask.palletsprojects.com/) アプリケーションの構造を、
LLM エージェント（Claude Code など）に **MCP (Model Context Protocol) ツール群**
として提供する OSS の MCP サーバです。

`grep` では答えにくい次のような質問に、ツール呼び出し 1 回で答えます。

- 「`GET /api/v1/users/<id>` を叩いたとき、どの `before_request` が走る？」
- 「app factory はどこで定義されていて、どの Blueprint が登録されている？」
- 「`/api/v1` 配下で `POST` を受け付けるルートを全部出して」

Phase 1 は **完全な静的解析** で動作します。Flask アプリは import も実行も
されません。プロジェクト内の Python AST を走査し、Blueprint /
`register_blueprint` 呼び出し / route デコレータを解決して、stdio 経由の
MCP として結果を返します。

---

## ステータス

本リリースは **Phase 1 MVP** です。スコープは
[docs/design-phase1.md](docs/design-phase1.md) に従います。

- 5 つの MCP ツール（後述）
- Flask の import エイリアスを追跡する静的 AST 解析
- ファイル mtime で無効化される gzip + JSON キャッシュ
- 3 つのフィクスチャ + ユニット / 統合 / パフォーマンステスト

以下は **Phase 1 のスコープ外** で、Phase 2 以降に実装します
（[docs/design-phase2.md](docs/design-phase2.md) ほか参照）。

- 認証関連の検出
- Flask-Login / Flask-RESTful 等の拡張検出
- 未登録 Blueprint の検出
- `MethodView` / Class-based view
- 設定ファイル `.flask-mcp-lens.toml`
- 実行時情報を併用するハイブリッド解析
- `watchdog` による差分解析

---

## 機能（Phase 1）

| ツール | 用途 |
|--------|------|
| `find_app_factory` | `Flask(...)` インスタンス化や `create_app` 系ファクトリを信頼度付きで列挙 |
| `get_app_overview` | app factory の場所、Blueprint 数、ルート数の概要と Markdown サマリ |
| `list_routes` | 解決済みルート一覧。`blueprint` / `url_prefix` / HTTP `method` でフィルタ可 |
| `get_route_handler` | `(url, method)` を受け取り、マッチしたルートの実行チェーン（app→blueprint 順の `before_request`、デコレータ列、view 関数のソース抜粋）を返す |
| `refresh_index` | キャッシュを破棄し、その場でインデックスを再構築 |

各ツールの戻り値は共通エンベロープに包まれた JSON です。

```jsonc
{
  "tool": "list_routes",
  "version": "1.0",
  "analysis_mode": "static",
  "warnings": [],
  "data": { /* ツールごとのペイロード */ }
}
```

### 対応する Flask 構文

- `app = Flask(__name__)`（モジュールトップレベル）と `def create_app(...)` ファクトリ
- `Blueprint(...)` 定義 — `from flask import Blueprint as BP` のようなエイリアスにも対応
- 入れ子 Blueprint（`parent_bp.register_blueprint(child_bp)`）— 最大 2 段
- `@app.route` / `@bp.route` デコレータ（`methods=`, `endpoint=` kwargs に対応）
- `app.add_url_rule(rule, endpoint, view_func, methods=...)`
- `@app.before_request` / `@bp.before_request` デコレータ、および `app.before_request(func)` の呼び出し形式
- URL コンバータ: `<name>`, `<int:name>`, `<float:name>`, `<path:name>`, `<uuid:name>`, `<string:name>`

静的に解決できない値（例: `url_prefix=os.environ.get(...)`、
`add_url_rule(..., view_func=動的な値)`）は `warnings` に記録され、
推測ではなく **スキップ** されます。

---

## インストール

Python **3.10 以上** が必要です。

```bash
# Phase 1 段階では clone からのインストールを推奨
git clone https://github.com/<your-account>/flask-mcp-lens.git
cd flask-mcp-lens
pip install -e .

# CLI が PATH に通っているか確認
flask-mcp-lens --help
```

ランタイム依存は [`mcp`](https://pypi.org/project/mcp/) (`>=0.9`) のみです。

テスト用 extras を入れる場合:

```bash
pip install -e ".[test]"
```

---

## 使い方

### MCP サーバとして

`flask-mcp-lens` は **stdio** で MCP プロトコルを話します。エージェント側から
起動される前提です。

Claude Code の場合、MCP 設定に次のように追加します。

```json
{
  "mcpServers": {
    "flask-mcp-lens": {
      "command": "flask-mcp-lens",
      "args": ["--root", "/path/to/your/flask/project"]
    }
  }
}
```

`--root` を省略すると、起動時の cwd を解析対象にします。

### ロギング

ログは **stderr** に出力します（stdout は MCP プロトコル専用）。
レベルは環境変数 `FLASK_MCP_LENS_LOG`（`debug`, `info`, …）で切り替えます。

### 追加の除外設定

組み込みの除外（`tests/`, `__pycache__/`, `.venv/`, `build/` 等）に加えて、
環境変数 `FLASK_MCP_LENS_EXCLUDE` にカンマ区切りのグロブを指定できます。

```bash
FLASK_MCP_LENS_EXCLUDE="migrations/*,scripts/legacy_*.py" flask-mcp-lens
```

設定ファイル `.flask-mcp-lens.toml` は **Phase 1 では未対応** で、
Phase 2 で実装予定です。

### キャッシュ

最初のツール呼び出し時にプロジェクト直下に
`.flask-mcp-lens/cache/index-v1.json.gz` が作成されます。以降のツール呼び出しは、
解析対象ファイルの mtime とファイル集合が一致する限りキャッシュを再利用します。
`.gitignore` に `.flask-mcp-lens/` を追加してください。

強制再解析が必要な場合は `refresh_index` を呼びます。

---

## 動作例

Phase 1 フィクスチャ
[`tests/fixtures/factory_nested_bp/`](tests/fixtures/factory_nested_bp/) を例に取ります。

```python
# app/__init__.py
def create_app():
    app = Flask(__name__)
    app.register_blueprint(api_v1, url_prefix="/api/v1")
    return app

# app/api/__init__.py    親 Blueprint
api_v1 = Blueprint("api_v1", __name__)
api_v1.register_blueprint(users_api, url_prefix="/users")
api_v1.register_blueprint(posts_api, url_prefix="/posts")

# app/api/users.py       子 Blueprint
users_api = Blueprint("users_api", __name__)

@users_api.route("/<int:user_id>", methods=["GET", "DELETE"])
def get_user(user_id): ...
```

`list_routes` は親子 Blueprint と route の prefix を結合し、
URL `/api/v1/users/<int:user_id>`、`methods: ["DELETE", "GET"]`、
`blueprint: "users_api"`、route デコレータのソース位置を返します。
`get_route_handler("/api/v1/users/<int:user_id>", "GET")` はさらに
`before_request` チェーン（app スコープ → `users_api` スコープの順）と
view 関数の 6 行抜粋を含めて返します。

---

## ディレクトリ構成

```
flask-mcp-lens/
├── pyproject.toml
├── docs/
│   ├── requirements.md
│   ├── design-phase1.md          ← この README が実装する範囲
│   ├── design-phase2.md
│   ├── design-phase3.md
│   └── design-phase4.md
├── src/
│   └── flask_mcp_lens/
│       ├── __main__.py           # python -m flask_mcp_lens
│       ├── server.py             # MCP エントリポイント、ツール登録
│       ├── tools/
│       │   ├── find_app_factory.py
│       │   ├── get_app_overview.py
│       │   ├── list_routes.py
│       │   ├── get_route_handler.py
│       │   └── refresh_index.py
│       ├── index.py              # IndexManager（キャッシュ + 遅延ビルド）
│       ├── cache.py              # gzip + JSON、アトミック書き込み
│       ├── urlmap.py             # コンバータ対応の URL マッチャ
│       ├── models.py             # frozen dataclass 群
│       └── analyzer/
│           ├── scanner.py        # ファイル列挙 + 除外
│           ├── ast_visitor.py    # FlaskASTVisitor
│           ├── resolver.py       # raw ノード → RouteIndex
│           └── imports.py        # `from flask import X as Y` 別名解析
└── tests/
    ├── fixtures/{single_app, factory_one_bp, factory_nested_bp}/
    ├── unit/{test_ast_visitor, test_resolver, test_urlmap, test_cache}.py
    ├── integration/{test_tools_smoke, test_e2e_mcp}.py
    └── perf/test_smoke.py
```

---

## 開発

```bash
pip install -e ".[test]"

# 全テスト
pytest

# 3 フィクスチャに対するスモーク / ゴールデンテストのみ
pytest tests/integration/test_tools_smoke.py
```

`ruff` と `mypy --strict` も使えます（設定は `pyproject.toml`）。

```bash
ruff check src tests
mypy src
```

---

## ロードマップ

| フェーズ | 主な内容 |
|---------|---------|
| **Phase 1** *（本リリース）* | 5 つの MCP ツール、静的 AST 解析、gzip キャッシュ、3 フィクスチャ |
| Phase 2 | 認証検出、拡張ライブラリ検出（Flask-Login / -RESTful 等）、未登録 Blueprint 検出、`MethodView`、`.flask-mcp-lens.toml` |
| Phase 3 | 実行時情報併用のハイブリッド解析、`watchdog` による差分解析 |
| Phase 4 | プラグイン機構、並列解析、HTTP/SSE transport |
| Phase 5+ | 複数 app を持つモノレポ対応 |

詳細は [`docs/design-phase2.md`](docs/design-phase2.md) 以降を参照してください。

---

## ライセンス

MIT.
