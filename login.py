"""ローカルで一度だけ実行する初回ログインスクリプト。

実行すると画面ありのブラウザが開くので、手動でXにログインする(2FA含めOK)。
ログイン完了を確認したらターミナルで Enter を押すと、セッションを
auth_state.json に保存し、GitHub Secrets に登録するための base64 文字列を表示する。

使い方:
    python login.py
"""
from __future__ import annotations

import base64

import config
from x_client import browser_page, is_logged_in


def main() -> None:
    print("ブラウザを開きます。表示されたウィンドウでXにログインしてください。")
    print("(2要素認証もそのまま画面で完了させてOKです)\n")

    # 既存セッションがあれば引き継いで開く(再ログインのやり直し用)
    state = config.STORAGE_STATE if config.STORAGE_STATE.exists() else None

    with browser_page(state, headless=False) as (context, page):
        page.goto(config.X_HOME, wait_until="domcontentloaded")

        input(
            "ログインが完了し、ホーム画面(タイムライン)が表示されたら、"
            "この画面で Enter を押してください... "
        )

        if not is_logged_in(page):
            print(
                "\n[!] まだログインが確認できません。ログインを完了してから"
                "もう一度 Enter を押してください。"
            )
            input("Enter で再確認... ")
            if not is_logged_in(page):
                print("[x] ログインを確認できませんでした。中止します。")
                return

        # セッションを保存
        context.storage_state(path=str(config.STORAGE_STATE))
        print(f"\n[OK] セッションを保存しました: {config.STORAGE_STATE}")

    # GitHub Secrets 用の base64 を表示
    raw = config.STORAGE_STATE.read_bytes()
    b64 = base64.b64encode(raw).decode("ascii")
    print("\n" + "=" * 60)
    print("GitHub Secrets 登録用の値 (Secret名: AUTH_STATE_B64)")
    print("=" * 60)
    print(b64)
    print("=" * 60)
    print(
        "\nGitHub リポジトリ > Settings > Secrets and variables > Actions >\n"
        "  New repository secret\n"
        "  Name : AUTH_STATE_B64\n"
        "  Value: 上の文字列をそのまま貼り付け\n"
    )


if __name__ == "__main__":
    main()
