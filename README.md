# XPoster — APIを使わないX自動投稿 (GitHub Actions)

Playwright でブラウザを自動操作し、X(Twitter)に **API無料枠を使わず** 投稿します。
ログインはローカルで一度だけ行い、保存したセッション(Cookie)を GitHub Secrets 経由で
再利用するため、サーバー(GitHub Actions)側ではログイン操作をしません。

## 構成

| ファイル | 役割 |
|----------|------|
| `login.py` | **ローカルで一度だけ実行**。手動ログイン → `auth_state.json` 保存 → Secret用base64を表示 |
| `post.py` | 投稿実行。`schedule.json` のキュー処理、または `--text` で単発投稿 |
| `x_client.py` | Playwright のブラウザ操作コア(ログイン判定・投稿) |
| `config.py` | 設定とセッション解決ロジック |
| `schedule.json` | 予約投稿キュー(時刻とテキスト) |
| `.github/workflows/post.yml` | 15分おきにキューを処理する定期実行ワークフロー |

## セットアップ

### 1. ローカル準備

```powershell
pip install -r requirements.txt
python -m playwright install chromium
```

### 2. 初回ログイン(ローカル)

```powershell
python login.py
```

ブラウザが開くので手動でXにログイン(2FAもOK)。完了後ターミナルで Enter を押すと:

- `auth_state.json` が保存される
- GitHub Secrets 登録用の **base64文字列** が表示される

> ⚠️ `auth_state.json` はログイン情報そのものです。`.gitignore` 済みですが、
> 絶対にコミット・共有しないでください。

### 3. GitHub リポジトリに登録

1. このフォルダを GitHub リポジトリに push(`auth_state.json` は除外される)
2. リポジトリ **Settings > Secrets and variables > Actions > New repository secret**
   - Name: `AUTH_STATE_B64`
   - Value: `login.py` が表示した base64 文字列
3. リポジトリ **Settings > Actions > General > Workflow permissions** で
   **Read and write permissions** を有効化(`schedule.json` のコミットに必要)

### 4. 動作確認

- リポジトリの **Actions** タブ → `X auto post` → **Run workflow** で手動実行
- `text` 欄に文字を入れればその場で単発投稿、空ならキュー処理

## 予約投稿の書き方

`schedule.json` を編集して push します。

```json
[
  { "time": "2026-06-10T09:00:00+09:00", "text": "おはようございます", "posted": false }
]
```

- `time`: ISO 8601。タイムゾーン付き推奨(無指定はJST扱い)
- ワークフローは15分おきに起動し、`time <= 現在時刻` かつ `posted=false` の投稿を実行
- 投稿後は `posted=true` / `posted_at` が自動で記録され、コミットされます

## ローカルでのテスト

```powershell
# 単発投稿(画面ありでデバッグしたいとき)
$env:HEADLESS="0"; python post.py --text "テスト投稿"

# キュー処理
python post.py
```

## 運用上の注意

- **利用規約**: 自動投稿はグレーゾーンです。自分のアカウントで常識的な頻度に留めてください。
- **DC-IP**: GitHub Actions はデータセンターIPのため、Xから再認証を求められCookieがDoc失効することがあります。
  その場合はジョブが失敗します(GitHubから失敗メールが届く)ので、`login.py` を
  再実行して `AUTH_STATE_B64` を更新してください。
- **cronの遅延**: GitHub Actions の cron は混雑時に数分〜遅延します。分単位の正確さは出ません。
- **60日ルール**: リポジトリが60日間無活動だと schedule cron が自動停止します。
  本ワークフローは投稿時に commit するため、稼働していれば自然に回避されます。
- **連投**: 同一実行で複数投稿する場合は30〜90秒の間隔を自動で空けています。
