"""共通設定。

ローカルでもGitHub Actions上でも同じコードが動くように、ログインセッションは
次の優先順位で解決する:

1. 環境変数 AUTH_STATE_B64 (base64エンコードされた auth_state.json) があればそれを使う
   -> GitHub Actions ではこの方式 (Secretsに登録)
2. なければローカルの auth_state.json を使う
   -> 開発機ではこの方式 (login.py が生成)
"""
import base64
import os
from pathlib import Path

# プロジェクトのルートディレクトリ
ROOT = Path(__file__).resolve().parent

# ローカルでのログインセッション(Cookie等)の保存先
STORAGE_STATE = ROOT / "auth_state.json"

# 予約投稿キュー
SCHEDULE_FILE = ROOT / "schedule.json"

# XのURL
X_HOME = "https://x.com/home"

# ヘッドレス実行するか。投稿スクリプトの既定。
# 環境変数 HEADLESS=0 で画面ありに切り替えられる(デバッグ用)。
HEADLESS = os.environ.get("HEADLESS", "1") != "0"

# 各種待機ミリ秒
NAV_TIMEOUT_MS = 60_000
ACTION_TIMEOUT_MS = 30_000


def resolve_storage_state() -> Path:
    """使用するセッションファイルのパスを返す。

    AUTH_STATE_B64 があればデコードして一時ファイルに書き出し、そのパスを返す。
    """
    b64 = os.environ.get("AUTH_STATE_B64")
    if b64:
        decoded = base64.b64decode(b64)
        tmp = ROOT / ".auth_state.runtime.json"
        tmp.write_bytes(decoded)
        return tmp
    return STORAGE_STATE
