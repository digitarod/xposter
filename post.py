"""予約投稿キュー(schedule.json)を処理して、時刻が来た投稿を実行する。

GitHub Actions から定期的に呼ばれることを想定。
- 現在時刻 >= 予約時刻 かつ未投稿(posted=false) のエントリを投稿
- 投稿に成功したら posted=true / posted_at を記録して schedule.json を更新
- 複数件あるときは投稿間隔をあけて連投を避ける

手動の単発投稿にも対応:
    python post.py --text "いますぐ投稿したい内容"

schedule.json の形式:
[
  {"time": "2026-06-03T09:00:00+09:00", "text": "おはようございます", "posted": false}
]
time はISO 8601。タイムゾーン付き推奨(無指定はJSTとして扱う)。
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from datetime import datetime, timezone, timedelta

import config
from x_client import NotLoggedInError, browser_page, post_tweet

JST = timezone(timedelta(hours=9))

# 同一実行内で複数投稿する際の最小/最大間隔(秒)。連投検知を避ける。
MIN_GAP_SEC = 30
MAX_GAP_SEC = 90


def load_schedule() -> list[dict]:
    if not config.SCHEDULE_FILE.exists():
        return []
    with config.SCHEDULE_FILE.open(encoding="utf-8") as f:
        return json.load(f)


def save_schedule(items: list[dict]) -> None:
    with config.SCHEDULE_FILE.open("w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
        f.write("\n")


def parse_time(value: str) -> datetime:
    """ISO 8601 文字列をタイムゾーン付き datetime に変換(無指定はJST)。"""
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=JST)
    return dt


def due_entries(items: list[dict], now: datetime) -> list[int]:
    """投稿すべきエントリのインデックス一覧を時刻順で返す。"""
    due = []
    for i, item in enumerate(items):
        if item.get("posted"):
            continue
        try:
            t = parse_time(item["time"])
        except (KeyError, ValueError):
            print(f"[skip] 不正な time: {item!r}", file=sys.stderr)
            continue
        if t <= now:
            due.append((t, i))
    due.sort(key=lambda x: x[0])
    return [i for _, i in due]


def run_schedule() -> int:
    items = load_schedule()
    now = datetime.now(JST)
    targets = due_entries(items, now)

    if not targets:
        print("投稿対象はありません。")
        return 0

    print(f"投稿対象: {len(targets)} 件")
    storage = config.resolve_storage_state()
    if not storage.exists():
        print(
            "[x] セッションファイルがありません。AUTH_STATE_B64 を設定するか "
            "login.py を実行してください。",
            file=sys.stderr,
        )
        return 2

    posted_any = False
    with browser_page(storage, headless=config.HEADLESS) as (context, page):
        for n, idx in enumerate(targets):
            text = items[idx]["text"]
            print(f"[{n+1}/{len(targets)}] 投稿します: {text!r}")
            try:
                post_tweet(page, text)
            except NotLoggedInError as e:
                print(f"[x] {e}", file=sys.stderr)
                # ここで止める。残りは次回に持ち越し。
                save_schedule(items)
                return 3

            items[idx]["posted"] = True
            items[idx]["posted_at"] = datetime.now(JST).isoformat()
            posted_any = True
            save_schedule(items)  # 1件ごとに保存(途中失敗に強くする)
            print("    -> 完了")

            # 次があれば間隔をあける
            if n < len(targets) - 1:
                gap = random.randint(MIN_GAP_SEC, MAX_GAP_SEC)
                print(f"    次まで {gap} 秒待機...")
                time.sleep(gap)

    return 0 if posted_any else 0


def run_single(text: str) -> int:
    # GitHub Actions の入力欄は1行のため、リテラルの "\n" を実際の改行に変換する。
    # (schedule.json 経由ではJSONの \n がそのまま改行になるので変換不要)
    text = text.replace("\\n", "\n")
    storage = config.resolve_storage_state()
    if not storage.exists():
        print("[x] セッションファイルがありません。", file=sys.stderr)
        return 2
    with browser_page(storage, headless=config.HEADLESS) as (context, page):
        print(f"投稿します: {text!r}")
        try:
            post_tweet(page, text)
        except NotLoggedInError as e:
            print(f"[x] {e}", file=sys.stderr)
            return 3
    print("-> 完了")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="X 自動投稿")
    parser.add_argument(
        "--text", help="単発投稿するテキスト(指定時は schedule.json を使わない)"
    )
    args = parser.parse_args()

    if args.text:
        return run_single(args.text)
    return run_schedule()


if __name__ == "__main__":
    sys.exit(main())
