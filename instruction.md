# XPoster セットアップ手順書

X(Twitter)に **API を使わず・無料で** 自動投稿する仕組みのセットアップ手順です。
Playwright でブラウザを自動操作し、ログイン済みCookieを再利用して投稿します。

```
[GAS 時間トリガー] → 投稿文を生成 → GitHub Actions 起動 → Playwright で X に投稿
```

全体は次の4パートです。順番に進めてください。

- パートA: ローカル準備とログインCookieの取得
- パートB: GitHub リポジトリ側の設定(Secret・権限)
- パートC: 投稿テスト
- パートD: GAS連携(定期実行・テキスト生成)

---

## パートA. ローカル準備とCookie取得

### A-1. 必要ソフト

- Python 3.11 以上
- Google Chrome または Microsoft Edge(普段ログインに使うブラウザ)

### A-2. インストール

```powershell
cd <このプロジェクトのフォルダ>
pip install -r requirements.txt
python -m playwright install chromium
```

### A-3. ログインCookieの取得

X の自動ログインはボット検知に弾かれるため、**普段使いのブラウザのCookie** を取り込みます。

1. 普段使いのブラウザ(Chrome/Edge)で **X にログイン** した状態にする
2. X のタブで **F12**(開発者ツール) → 上部 **Application**(アプリケーション)タブ
3. 左の **Storage > Cookies > `https://x.com`** を選択
4. 次の2つの **Value** をコピー:
   - `auth_token`
   - `ct0`
5. スクリプトを実行して貼り付け:

```powershell
python import_cookies.py
```

→ `auth_state.json` が生成され、**GitHub Secrets 登録用の base64 文字列** が表示されます。

> ⚠️ `auth_token` はパスワード級の認証情報です。第三者に渡さないでください。
> `auth_state.json` は `.gitignore` 済みでコミットされません。

base64を後で使うので、クリップボードにコピーしておきます(再表示する場合):

```powershell
python -c "import base64,pathlib; print(base64.b64encode(pathlib.Path('auth_state.json').read_bytes()).decode())" | Set-Clipboard
```

---

## パートB. GitHub リポジトリ側の設定

### B-1. コードを push

このプロジェクト一式を GitHub リポジトリに push します(`auth_state.json` は除外されます)。

### B-2. Secret `AUTH_STATE_B64` を登録

1. リポジトリ **Settings > Secrets and variables > Actions**
2. **New repository secret**
   - Name: `AUTH_STATE_B64`
   - Secret: A-3でコピーした base64 文字列を貼り付け
3. **Add secret**

### B-3. ワークフローの書き込み権限を有効化

1. リポジトリ **Settings > Actions > General**
2. **Workflow permissions** → **Read and write permissions** を選択 → **Save**
   (予約投稿の「投稿済み」フラグをコミットするために必要)

---

## パートC. 投稿テスト

### C-1. ローカルでテスト投稿

```powershell
$env:HEADLESS="0"; python post.py --text "テスト投稿です"
```

ブラウザが開いて投稿されれば成功です。

### C-2. GitHub Actions でテスト投稿

1. リポジトリ **Actions** タブ → **X auto post**
2. **Run workflow** → `text` 欄にテスト文言を入力 → **Run workflow**
3. 実行ログの **Post** ステップが成功し、X に投稿されればOK

> 改行を入れたいときは `text` 欄で `\n` と書きます(例: `1行目\n2行目`)。

---

## パートD. GAS連携(定期実行・テキスト生成)

GAS の時間トリガーで投稿文を生成し、GitHub Actions を起動します。
詳細コードは `gas/Code.gs`、補足は `gas/README.md` を参照。

### D-1. GitHub Personal Access Token (PAT) を作る

- https://github.com/settings/personal-access-tokens → **Generate new token (fine-grained)**
- **Repository access**: 対象リポジトリのみ選択
- **Permissions > Repository permissions**:
  - **Actions: Read and write** ← 必須
- 生成された `github_pat_...` をコピー(一度しか表示されない)

### D-2. GAS プロジェクトを作る

1. https://script.google.com → 新しいプロジェクト
2. `gas/Code.gs` の内容を貼り付け
3. **歯車(プロジェクトの設定) > スクリプト プロパティ** に以下を追加:

| プロパティ名 | 値 |
|------------|-----|
| `GITHUB_TOKEN` | D-1のPAT(`github_pat_...`) |
| `GITHUB_OWNER` | リポジトリのオーナー名 |
| `GITHUB_REPO` | リポジトリ名 |
| `WORKFLOW_FILE` | `post.yml` (省略可) |
| `GITHUB_REF` | `main` (省略可) |

### D-3. 動作テスト

- GASエディタで関数 `testTrigger` を選び **実行**(初回は認可ダイアログ → 許可)
- GitHub の **Actions** に実行が現れ、X に投稿されれば成功

### D-4. 時間トリガーを設定

1. GASエディタ左の **時計アイコン(トリガー)** → **トリガーを追加**
2. 実行する関数: **`postToX`** / イベントのソース: **時間主導型** / 希望の時間帯
3. 保存

### D-5. 投稿文のカスタマイズ

`gas/Code.gs` の **`generateText()`** を編集します。
- URL: 文字列にそのまま含める(自動リンク化)
- 改行: JavaScript の `'\n'`
- スプレッドシート連携や外部API取得で動的生成も可能

投稿処理本体は **`postTextToX(text)`** が担当します(関数名・引数は従来互換)。

---

## 画像投稿(オプション)

画像はオプション機能です。**指定しなければテキストのみ投稿**されます。
画像処理のコードは `media.py` に分離されており、画像が無ければ実行されません。

### 使い方

1. 投稿したい画像を `images/` フォルダに入れてコミットする
   (GitHub Actions から使うため、リポジトリに含める必要がある)
2. 画像を指定する。1ツイート最大4枚。

**予約投稿(schedule.json)** — `images` を追加(任意):

```json
[
  {
    "time": "2026-06-10T09:00:00+09:00",
    "text": "新商品の紹介です📷",
    "images": ["images/product1.png", "images/product2.png"],
    "posted": false
  }
]
```

**手動実行(Actions)** — Run workflow の `images` 欄にカンマ区切りで入力:
`images/product1.png,images/product2.png`

**ローカル** — `--images` で指定:

```powershell
python post.py --text "画像テスト" --images "images/a.png,images/b.png"
```

**GAS** — `postTextToX(text, images)` の第2引数(任意):

```javascript
postTextToX('画像つき投稿です', 'images/a.png');   // 画像あり
postTextToX('テキストだけの投稿');                  // 画像なし(従来どおり)
```

> 指定した画像ファイルが存在しない場合は警告を出してスキップし、テキストのみ投稿します。

---

## 運用上の注意

- **Cookie失効**: `auth_token` は数週間〜数ヶ月で予告なく失効します。失効するとジョブが
  失敗します。その場合は **パートA-3 を再実行** して `AUTH_STATE_B64` を更新してください。
- **DC-IP**: GitHub Actions はデータセンターIPのため、再認証を求められることがあります。
- **規約**: API非経由の自動投稿はXの規約上グレーです。自分のアカウントで常識的な頻度に
  留めてください。過度な自動化はアカウント制限・凍結のリスクがあります。
- **cronの遅延**: GitHub Actions の cron は数分の遅延が出ることがあります。
- **画像投稿**: 現状はテキスト専用です。画像が必要な場合は別途拡張が必要です。
