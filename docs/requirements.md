# flask-mcp-lens 要件定義書

ステータス: ドラフト v1.0
対象リポジトリ: `flask-mcp-lens`
作成日: 2026-04-28

---

## 目次

- [0. 前提（仮定）](#0-前提仮定)
- [1. プロジェクト概要](#1-プロジェクト概要)
- [2. ユースケース](#2-ユースケース)
- [3. 機能要件](#3-機能要件)
- [4. 非機能要件](#4-非機能要件)
- [5. 設計上の主要判断](#5-設計上の主要判断)
- [6. アウトオブスコープ](#6-アウトオブスコープ)
- [7. リスクと未解決事項](#7-リスクと未解決事項)
- [8. 成功指標](#8-成功指標)
- [9. 開発フェーズ計画](#9-開発フェーズ計画)
- [10. ユーザー判断が必要な項目](#10-ユーザー判断が必要な項目)

---

## 0. 前提（仮定）

質問せず以下を仮定として置く。誤っていればこのセクションから訂正する。

| # | 前提 | 根拠/補足 |
|---|------|----------|
| A1 | 配布形態は単一の Python パッケージ（`pip install flask-mcp-lens`）。Docker 等の同梱は不要 | MCP サーバはエージェント側プロセスから stdio で起動されるのが一般的 |
| A2 | MCP transport は stdio のみ。HTTP/SSE は Phase 4 以降 | Claude Code を主ターゲットにすれば stdio で十分 |
| A3 | 対象プロジェクトは「単一リポジトリに 1 つの Flask app（または `create_app()`）」を持つ構成。マイクロサービス的に複数 app が混在する構成は Phase 1 のスコープ外 | 中〜大規模 B2B SaaS の典型 |
| A4 | 対象プロジェクトのソースは MCP サーバを起動した cwd 配下に存在する | `--root` オプションで上書き可能とする |
| A5 | 解析対象に test ディレクトリは含めない（`tests/`, `test_*.py`, `conftest.py` を既定で除外） | テストにダミーの app 定義が散らばるとノイズになる |
| A6 | 1 ルート = 1 view function（`add_url_rule` 直接呼びを含む）。`MethodView` は Phase 2 で扱う | Phase 1 の複雑度を抑える |
| A7 | 開発リソースは 1 名・週 5 日換算 | フェーズ工数の妥当性判断のため |

---

## 1. プロジェクト概要

`flask-mcp-lens` は、Flask 製 Web アプリケーション（中〜大規模、B2B SaaS、API サーバを含む）を解析し、その構造を **MCP (Model Context Protocol) ツール群** として LLM エージェント（特に Claude Code）に提供する OSS。エージェントは「この URL を叩いた時に通る認証チェックは？」「このエンドポイントは Blueprint 経由で本当に登録されているか？」のような、grep では答えられない構造的な問いを、ツール呼び出し 1 回で解決できる。利用者はエージェントを操作する開発者・コードレビュアーで、利用タイミングはコード把握初期、認証監査、リファクタ計画立案。

差別化:

- **ast-structure-map** は Python 一般の AST→Markdown 一括レポート器であり、対話的なツール呼び出し API を持たず、Flask のセマンティクス（Blueprint, before_request, デコレータ実行順）を理解しない。flask-mcp-lens はその逆で、Flask 特化・対話型・必要な情報だけ返す。
- **Bandit / semgrep** はセキュリティ脆弱性パターン検出器であり、ルーティングのトポロジを返すツールではない。flask-mcp-lens は「認証漏れ候補の指摘」までは行うが、CVE 判定や脆弱性カタログ照合は行わない。
- **Pyright** は型検査器であり、ルーティング・Blueprint・拡張ライブラリ設定を要求された粒度で返す機能はない。

---

## 2. ユースケース

### UC1: 認証チェックの追跡

> **開発者**「`/api/v1/users/<id>` にアクセスした時、認証チェックは通っているか？」
> **Claude Code** → `get_route_handler("/api/v1/users/<id>", "GET")` を呼ぶ
> → 戻り値: `before_request` チェーン（順序付き）→ デコレータ列（`@jwt_required` 検出）→ view 関数本体
> → **Claude Code**「`@jwt_required()` で保護されています。`before_request` には認証関連のものはありません。view の冒頭で `current_user` を参照しています。」

### UC2: 新規参画時のオーバービュー取得

> **開発者**「このリポジトリの構成を教えて」
> **Claude Code** → `get_app_overview()` を呼ぶ
> → 戻り値: app factory の場所、登録されている Blueprint 数、ルート総数、検出された Flask 拡張、認証方式の概要
> → **Claude Code** が Markdown サマリで提示

### UC3: 認証漏れ監査

> **レビュアー**「認証なしでアクセスできるエンドポイントを全部リストアップして」
> **Claude Code** → `find_potentially_unprotected_routes()` を呼ぶ
> → 戻り値: 各ルートに信頼度スコア（`unprotected_high` / `unprotected_medium` / `ambiguous`）と判定理由
> → **Claude Code** が「明確に未保護: 3 件 / グレー: 5 件、それぞれの理由は…」と要約

### UC4: Blueprint 登録漏れ調査

> **開発者**「`admin_bp` ってどこで登録されてる？」
> **Claude Code** → `list_blueprints()` を呼ぶ
> → 戻り値: 各 Blueprint の定義位置、`register_blueprint` 呼び出し位置、`url_prefix`、登録されていない Blueprint には `registered: false` と未登録フラグ
> → **Claude Code**「`admin_bp` は `app/blueprints/admin.py:12` で定義されていますが、`register_blueprint` で登録されていません。」

### UC5: API と Web 画面の境界把握

> **開発者**「API エンドポイントだけ抜き出して。Web ページは要らない」
> **Claude Code** → `list_api_endpoints()` を呼ぶ
> → 戻り値: `Content-Type: application/json` を返す or `Flask-RESTful` / `Flask-RESTX` 経由 or URL prefix が `/api` のルート群
> → **Claude Code** が表形式で提示

### UC6: 拡張ライブラリの設定確認

> **開発者**「Flask-Login の設定どうなってる？login_view は？」
> **Claude Code** → `list_extensions()` で Flask-Login の存在を確認 → `get_extension_config("flask_login")` で詳細
> → 戻り値: `LoginManager()` インスタンスの初期化位置、`login_view`、`user_loader` 関数の場所

---

## 3. 機能要件

### 3.1 設計判断

#### 判断 3.1.1: Phase 1 のツール選定

**結論**: Phase 1 には `list_routes`, `get_route_handler`, `get_app_overview`, `find_app_factory` の 4 つを入れる。

**根拠**:

- `list_routes` と `get_route_handler` の 2 つだけでは「app の入口を発見する」工程がエージェント側で迷う。Application Factory が `__init__.py` にあるか `app.py` にあるか `wsgi.py` にあるかは規約がない。`find_app_factory` でこの探索を肩代わりしないと、エージェントは grep を繰り返すことになり、本ツールの存在価値が薄れる。
- `get_app_overview` は新規参画ユースケース（UC2）の主用途で、これがないと「まず何を聞くべきか」がエージェントに伝わらない。出力サイズも小さく、初動コスト低。
- 認証関連（`list_auth_strategies`, `find_potentially_unprotected_routes`）は信頼度スコア設計が要るため Phase 2 に分離。MVP の品質ハードルを下げる。

**却下案**:

- `list_routes` + `get_route_handler` のみ: 上記理由で実用最低限に届かない。
- 9 ツール全部入り MVP: 1〜2 日で動かす制約と矛盾。

#### 判断 3.1.2: ツール粒度（多数の小さなツール vs 1 つの巨大ツール）

**結論**: **多数の小さなツール**。

**根拠**:

- LLM エージェントは必要なツールを選択的に呼ぶため、巨大ペイロードを 1 回返すより、目的別に分割した方が token 消費が少ない。`get_app_overview` が 50KB を返すより、エージェントが `list_routes` だけ呼ぶ方が効率的なケースが多い。
- ツール名そのものが MCP のディスカバリで露出するため、名前で「何ができるか」を伝えられる。

**却下案**:

- 1 つの `query(question_type, params)` ツール: ディスカバリ性が消え、LLM がパラメータを誤る確率が上がる。

#### 判断 3.1.3: 出力フォーマット

**結論**: **JSON を主、Markdown を補助**。`get_app_overview` のみ JSON と Markdown の両方を返す（フィールド名 `summary_markdown`）。それ以外は JSON のみ。

**根拠**:

- LLM の構造化処理は JSON が最も安定。
- 人間が直接読むケースは少なく、Claude Code が要約して提示するため Markdown 必須なのは「最初の 1 画面」だけ。
- 全ツールに Markdown 版を持たせると実装コストとペイロードが倍になる。

**却下案**:

- Markdown のみ: パース失敗時のフォールバックがない。
- 完全な両対応: 実装コストに見合わない。

### 3.2 Phase 1 ツール詳細

すべての出力に共通のメタフィールドを含める:

```jsonc
{
  "tool": "list_routes",
  "version": "1.0",
  "analysis_mode": "static",        // or "hybrid"
  "warnings": [...],                 // 解析中に出た警告
  "data": {...}                      // ツール固有
}
```

#### 3.2.1 `find_app_factory()`

- **シグネチャ**: `find_app_factory() -> JSON`
- **入力**: なし
- **出力**:
  ```jsonc
  {
    "candidates": [
      {
        "kind": "factory_function",   // or "module_level_app"
        "name": "create_app",
        "file": "app/__init__.py",
        "line": 14,
        "params": ["config_name"],
        "confidence": "high"          // high / medium / low
      }
    ],
    "selected": 0                     // candidates のインデックス
  }
  ```
- **返さないもの**: 関数の本体ソースコード（必要なら別途 `Read` で取る）。
- **実装の難所**: 複数候補（`create_app`, `make_app`, `app = Flask(__name__)`）が見つかった時の優先順位付け。`Flask(__name__)` 直書き > `create_app` 型関数の順で確信度を付与（後述の 5.1 の判断と一致）。

#### 3.2.2 `get_app_overview()`

- **シグネチャ**: `get_app_overview() -> JSON`
- **出力**:
  ```jsonc
  {
    "app_factory": { "file": "...", "line": 14 },
    "blueprint_count": 12,
    "route_count": 87,
    "extensions_detected": ["flask_login", "flask_sqlalchemy"],
    "auth_strategies_summary": { "decorator_based": 2, "before_request_based": 0 },
    "summary_markdown": "## アプリ概要\n..."
  }
  ```
- **返さないもの**: ルート 1 件 1 件の詳細（`list_routes` で取る）。
- **実装の難所**: `auth_strategies_summary` を Phase 1 で出すか議論。**結論: Phase 1 では出さない**（信頼度スコア未実装のため誤情報を出すリスク）。Phase 2 で追加。

#### 3.2.3 `list_routes(filter?)`

- **シグネチャ**: `list_routes(filter: { url_prefix?: str, method?: str, blueprint?: str } = None) -> JSON`
- **出力**:
  ```jsonc
  {
    "routes": [
      {
        "url": "/api/v1/users/<id>",
        "methods": ["GET", "DELETE"],
        "endpoint": "users_api.get_user",
        "view_function": "get_user",
        "blueprint": "users_api",
        "definition": { "file": "app/api/users.py", "line": 23 },
        "decorators": ["jwt_required"]
      }
    ],
    "total": 87
  }
  ```
- **返さないもの**: view 関数本体、認証判定の信頼度（Phase 2）。
- **実装の難所**: `add_url_rule` 直接呼びと `@app.route` の両方を拾う。`url_prefix` の継承（Blueprint 入れ子）。

#### 3.2.4 `get_route_handler(url, method)`

- **シグネチャ**: `get_route_handler(url: str, method: str) -> JSON`
- **出力**:
  ```jsonc
  {
    "route": { /* list_routes と同形 */ },
    "execution_chain": [
      { "kind": "before_request", "function": "load_user", "file": "...", "line": 10, "scope": "app" },
      { "kind": "before_request", "function": "check_csrf", "file": "...", "line": 22, "scope": "blueprint:users_api" },
      { "kind": "decorator", "name": "jwt_required", "file": "...", "line": 23 },
      { "kind": "view_function", "name": "get_user", "file": "...", "line": 24, "source_excerpt": "def get_user(id):\n    ..." }
    ]
  }
  ```
- **返さないもの**: ランタイムでしか決定しない after_request の戻り値変更内容。
- **実装の難所**:
  - URL マッチング（Werkzeug の `URLMap` を直接使うか、軽量実装するか）→ **判断: 軽量実装**。Werkzeug の `URLMap` はハイブリッド実行時 `app.url_map` から取れる結果と一致させる必要があるが、本ツールは静的解析を主とするため、コンバータ（`<int:id>`）と HTTP method の組合せを自前でマッチさせる。これにより本ツールは Werkzeug を import する必要がなくなり、ターゲット側 Flask バージョン差異の影響を受けない。
  - `before_request` の app スコープと blueprint スコープの両方を集めて順序通りに並べる。

### 3.3 Phase 2 以降のツール（概要のみ）

| ツール | Phase | 主用途 |
|--------|-------|--------|
| `list_blueprints()` | 2 | Blueprint 登録状態の一覧。未登録 BP の検出 |
| `list_extensions()` | 2 | Flask 拡張の検出と初期化位置 |
| `list_auth_strategies()` | 2 | 検出された認証方式と適用範囲 |
| `find_potentially_unprotected_routes()` | 2 | 認証漏れ候補（信頼度スコア付き） |
| `list_api_endpoints()` | 2 | JSON 返すルート / `/api` prefix / RESTful 経由ルートの抽出 |
| `get_extension_config(name)` | 2 | 拡張ごとの詳細設定 |
| `refresh_index()` | 1 | キャッシュ無効化と再解析（明示的）|
| ハイブリッド解析関連 | 3 | `create_app()` 実行による補完 |

### 3.4 不採用ツール

- **`get_view_source(endpoint)`**: 既存の `Read` ツールで足りる。重複機能を避ける。
- **`grep_routes(pattern)`**: `list_routes(filter=...)` で URL prefix と method のフィルタが効けば十分。任意正規表現マッチは `Grep` で代替可能。

---

## 4. 非機能要件

### 4.1 性能目標

| 指標 | 目標値 | 計測条件 |
|------|--------|----------|
| MCP サーバ起動時間 | 2 秒以内 | cold start、解析は遅延 |
| 初回解析（1 万行） | 5 秒以内 | 標準ノートPC（2025 年クラス）|
| 初回解析（5 万行） | 30 秒以内 | 同上 |
| 初回解析（10 万行） | 120 秒以内（劣化許容） | 同上 |
| ツール応答（解析後） | 1 秒以内 | `list_routes` で 100 ルート |
| メモリ上限 | 500 MB | 10 万行プロジェクト解析時 |

### 4.2 対応バージョン

- **Python**: 3.10+ （根拠: 2026 年時点で 3.9 が EOL 直前。3.10 の `match` 文を解析対象コードで扱う必要があり、本ツール側もそれを動かせる必要がある）
- **Flask**: 2.2+ （3.x も対応。1.x は対象外、根拠: 1.x は EOL でルーティング API も差異が大きく、後方互換コストに見合わない）
- **OS**: Windows / macOS / Linux

### 4.3 設計判断

#### 判断 4.3.1: 静的解析エンジン

**結論**: **Python 標準 `ast` のみ**を使う。Jedi / Pyright / LibCST / RustPython は使わない。

**根拠**:

- 依存最小化が配布性に直結する（MCP サーバはユーザー環境で `pip install` される。重い依存はサポート問い合わせを増やす）。
- ルーティング・Blueprint・デコレータの抽出に必要なのは構文情報のみで、型推論は不要。Jedi/Pyright の能力は過剰。
- `ast` は標準ライブラリのため Python のバージョン追従が自動。

**却下案**:

- **Jedi**: 名前解決の補助に魅力的だが、ルーティング解析の主目的に対しては副次的価値しかない。`from app.auth import login_required as login` のようなエイリアス追跡は、import 解析を自前で書けば足りる範囲。
- **Pyright**: Node.js 必須、起動コスト大、過剰機能。
- **LibCST**: コメント保持が必要なリファクタ用途には強いが、本ツールは読み取り専用。

#### 判断 4.3.2: キャッシュ戦略

**結論**: プロジェクト直下の `.flask-mcp-lens/cache/index.json.gz` に gzip 圧縮 JSON で保存。無効化は **解析対象ファイルのいずれかの mtime > キャッシュ mtime** で全体再解析（Phase 1）。Phase 3 でファイル単位の差分再解析。

**根拠**:

- プロジェクト直下に置くと `.gitignore` 追加だけでチーム全体に影響を与えずに済む。`~/.cache/flask-mcp-lens/<hash>` 案より、リポジトリ移動・複数チェックアウトに強い。
- mtime ベースの全体再解析は実装が単純で、10 万行でも 2 分で再解析できるなら許容範囲。
- gzip 圧縮で 10 万行プロジェクトのキャッシュサイズを 数 MB 程度に抑える。

**却下案**:

- **キャッシュなし**: 起動毎の解析はユーザー体験を損なう。
- **SQLite キャッシュ**: クエリ性能は要らない（一括ロード型）。複雑度の割に得るものが少ない。
- **ファイル単位差分（Phase 1 から）**: 依存グラフの追跡が要り、MVP のスコープを超える。

#### 判断 4.3.3: ファイル変更検知

**結論**: **Phase 1 は明示的 `refresh_index()` ツールのみ**。Phase 3 で watchdog による自動検知を追加（オプトイン、`--watch` フラグ）。

**根拠**:

- watchdog を常駐させると無音のリソース消費が発生し、エージェントが意図しないタイミングで解析が走る。Claude Code のセッションは数十分単位なので、明示 refresh で困る場面は少ない。
- mtime ベースの自動無効化（4.3.2）が次回ツール呼び出し時に効くため、refresh を忘れても致命的ではない。

**却下案**:

- **Phase 1 から watchdog**: 実装コスト + プラットフォーム差異の吸収（特に Windows）でスケジュール圧迫。

---

## 5. 設計上の主要判断（最重要セクション）

### 5.1 ハイブリッド解析の扱い

**結論**: **静的解析を主、ハイブリッド（`create_app()` 実行）を Phase 3 のオプトインオプションとして補助**。デフォルトは静的のみ。

**根拠**:

- 静的解析は失敗してもユーザー環境を汚さない。MCP サーバとして最低限信頼されるべき性質。
- 一方、Application Factory パターン下では以下が静的に解決不能なケースがある:
  - 条件付き Blueprint 登録 (`if config['ENABLE_ADMIN']: app.register_blueprint(admin_bp)`)
  - ループ内登録 (`for bp in plugin_blueprints: app.register_blueprint(bp)`)
  - 動的 url_prefix（環境変数からの値注入）
- これらを取りに行くにはハイブリッド解析が要るが、副作用（DB 接続、外部 API、ファイル書き込み）が予測困難。
- 解決策として、ハイブリッドは「ユーザーが明示的にオプトインしたプロジェクトに限り、隔離環境で実行」する。

**ハイブリッド実行の設計**（Phase 3）:

- **オプトイン**: `.flask-mcp-lens.toml` に `[hybrid] enabled = true` がある場合のみ実行。MCP サーバ起動時にもログで明示。
- **副作用抑止**:
  - 環境変数 `TESTING=true`, `FLASK_ENV=testing` を強制注入
  - `os.environ.update(user_provided_overrides)` をユーザー設定で許可
  - DB URI を SQLite in-memory に強制差し替え（ユーザーがブラックリストする方式: 既定で `SQLALCHEMY_DATABASE_URI` を `sqlite:///:memory:` に上書き）
  - `requests`, `httpx`, `urllib` の `socket.create_connection` を monkey-patch して外部通信を遮断
- **失敗時のフォールバック**: 静的解析結果のみ返し、`warnings` に「ハイブリッド解析失敗: <例外メッセージ>」を含める。
- **セキュリティ**: README と起動時ログで「ハイブリッドはターゲットプロジェクトの任意コードを実行する」ことを明示。CI で MCP サーバを動かすユースケースには「未知のリポジトリには使うな」と警告。
- **`create_app()` の引数**: 引数を持つ場合、`.flask-mcp-lens.toml` の `[hybrid.factory_args]` から渡す。設定がなければ静的解析にフォールバック。

**却下案**:

- **実行のみ**: 副作用が制御できないプロジェクトで使えない。失敗時の体験が悲惨。
- **静的のみ**: 上記の動的登録パターンを永続的に取り逃す。中規模以上の実プロジェクトで顕在化する欠陥。
- **デフォルトでハイブリッド有効**: セキュリティ的に許容できない（npm install で run-script が動くのと同じリスク）。

### 5.2 拡張ライブラリ対応の戦略

**結論**:

- **主要 5 つを本体に組み込む**: Flask-Login, Flask-SQLAlchemy, Flask-RESTful, Flask-RESTX, Flask-JWT-Extended
- **Phase 1 に組み込むのは Flask-Login と Flask-JWT-Extended のみ**（認証検出に必要）
- **Phase 2 で残り 3 つ**
- **プラグイン機構は Phase 4 で検討**（`flask_mcp_lens.plugins` entry point）

**検出方法**: `requirements.txt` / `pyproject.toml` / `Pipfile` の **依存リストと**、コード中の `import` 文の **両方**を見る。両方一致したら検出確定、片方だけなら `confidence: medium` で報告。

**根拠**:

- プラグイン機構をいきなり作ると MVP が膨らむ。プラグイン API 設計には複数の利用者が必要だが、現時点で flask-mcp-lens ユーザーは存在しない。
- 主要 5 つで実プロジェクトの拡張使用の大半（仮定: 80%）をカバーできる。残り 20% は warning（"未対応の Flask 拡張を検出: <name>"）を出すに留める。
- 依存リスト + import 文の両方を見るのは、`requirements.txt` に書いてあっても import されていない（dead dependency）ケースがあるため。

**却下案**:

- **全部本体に組み込む**: 拡張は数十個ある。メンテナンスが破綻する。
- **最初からプラグインのみ**: ユーザーが「standard で何ができるか」を理解できず採用障壁になる。
- **import 文のみ検出**: `requirements.txt` のバージョン情報を取り逃す（拡張間の API 互換性チェックに必要）。

### 5.3 MCP サーバとしての解析タイミング

**結論**: **起動時は最小限（プロジェクトルート検出と依存ファイル読み込みのみ、500ms 以内）。初回ツール呼び出し時にバックグラウンドで全解析を開始し、当該ツール呼び出しは解析完了を待ってから返す。後続ツール呼び出しはキャッシュ済み結果を即座に返す。** 明示的な `refresh_index()` で再解析可能。

**根拠と Claude Code 体験への影響**:

| 戦略 | 起動 | 初回ツール呼び出し | 後続呼び出し | メモリ消費タイミング | 採否 |
|------|------|-------------------|--------------|---------------------|------|
| (A) 起動時に全解析（同期） | 30〜120 秒 | 即座 | 即座 | 起動時 | × MCP の起動タイムアウト（Claude Code は ~30 秒）に抵触 |
| (B) 完全遅延（毎回） | 即座 | 30〜120 秒 + ツール処理 | 同左 | 各回 | × 体感が悲惨、キャッシュも無意味 |
| (C) 起動時最小、初回呼び出しで全解析 | 即座 | 30〜120 秒 | 即座 | 初回呼び出し時 | ◎ **採用** |
| (D) バックグラウンド先行解析 | 即座 | (タイミング依存) | 即座 | 起動直後 | × 解析完了前にツールが呼ばれるとどうせ待つ。複雑度が増えるだけ |
| (E) 明示的 `index()` ツール | 即座 | エラー（未解析）| - | - | × エージェントがまず `index()` を呼ぶと学習する必要あり、UX 悪化 |

(C) を採用。理由は MCP の起動タイムアウト回避、キャッシュとの相性（2 回目以降のセッションは瞬時起動）、実装の単純さ。

**却下案**: 上記表のとおり。

### 5.4 認証チェックの判定ロジック

**結論**: **3 段階の信頼度スコア + ユーザー設定で上書き可能** 方式。

**判定ルール**:

「ルートに認証が掛かっているか」を判定する各シグナルに信頼度を割り当てる:

| シグナル | 信頼度 |
|---------|--------|
| 既知の認証デコレータ名にマッチ（`@login_required`, `@jwt_required`, `@require_auth`, `@authenticated`, `@requires_login`, `@oidc_auth` 等のホワイトリスト）| **high** |
| `.flask-mcp-lens.toml` の `[auth.decorators]` / `[auth.functions]` で明示宣言 | **high**（ユーザー宣言）|
| ルートのスコープに登録された `before_request` 内に `abort(401)` または `abort(403)` を含む関数がある | **medium** |
| view 関数内またはデコレータ内でユーザー定義関数を呼んでおり、その関数名が `auth`, `permission`, `authenticate`, `authorize`, `check_login` のいずれかを含む | **low** |
| 上記いずれにもマッチしない | **none** |

ルートあたりの最高シグナルが採用される（high が 1 つでもあれば high 判定）。

**`find_potentially_unprotected_routes()` の出力**: ルート最高シグナルから 3 段階に分類:

```jsonc
{
  "definitely_unprotected": [...],   // 最高シグナル = none。認証が掛かっている形跡が一切ない
  "likely_unprotected": [...],       // 最高シグナル = low。関数名ヒューリスティックのみで、実際には認証していない可能性が高い
  "ambiguous": [...]                 // 最高シグナル = medium。before_request の適用範囲が動的で確定できない
}
```

high 判定のルートは「認証されている」とみなしこのツールの出力には含めない。

**根拠**:

- 偽陽性 0% は不可能（自前認証フレームワークを排除できない）。代わりに「LLM が判断材料を持って人間に提示する」形にする。
- ホワイトリストはハードコード + ユーザー設定の二層で、メンテナンス負荷とカバレッジのバランスを取る。
- 信頼度を分けて返すことで、エージェントが「赤信号 3 件、要確認 5 件」のように要約できる。

**却下案**:

- **デコレータ名ホワイトリストのみ**: 自前認証ラッパー（`@my_auth`）を持つプロジェクトで全件偽陽性。実用にならない。
- **二値判定（保護/未保護）**: 灰色を黒か白に押し付ける。誤った安心感は危険、誤った警告は無視される。
- **ユーザー設定必須**: セットアップ障壁が上がり、初回利用が萎える。

### 5.5 大規模コードベースでのスケーラビリティ

**結論**:

- **目標**: 10 万行 / 1500 ファイル / 500 ルート / 50 Blueprint まで実用。
- **劣化シナリオ**:
  - 30 万行超: 解析 5 分超を許容（warning 表示）、メモリ 1GB 超を許容
  - 1000 ファイル超: Phase 1 はシリアル解析、Phase 3 で `multiprocessing.Pool(N=cpu_count())` による並列パース導入
  - Blueprint 入れ子 4 段以上: 警告のみ（実プロジェクトで稀）
- **閾値超過時の挙動**: 解析は完了させるが、`warnings` に「規模が想定上限を超えている: 性能保証外」を含める。

**根拠**:

- 10 万行は B2B SaaS の中規模上限。これを切り捨てると主要ターゲット層を失う。
- 30 万行以上は超大規模で、対象は希少。完全カバーよりも「壊れない」ことを優先。
- 並列パースは効果が大きいが Phase 1 の複雑度を上げるため後回し。

**却下案**:

- **5 万行までを目標**: B2B SaaS の典型サイズに届かない。
- **無制限を保証**: 計測も保証もできない約束をすべきでない。

---

## 6. アウトオブスコープ

| 項目 | 理由 |
|------|------|
| Django, FastAPI, Bottle, Quart 等の他フレームワーク対応 | フレームワーク特化が本ツールの価値の源泉。横展開すると Flask 特有のセマンティクス（before_request 順序、Blueprint 入れ子）の理解度が浅くなる |
| コードの自動修正・自動リファクタリング | LLM エージェントが修正実行を担当する分業前提。本ツールは情報提供に専念 |
| 動的ルーティング（リクエスト時パラメータで分岐するもの）の完全追跡 | 静的解析の原理的限界。`warnings` で「動的分岐検出」を返すのみ |
| Jinja2 テンプレート構造の深追い（テンプレート継承グラフ等） | LLM が `Read` で直接読む方が token 効率が良い。テンプレート内ロジックの構造化は需要も少ない |
| セキュリティ脆弱性スキャナとしての完全機能 | Bandit / semgrep の領域。本ツールが扱うのは「認証漏れ候補」までで、SQL injection / XSS / CSRF 検出は行わない |
| WebSocket / Flask-SocketIO の解析 | ルーティングモデルが HTTP と異なり別設計が要る。需要も限定的 |
| OpenAPI / Swagger スキーマの生成 | 既存ツール（apispec, flask-smorest 自動生成等）と競合し、独自価値が薄い |
| マイクロサービス的な複数 app 構成（同一リポジトリに 2 つ以上の Flask app） | A3 の前提と矛盾。需要が出てきたら Phase 5 以降で検討 |

---

## 7. リスクと未解決事項

| # | 項目 | 影響 | 検証手段 |
|---|------|------|----------|
| R1 | `create_app()` 実行時の副作用抑止が、現実プロジェクトでどこまで効くか | ハイブリッド解析の実用性に直結 | Phase 3 着手前に実 OSS Flask プロジェクト 5 件で計測 |
| R2 | Blueprint 入れ子 + `add_url_rule` 直書き混在時の URL 解決精度 | `get_route_handler` の正確性 | Phase 1 内でテストケース整備 |
| R3 | `before_request` の登録が動的（ループ内、条件分岐）な場合の検出限界 | 認証判定の偽陰性 | Phase 2 で代表パターンをテストケース化 |
| R4 | 拡張ライブラリのメジャーバージョン更新追従コスト | 中長期メンテ負荷 | バージョン明示と CI で複数バージョンマトリクステスト |
| R5 | MCP プロトコル仕様の将来変更 | 互換性破壊 | MCP SDK 公式更新を追従、stdio transport に絞ることで影響面を狭める |
| R6 | Windows パス（`\` と `/`）混在の取り扱い | Windows ユーザーで誤動作 | 全パスを `pathlib.Path` で統一 |
| R7 | `from flask import Blueprint as BP` 等のエイリアス import | 静的解析の検出漏れ | import エイリアス解析を Phase 1 で実装、テストで担保 |

---

## 8. 成功指標

観測可能な形で記述。

| 指標 | 閾値 | 計測方法 |
|------|------|----------|
| 中規模 Flask プロジェクト（100 ルート、~3 万行）で `list_routes()` がキャッシュ後 1 秒以内に返る | 1.0s | `time` 計測、3 回平均 |
| `find_potentially_unprotected_routes()` の偽陽性率 | 30% 以下 | 実 OSS Flask プロジェクト 3 件（後述）で人手レビュー |
| `find_potentially_unprotected_routes()` の偽陰性率 | 10% 以下 | 同上、認証されているのに警告されないケース |
| Claude Code が flask-mcp-lens 経由で「`/path` は認証されているか？」に正答できる | 90% 以上（10 問中 9 問）| 質問セットを準備し、本ツール有/無で比較 |
| Phase 1 完了時点で実 OSS Flask プロジェクト 3 件で `list_routes`, `get_route_handler`, `get_app_overview`, `find_app_factory` が完走する（クラッシュせず、明らかな欠落なく） | 3/3 | 検証スクリプト |
| MCP サーバ起動 → 初回 `get_app_overview` 完了までの時間（5 万行プロジェクト） | 35 秒以内 | 起動 2s + 初回解析 30s + ツール 1s = 33s 想定 |

**検証用 OSS プロジェクト候補**（実装着手時に確定）:

- 中規模 Flask アプリの代表例 3 件（GitHub 上の star 数 1k 以上、active な保守、認証実装あり）

---

## 9. 開発フェーズ計画

### Phase 1: MVP（想定 1.5 人日 ≒ 12h）

**Done 条件**:

- [ ] `pip install -e .` で開発インストール可能
- [ ] `flask-mcp-lens` コマンドで MCP サーバが stdio で起動
- [ ] Claude Code から MCP サーバとして接続でき、ツールリストが取得できる
- [ ] `find_app_factory()` が動く（`Flask(__name__)` 直書き / `create_app()` 関数の両方を検出）
- [ ] `get_app_overview()` が動く（`auth_strategies_summary` 抜き、Markdown 含む）
- [ ] `list_routes()` が動く（`@app.route`, `@bp.route`, `add_url_rule` 対応、url_prefix 継承）
- [ ] `get_route_handler(url, method)` が動く（before_request チェーン + デコレータ列）
- [ ] `refresh_index()` が動く
- [ ] サンプル Flask アプリ（test fixture）3 種で E2E 動作確認: (a) 単一 app.py, (b) Application Factory + Blueprint 1 つ, (c) Application Factory + Blueprint 2 つ + 入れ子
- [ ] README に最小セットアップ手順
- [ ] mtime ベースのキャッシュ（`.flask-mcp-lens/cache/`）

### Phase 2: 認証・拡張対応（想定 4 人日）

**Done 条件**:

- [ ] `list_blueprints()`（未登録 Blueprint 検出含む）
- [ ] `list_extensions()`（requirements.txt + import 解析）
- [ ] `list_auth_strategies()`（信頼度スコア付き）
- [ ] `find_potentially_unprotected_routes()`（3 段階分類）
- [ ] `list_api_endpoints()`
- [ ] `get_extension_config(name)` で Flask-Login と Flask-JWT-Extended に対応
- [ ] `.flask-mcp-lens.toml` 設定ファイル対応（`[auth]` セクション）
- [ ] `get_app_overview()` に `auth_strategies_summary` 追加
- [ ] `MethodView` 対応
- [ ] Phase 1 ツールにフィルタ引数追加

### Phase 3: ハイブリッド解析・自動更新（想定 5 人日）

**Done 条件**:

- [ ] `[hybrid] enabled = true` で `create_app()` 実行
- [ ] 副作用抑止層（環境変数注入、DB URI 上書き、外部通信ブロック）
- [ ] ハイブリッド失敗時の静的フォールバック
- [ ] watchdog による自動 invalidate（`--watch` フラグ）
- [ ] ファイル単位の差分再解析
- [ ] Flask-SQLAlchemy, Flask-RESTful, Flask-RESTX 対応追加
- [ ] 実 OSS Flask プロジェクト 3 件での検証完了

### Phase 4: 拡張性・最適化（想定 5〜7 人日、必要性を見て着手）

**Done 条件**:

- [ ] プラグイン機構（`flask_mcp_lens.plugins` entry point、外部パッケージから拡張対応を追加可能）
- [ ] `multiprocessing` による並列パース
- [ ] 30 万行プロジェクトで動作確認（性能劣化を許容しつつ完走）
- [ ] HTTP/SSE transport 対応（必要性が確認できた場合のみ）

---

## 10. ユーザー判断が必要な項目

以下は仮定で進めたが、ユーザーの最終判断を求めたい:

1. **検証用 OSS Flask プロジェクト 3 件の選定**: 候補（成功指標セクション参照）を提示するので確定したい。
2. **ライセンス**: 仮定として MIT を想定。Apache-2.0 / BSD-3-Clause / MIT のいずれか。
3. **MCP サーバの公開名**: `flask-mcp-lens` で確定か、PyPI 衝突がないか確認要。
4. **`.flask-mcp-lens.toml` ではなく `pyproject.toml` の `[tool.flask-mcp-lens]` セクションで設定を持つ案**: どちらが好みか。後者の方が Python エコシステム準拠だが、フォルダ移動でコピーしづらい欠点あり。
5. **ハイブリッド解析の Phase 3 着手前に R1（副作用抑止の現実性）の事前調査を実施するか**: 工数 1 人日程度を割く必要あり。
6. **Phase 4 のプラグイン機構を実装する判断ライン**: 「外部からの貢献要望が出たら」「対応希望拡張が累計 3 件出たら」など、客観的なトリガーを決めたい。
