"""普段使いのブラウザのCookieから auth_state.json を作る。

自動ブラウザでのログインがXのボット検知に弾かれる場合の回避策。
ログイン済みの通常ブラウザ(Chrome/Edge)から auth_token と ct0 を取り出して渡すと、
Playwright が使えるセッションファイルを生成する。

Cookieの取り出し方(Chrome/Edgeの例):
  1. ブラウザでXにログインした状態にする
  2. F12 で開発者ツール → [Application](アプリケーション)タブ
  3. 左の Storage > Cookies > https://x.com を選択
  4. 一覧から次の2つの Value をコピー:
       - auth_token
       - ct0
  5. このスクリプトを実行して貼り付ける

使い方:
    python import_cookies.py
    (auth_token と ct0 を順に貼り付け)

または引数で渡す:
    python import_cookies.py --auth-token XXXX --ct0 YYYY
"""
from __future__ import annotations

import argparse
import base64
import json

import config


def build_state(auth_token: str, ct0: str) -> dict:
    """Playwright の storage_state 形式を組み立てる。"""
    cookies = [
        {
            "name": "auth_token",
            "value": auth_token,
            "domain": ".x.com",
            "path": "/",
            "httpOnly": True,
            "secure": True,
            "sameSite": "None",
        },
        {
            "name": "ct0",
            "value": ct0,
            "domain": ".x.com",
            "path": "/",
            "httpOnly": False,
            "secure": True,
            "sameSite": "Lax",
        },
    ]
    return {"cookies": cookies, "origins": []}


def main() -> int:
    parser = argparse.ArgumentParser(description="ブラウザCookieからセッション生成")
    parser.add_argument("--auth-token", help="auth_token の値")
    parser.add_argument("--ct0", help="ct0 の値")
    args = parser.parse_args()

    auth_token = args.auth_token or input("auth_token を貼り付け: ").strip()
    ct0 = args.ct0 or input("ct0 を貼り付け: ").strip()

    if not auth_token or not ct0:
        print("[x] auth_token と ct0 の両方が必要です。")
        return 1

    state = build_state(auth_token, ct0)
    with config.STORAGE_STATE.open("w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    print(f"\n[OK] セッションを保存しました: {config.STORAGE_STATE}")

    raw = config.STORAGE_STATE.read_bytes()
    b64 = base64.b64encode(raw).decode("ascii")
    print("\n" + "=" * 60)
    print("GitHub Secrets 登録用の値 (Secret名: AUTH_STATE_B64)")
    print("=" * 60)
    print(b64)
    print("=" * 60)
    print(
        "\n次に投稿テスト:\n"
        '  $env:HEADLESS="0"; python post.py --text "テスト投稿"\n'
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
