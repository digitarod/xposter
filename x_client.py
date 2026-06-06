"""X(Twitter)へのブラウザ操作をまとめたコアモジュール。

Playwright の同期APIを使い、保存済みセッション(Cookie)を再利用して投稿する。
ログイン操作そのものは行わない(login.py の役割)。
"""
from __future__ import annotations

import contextlib
from pathlib import Path

from playwright.sync_api import Page, TimeoutError as PWTimeout, sync_playwright

import config


class NotLoggedInError(RuntimeError):
    """保存済みセッションが無効(未ログイン)のときに送出。"""


@contextlib.contextmanager
def browser_page(storage_state: Path | None, headless: bool = True):
    """ブラウザ+ページを開くコンテキストマネージャ。

    storage_state に既存セッションファイルを渡すとログイン状態を復元する。
    None の場合(初回ログイン時)はまっさらな状態で開く。

    自動化検知(navigator.webdriver 等)を緩和するため、Automation系フラグを外し、
    可能なら実Chrome/Edgeチャンネルを使う。
    """
    with sync_playwright() as p:
        launch_kwargs = dict(
            headless=headless,
            args=["--disable-blink-features=AutomationControlled"],
            ignore_default_args=["--enable-automation"],
        )
        # 実ブラウザがあればそれを使う(検知されにくい)。なければ同梱Chromium。
        browser = None
        for channel in ("chrome", "msedge", None):
            try:
                if channel:
                    browser = p.chromium.launch(channel=channel, **launch_kwargs)
                else:
                    browser = p.chromium.launch(**launch_kwargs)
                break
            except Exception:
                continue
        if browser is None:
            raise RuntimeError("ブラウザを起動できませんでした。")

        context = browser.new_context(
            storage_state=str(storage_state) if storage_state else None,
            locale="ja-JP",
            timezone_id="Asia/Tokyo",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 900},
        )
        # navigator.webdriver を消すなど、自動化の痕跡を隠す
        context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        )
        context.set_default_navigation_timeout(config.NAV_TIMEOUT_MS)
        context.set_default_timeout(config.ACTION_TIMEOUT_MS)
        page = context.new_page()
        try:
            yield context, page
        finally:
            browser.close()


def is_logged_in(page: Page) -> bool:
    """ホームを開いてログイン状態を判定する。"""
    page.goto(config.X_HOME, wait_until="domcontentloaded")
    # ログインしていれば左ナビのアカウントボタン or 作成ボックスが出る。
    # 未ログインだと /login や /i/flow/login にリダイレクトされる。
    try:
        page.wait_for_selector(
            '[data-testid="SideNav_AccountSwitcher_Button"], '
            '[data-testid="tweetTextarea_0"]',
            timeout=15_000,
        )
        return True
    except PWTimeout:
        return False


def post_tweet(page: Page, text: str, image_paths: list | None = None) -> None:
    """ホームのインライン作成欄から投稿する。

    image_paths が指定されたときだけ画像を添付する(media.py を遅延import)。
    指定が無ければテキストのみ投稿し、画像処理は一切実行しない。
    """
    page.goto(config.X_HOME, wait_until="domcontentloaded")

    # 作成欄が出るまで待つ。出なければ未ログインとみなす。
    try:
        editor = page.wait_for_selector(
            '[data-testid="tweetTextarea_0"]', timeout=20_000
        )
    except PWTimeout as e:
        raise NotLoggedInError(
            "作成欄が見つかりません。セッションが失効した可能性があります。"
        ) from e

    editor.click()
    # 1文字ずつ入力して人間らしく(かつ確実にイベントを発火させる)
    page.keyboard.type(text, delay=20)

    # 画像が指定されている場合のみ、分離した media モジュールで添付する。
    if image_paths:
        import media  # オプション機能。テキストのみのときは読み込まない。

        media.attach_images(page, image_paths)

    # Ctrl+Enter で送信(Xの標準ショートカット)。ボタンクリックより安定。
    page.keyboard.press("Control+Enter")

    # 送信完了を確認: 作成欄が空に戻る or トーストが出る。
    try:
        page.wait_for_function(
            """() => {
                const el = document.querySelector('[data-testid="tweetTextarea_0"]');
                return el && el.textContent.trim().length === 0;
            }""",
            timeout=config.ACTION_TIMEOUT_MS,
        )
    except PWTimeout:
        # フォールバック: 送信ボタンを明示的にクリック
        with contextlib.suppress(PWTimeout):
            btn = page.wait_for_selector(
                '[data-testid="tweetButtonInline"]', timeout=5_000
            )
            btn.click()
            page.wait_for_timeout(3_000)
