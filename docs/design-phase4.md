# flask-mcp-lens Phase 4 設計書（拡張性・最適化）

ステータス: ドラフト v1.0
対応要件: [requirements.md](./requirements.md) §3.2 (プラグイン機構), §5.5 (スケーラビリティ), §9 Phase 4
前提: [design-phase1.md](./design-phase1.md), [design-phase2.md](./design-phase2.md), [design-phase3.md](./design-phase3.md) を踏襲
想定工数: 5〜7 人日（着手判断を要件 §10 のトリガーに従う）

---

## 目次

- [1. スコープ](#1-スコープ)
- [2. 着手判断の前提条件](#2-着手判断の前提条件)
- [3. プラグイン機構](#3-プラグイン機構)
- [4. 並列解析](#4-並列解析)
- [5. HTTP/SSE transport（オプション）](#5-httpsse-transportオプション)
- [6. 30 万行スケール対応](#6-30-万行スケール対応)
- [7. プラグイン公式参考実装](#7-プラグイン公式参考実装)
- [8. 互換性とバージョニング](#8-互換性とバージョニング)
- [9. テスト設計](#9-テスト設計)
- [10. リリース戦略](#10-リリース戦略)

---

## 1. スコープ

| 項目 | 概要 |
|------|------|
| プラグイン機構 | 第三者が拡張ライブラリ対応や独自ツールを追加できる仕組み |
| 並列解析 | `multiprocessing` によるファイル AST パースの並列化 |
| HTTP/SSE transport | stdio 以外の MCP transport 対応（必要性が確認できた場合のみ） |
| 30 万行スケール対応 | 性能劣化を許容しつつ完走させる |
| 公式参考プラグイン | プラグイン API の妥当性検証用、Flask-Admin 対応を別パッケージで作成 |

**Out of Phase 4**: 複数 Flask app 構成、Quart/Litestar 対応（要件のアウトオブスコープ参照）、自動修正。

---

## 2. 着手判断の前提条件

要件 §10 の「ユーザー判断が必要な項目」に従い、以下のいずれかが満たされたら着手:

1. 外部からの拡張対応要望が累計 3 件以上
2. 30 万行クラスのプロジェクトでの実用要望が確認された
3. 公式拡張対応のメンテナンス負荷が顕在化（5 つを超える拡張ハンドラの並行修正が発生）
4. HTTP/SSE transport の具体的な利用シナリオが提示された（Web UI、IDE 連携等）

トリガーが発火する前に Phase 4 着手しても良いが、**プラグイン API は早すぎる抽象化のリスクが高い**ため、実利用者なしで設計凍結することは避ける。

---

## 3. プラグイン機構

### 3.1 設計方針

**結論**: Python の **entry points** メカニズムを採用。プラグインは独立した `pip install` 可能なパッケージで提供される。

**根拠**:

- entry points は標準ライブラリ (`importlib.metadata`) で読める。追加依存なし
- `setup.py` / `pyproject.toml` の標準的な配布形態に乗る
- 動的ローディング不要（プラグインがインストールされていれば自動検出）

**却下案**:

- 設定ファイルでプラグイン path 指定: ユーザー側のセットアップ負荷
- 名前ベース動的 import (`importlib.import_module`): 何が読まれるかが不透明、デバッグ困難

### 3.2 Entry Points 定義

プラグイン側 `pyproject.toml`:

```toml
[project.entry-points."flask_mcp_lens.extensions"]
flask_admin = "flask_mcp_lens_admin.handler:FlaskAdminHandler"

[project.entry-points."flask_mcp_lens.tools"]
list_admin_views = "flask_mcp_lens_admin.tools:list_admin_views"
```

**2 種類の拡張ポイント**:

1. `flask_mcp_lens.extensions`: 拡張ライブラリハンドラ（Phase 2-3 のビルトインと同インタフェース）
2. `flask_mcp_lens.tools`: MCP ツール追加

### 3.3 プラグイン API: ExtensionHandler

ビルトインハンドラと共通の基底を `flask_mcp_lens.api` として **公開 API** 化:

```python
# flask_mcp_lens/api/__init__.py (公開)
from flask_mcp_lens.api.extension import ExtensionHandler, ExtensionDetectionResult
from flask_mcp_lens.api.tool import ToolDefinition, ToolContext
from flask_mcp_lens.api.models import Route, Blueprint, SourceLoc, RouteIndex
```

```python
class ExtensionHandler(Protocol):
    package_name: str           # PyPI 名 ("flask-admin")
    import_name: str            # import 名 ("flask_admin")
    api_version: str            # 対応 flask-mcp-lens API のメジャーバージョン

    def detect_initialization(
        self, ast_results: ASTResults
    ) -> Optional[SourceLoc]: ...

    def collect_config(
        self, ast_results: ASTResults
    ) -> dict: ...

    # オプション: 追加 Route を提供（管理画面ルート等）
    def contribute_routes(
        self, ast_results: ASTResults
    ) -> list[Route]: ...
```

`ASTResults` は read-only なフラットビュー。プラグインに本体内部のミュータブル状態を渡さない。

### 3.4 プラグイン API: ツール追加

```python
class ToolContext(Protocol):
    """ツール実装に渡されるコンテキスト。Index への安全なアクセスを提供。"""
    project_root: Path
    config: Config

    def get_index(self) -> RouteIndex: ...
    def get_extension_info(self, name: str) -> Optional[ExtensionInfo]: ...
    def warn(self, message: str) -> None: ...

class ToolDefinition(Protocol):
    name: str                                 # MCP ツール名 ("list_admin_views")
    description: str
    input_schema: dict                        # JSON Schema
    handler: Callable[[ToolContext, dict], dict]
```

**name 衝突**: ビルトインツール名と衝突したら起動時エラー。プラグイン同士の衝突は load 順 + 警告で後者を無視。

### 3.5 ローダ実装

`flask_mcp_lens/plugin_loader.py`:

```python
import importlib.metadata as md

def load_extension_handlers() -> dict[str, ExtensionHandler]:
    handlers = dict(BUILTIN_HANDLERS)
    for ep in md.entry_points(group="flask_mcp_lens.extensions"):
        try:
            handler_cls = ep.load()
            handler = handler_cls()
            check_api_compat(handler.api_version)
            if handler.package_name in handlers:
                logger.warning("Plugin overrides built-in handler: %s", handler.package_name)
            handlers[handler.package_name] = handler
        except Exception as e:
            logger.warning("Failed to load plugin %s: %s", ep.name, e)
    return handlers

def load_extra_tools() -> list[ToolDefinition]:
    tools = []
    for ep in md.entry_points(group="flask_mcp_lens.tools"):
        try:
            tool = ep.load()
            check_tool_definition(tool)
            tools.append(tool)
        except Exception as e:
            logger.warning("Failed to load tool plugin %s: %s", ep.name, e)
    return tools
```

**フォールバック**: プラグイン読み込み失敗は本体起動を止めない。warning のみ。

### 3.6 API バージョニング

`flask_mcp_lens.api.__version__ = "1.0"`。

互換性ルール:

- メジャー変更（API シグネチャ破壊）は本体のメジャーバージョンと連動
- マイナー変更（新メソッド追加）は本体のマイナーバージョンと連動
- プラグイン側は `api_version = "1.x"` を宣言、ローダは `>=1.0,<2.0` でマッチ

不一致時の挙動:

- メジャー不一致: プラグインを load しない、warning
- マイナー不足: プラグインを load する（本体が新しいだけなら互換）
- マイナー超過: load しない、warning

### 3.7 セキュリティ

プラグインは任意コードを実行する。

- インストール済みプラグインの一覧は `flask-mcp-lens --list-plugins` で表示
- 起動時 stderr に「Loaded N plugins: [...]」を出力（透明性）
- ハイブリッド実行とは別問題（プラグインは本体プロセス内で動く、これは entry_point の性質上避けられない）

---

## 4. 並列解析

### 4.1 設計判断

**結論**: `multiprocessing.Pool` で **AST パースのみ並列化**。Resolver は引き続きシングルプロセス。

**根拠**:

- AST パースは CPU バウンド + 各ファイル独立 → 並列化の効果が大きい
- Resolver は各ファイルの結果を結合するため逐次的 → 並列化のうま味が小さく、ロック等の複雑度が増える
- スレッド (`ThreadPoolExecutor`) ではなくプロセスを使うのは Python の GIL 回避

**却下案**:

- 全工程並列化: Resolver の依存関係を考えると複雑度に見合わない
- `concurrent.futures.ThreadPoolExecutor`: GIL のため CPU バウンドでは効果なし
- async I/O: ファイル読み込みは fast、CPU が boundary

### 4.2 実装

`analyzer/parallel.py`:

```python
def parse_files_parallel(files: list[Path], n_workers: int = None) -> dict[str, FileAnalysis]:
    n = n_workers or max(1, os.cpu_count() - 1)
    if len(files) < 50 or n <= 1:
        # オーバーヘッドが効かないので逐次
        return {str(f): _analyze_file(f) for f in files}
    with multiprocessing.Pool(n) as pool:
        results = pool.map(_analyze_file_worker, files, chunksize=10)
    return {str(f): r for f, r in zip(files, results)}

def _analyze_file_worker(file: Path) -> FileAnalysis:
    """worker process で実行される。pickle 可能な引数/戻り値のみ扱う。"""
    return _analyze_file(file)
```

**閾値**: 50 ファイル未満は逐次（プロセス起動オーバーヘッドの方が大きい）。`chunksize=10` で IPC 回数を削減。

### 4.3 Windows 対応

`multiprocessing` は Windows で `spawn` モード。worker 関数とその依存はトップレベルに置く必要あり。`_analyze_file_worker` を `parallel.py` のモジュールレベルに配置する。

### 4.4 メモリ消費

10 万行プロジェクトで 8 worker x ~50MB = ~400MB の追加メモリ。要件 §4.1 のメモリ上限 500MB は worker を含めない数値であることを明記し、並列モード時は実質 1GB 程度を許容する記載を README に追加。

### 4.5 オプトイン

- デフォルト: 自動（ファイル数 >= 50 で自動並列化）
- 強制 OFF: `--no-parallel` フラグ
- 並列度指定: `--workers N`

---

## 5. HTTP/SSE transport（オプション）

### 5.1 着手条件

具体的な利用シナリオが確認された場合のみ。Phase 4 の中でも独立して着手可能（プラグイン機構と独立）。

### 5.2 実装

`mcp` SDK の HTTP/SSE transport を使う:

```bash
flask-mcp-lens --transport http --port 8765
flask-mcp-lens --transport sse --port 8765
```

**認証**: ローカルバインド (`127.0.0.1`) のみ既定許可。`--bind 0.0.0.0` 指定時は警告 + token 必須:

```bash
flask-mcp-lens --transport http --bind 0.0.0.0 --auth-token $(uuidgen)
```

token は `Authorization: Bearer <token>` ヘッダで検証。

### 5.3 同時接続

複数クライアントが同時にツール呼び出し可能。`IndexManager` は既にスレッドセーフ（Phase 3 で `threading.Lock` 導入済み）なので追加実装少。

### 5.4 stdio との挙動差

なし（同じ tool dispatcher を経由する）。差分があれば bug。

---

## 6. 30 万行スケール対応

### 6.1 想定劣化

要件 §5.5 の通り、性能保証は外す。ただし **クラッシュさせず完走** することは保証する。

| 指標 | 30 万行での目標 |
|------|----------------|
| 全体解析時間 | 5 分以内（並列 8 worker 想定）|
| メモリ | 1.5GB 以内（worker 含む）|
| キャッシュサイズ | 30MB 以内（gzip 後）|

### 6.2 対策

| 課題 | 対策 |
|------|------|
| 巨大 AST のメモリ消費 | parse 後すぐに必要情報だけ抽出して AST を捨てる |
| キャッシュ JSON サイズ | 既に gzip 済み。さらにファイル単位分割キャッシュ（Phase 3 で導入済み）が効く |
| 起動時のキャッシュロード時間 | 必要な部分だけ lazy load する index split |
| ツール応答時間 | 結果セットが大きいツール（`list_routes` 等）に `limit`/`offset` パラメータ追加 |

### 6.3 ツール出力のページング

```jsonc
// list_routes 拡張
{
  "type": "object",
  "properties": {
    "filter": {...},
    "limit": {"type": "integer", "default": 1000, "maximum": 5000},
    "offset": {"type": "integer", "default": 0}
  }
}
```

レスポンスに `next_offset` を追加。MCP の token budget を考慮しエージェントが必要分だけ取得できるように。

### 6.4 30 万行ベンチマーク

実プロジェクト（または合成プロジェクト）でベンチを CI に追加:

- 合成: スクリプトで 1500 ファイル x 200 行のダミー Flask app を生成
- 計測: 全体解析、`list_routes` 1000 件、差分再解析 1 ファイル

---

## 7. プラグイン公式参考実装

`flask-mcp-lens-admin` を別リポジトリ・別 PyPI パッケージとして作成:

- 対象: Flask-Admin
- 実装するもの:
  - `ExtensionHandler` の `detect_initialization` / `collect_config`
  - 追加ツール `list_admin_views()` で各 ModelView を列挙
- 配布形態: `pip install flask-mcp-lens-admin`

これがプラグイン API の最初のドッグフード。実装中に発見した API の不便を本体側 API にフィードバックする（Phase 4 内で）。

---

## 8. 互換性とバージョニング

### 8.1 SemVer

| 変更 | バージョン規則 |
|------|---------------|
| MCP ツール追加 | minor |
| MCP ツール出力フィールド追加（既存削除なし）| minor |
| MCP ツール削除/必須フィールド削除 | major |
| プラグイン API シグネチャ変更（破壊的）| major |
| プラグイン API メソッド追加 | minor |
| キャッシュ schema_version 変更 | minor で OK（自動 invalidate）|

### 8.2 Deprecation

メジャー変更前は 1 マイナーバージョン以上の deprecation 期間。`warnings.warn(DeprecationWarning)` を出してから次メジャーで削除。

### 8.3 プラグイン側の対応負荷軽減

- 公式ドキュメントに移行ガイド
- 主要破壊変更時は `flask-mcp-lens-compat` パッケージを提供（旧 API を新 API に橋渡し）

---

## 9. テスト設計

### 9.1 プラグインテスト

`tests/plugin/`:

- ダミープラグイン (`tests/fixtures/dummy_plugin/`) を `pip install -e` でインストールして起動
- ハンドラ追加が反映されることの確認
- API バージョン不一致時に load 拒否されることの確認
- ツール衝突時の挙動確認

### 9.2 並列解析テスト

- 50 ファイル未満で逐次パスが選ばれること
- 50 ファイル以上で並列パスが選ばれること
- 並列結果が逐次結果と一致すること（決定性）
- 1 ファイルが構文エラーでも他ファイルが完走すること

### 9.3 スケールテスト

- `tests/scale/test_30k_lines.py`: 1500 ファイル合成プロジェクトで 5 分以内完走
- メモリ計測: `tracemalloc` で peak 1.5GB 以内

### 9.4 HTTP transport テスト

- subprocess で `--transport http --port <random>` 起動
- requests で tool call を送信して JSON-RPC レスポンス検証
- token 認証 ON/OFF の挙動

---

## 10. リリース戦略

### 10.1 段階的リリース

| バージョン | 内容 |
|-----------|------|
| 0.4.0 | プラグイン API（実験的、API stable 宣言なし）|
| 0.4.x | 並列解析、HTTP transport |
| 0.5.0 | プラグイン API stable 宣言、参考プラグイン公開 |
| 1.0.0 | プラグイン API 確定、公開 SemVer 開始 |

0.x の間は破壊的変更を minor で行うことを README に明記。1.0 以降は SemVer 準拠。

### 10.2 ドキュメント

Phase 4 着手時に追加するドキュメント:

- `docs/plugin-api.md`: プラグイン作者向け API リファレンス
- `docs/plugin-tutorial.md`: Flask-Admin 対応プラグインを作るチュートリアル
- `docs/performance.md`: 大規模プロジェクト向けチューニングガイド
- `docs/transports.md`: stdio / HTTP / SSE の選択基準

### 10.3 コミュニティ

- GitHub Issues に「plugin-request」ラベル
- 公式プラグイン候補（Flask-Admin 以降）はコミュニティ要望に応じて
- 本体に取り込まない方針: 「2 個以上の独立プラグインで同パターンが繰り返されたら本体への取り込みを検討」
