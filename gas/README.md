# GAS トリガー連携

Google Apps Script(GAS)の時間トリガーで投稿を起動する構成です。
GASが投稿テキストを生成し、GitHub Actions のワークフローを呼び出して実投稿します。

```
[GAS 時間トリガー] → generateText() → GitHub workflow_dispatch API
        → [GitHub Actions] post.py --text "..." → [X 投稿]
```

GAS は HTTP リクエストしか送れないため(ブラウザ操作は不可)、投稿そのものは
GitHub Actions 側の Playwright が担当します。

## セットアップ

### 1. GitHub Personal Access Token (PAT) を作る

- https://github.com/settings/personal-access-tokens → **Generate new token (fine-grained)**
- **Repository access**: Only select repositories → `digitarod/xposter`
- **Permissions** → Repository permissions:
  - **Actions: Read and write** ← ワークフロー起動に必須
  - (Contents は Read のままでOK)
- 生成された `github_pat_...` をコピー(一度しか表示されない)

### 2. GAS プロジェクトを作る

1. https://script.google.com → 新しいプロジェクト
2. `Code.gs` の内容を貼り付け
3. 左の **歯車(プロジェクトの設定)** → **スクリプト プロパティ** で以下を追加:

| プロパティ名 | 値 |
|------------|-----|
| `GITHUB_TOKEN` | 手順1のPAT (`github_pat_...`) |
| `GITHUB_OWNER` | `digitarod` |
| `GITHUB_REPO` | `xposter` |
| `WORKFLOW_FILE` | `post.yml` (省略可) |
| `GITHUB_REF` | `main` (省略可) |

### 3. 動作テスト

- GASエディタで関数 `testTrigger` を選び **実行**
- 初回は認可ダイアログが出る → 許可
- GitHubの **Actions タブ** にワークフロー実行が現れ、Xに投稿されれば成功

### 4. 時間トリガーを設定

1. GASエディタ左の **時計アイコン(トリガー)** → **トリガーを追加**
2. 設定:
   - 実行する関数: **`postToX`**
   - イベントのソース: **時間主導型**
   - 例: 「日付ベースのタイマー」→ 午前9〜10時 など
3. 保存

これで指定時刻に GAS が起動 → テキスト生成 → 自動投稿されます。

## 投稿テキストのカスタマイズ

`Code.gs` の `generateText()` を編集します。
- URL: そのまま文字列に含めればOK(自動リンク化)
- 改行: JavaScriptの `'\n'` で改行

スプレッドシートから文言を引く、APIで情報を取得して文章を組み立てる等、
GAS側で自由に生成できます。

## 補足

- workflow_dispatch で起動した場合、`schedule.json` のコミットは行われません
  (単発投稿として処理されるため)。予約キューとは独立して動きます。
- GASトリガーと `schedule.json` の cron は併用可能ですが、混乱を避けるなら
  どちらか一方に寄せるのがおすすめです。GAS主導にするなら、`post.yml` の
  `schedule:` (cron) はコメントアウトしてもよいです。
