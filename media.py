"""画像投稿(オプション機能)。

本体(x_client / post)はテキスト投稿のみを担当し、画像のアップロード処理は
このファイルに分離している。画像が指定されたときだけ post_tweet から呼ばれる。
画像が無ければこのモジュールは一切実行されない。
"""
from __future__ import annotations

import mimetypes
import tempfile
import urllib.request
from pathlib import Path

from playwright.sync_api import Page, TimeoutError as PWTimeout

import config

# 作成欄内の隠しファイル入力(ここにファイルを流し込むとアップロードされる)
FILE_INPUT = '[data-testid="fileInput"]'
# アップロード完了の目印(添付サムネイル/削除ボタン)
ATTACHMENT_MARKER = (
    '[data-testid="attachments"], [data-testid="removeMedia"]'
)

# Xの画像添付は1ツイート最大4枚
MAX_IMAGES = 4

# URLダウンロード時のUA(商品画像サーバが素のリクエストを弾くことがあるため)
_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
# 拡張子が判別できないときの既定
_DEFAULT_EXT = ".jpg"
# ダウンロード画像の一時保存先(GitHub Actionsでは実行ごとに破棄される)
_TMP_DIR = Path(tempfile.gettempdir()) / "xposter_media"


def _is_url(value: str) -> bool:
    return value.startswith("http://") or value.startswith("https://")


def _download_image(url: str, index: int) -> Path | None:
    """画像URLをダウンロードして一時ファイルのパスを返す。失敗時 None。"""
    _TMP_DIR.mkdir(parents=True, exist_ok=True)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": _UA})
        with urllib.request.urlopen(req, timeout=30) as resp:
            if resp.status != 200:
                print(f"[warn] 画像取得失敗(HTTP {resp.status})のためスキップ: {url}")
                return None
            ctype = resp.headers.get("Content-Type", "")
            data = resp.read()
        ext = mimetypes.guess_extension(ctype.split(";")[0].strip()) or _DEFAULT_EXT
        # jpeg は .jpe になることがあるので正規化
        if ext == ".jpe":
            ext = ".jpg"
        dest = _TMP_DIR / f"img_{index}{ext}"
        dest.write_bytes(data)
        print(f"    画像ダウンロード: {url} ({len(data)} bytes)")
        return dest
    except Exception as e:  # noqa: BLE001 ネットワーク系の各種例外をまとめて処理
        print(f"[warn] 画像取得に失敗したためスキップ: {url} ({e})")
        return None


def resolve_image_paths(raw_paths: list[str]) -> list[Path]:
    """画像指定をローカルの実ファイルパスに解決する(最大4枚)。

    各要素は次のどちらでもよい:
      - URL (http/https): 実行時にダウンロードして一時ファイル化する
      - ローカルパス     : リポジトリ内などの実ファイル
    解決できないものは警告して除外する。1枚も無ければ空リスト。
    """
    resolved: list[Path] = []
    for i, raw in enumerate(raw_paths):
        if not raw:
            continue
        if _is_url(raw):
            downloaded = _download_image(raw, i)
            if downloaded:
                resolved.append(downloaded)
            continue
        p = Path(raw)
        if not p.is_absolute():
            p = config.ROOT / p
        if p.is_file():
            resolved.append(p)
        else:
            print(f"[warn] 画像が見つからないためスキップ: {raw}")
    if len(resolved) > MAX_IMAGES:
        print(f"[warn] 画像は最大{MAX_IMAGES}枚。先頭{MAX_IMAGES}枚のみ使用します。")
        resolved = resolved[:MAX_IMAGES]
    return resolved


def attach_images(page: Page, image_paths: list[Path]) -> None:
    """作成欄に画像を添付し、アップロード完了まで待つ。

    呼び出し側で image_paths が空でないことを保証すること。
    """
    file_input = page.wait_for_selector(FILE_INPUT, state="attached", timeout=15_000)
    file_input.set_input_files([str(p) for p in image_paths])
    print(f"    画像を{len(image_paths)}枚アップロード中...")

    # アップロード完了(サムネイル表示)を待つ
    try:
        page.wait_for_selector(ATTACHMENT_MARKER, timeout=config.ACTION_TIMEOUT_MS)
    except PWTimeout as e:
        raise RuntimeError("画像アップロードの完了を確認できませんでした。") from e

    # 後処理(エンコード)の取りこぼし防止に少し待つ
    page.wait_for_timeout(2_000)
    print("    画像アップロード完了")
