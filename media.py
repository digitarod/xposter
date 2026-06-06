"""画像投稿(オプション機能)。

本体(x_client / post)はテキスト投稿のみを担当し、画像のアップロード処理は
このファイルに分離している。画像が指定されたときだけ post_tweet から呼ばれる。
画像が無ければこのモジュールは一切実行されない。
"""
from __future__ import annotations

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


def resolve_image_paths(raw_paths: list[str]) -> list[Path]:
    """指定パスのうち、実在するファイルだけを返す(最大4枚)。

    存在しないものは警告して除外する。1枚も無ければ空リスト。
    """
    resolved: list[Path] = []
    for raw in raw_paths:
        if not raw:
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
