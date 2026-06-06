/**
 * GAS から GitHub Actions の投稿ワークフローを起動するスクリプト。
 *
 * 仕組み:
 *   1. 時間主導トリガーで postToX() が定期実行される
 *   2. generateText() で投稿文を生成
 *   3. GitHub の workflow_dispatch API を叩き、text を渡してワークフロー起動
 *   4. GitHub Actions 側が post.py --text "..." を実行してXに投稿
 *
 * 事前設定(スクリプトプロパティ):
 *   GITHUB_TOKEN : GitHub Personal Access Token
 *                  (fine-grained: 対象リポに Actions=Read and write 権限)
 *   GITHUB_OWNER : "digitarod"
 *   GITHUB_REPO  : "xposter"
 *   WORKFLOW_FILE: "post.yml"   (省略時は post.yml)
 *   GITHUB_REF   : "main"       (省略時は main)
 *
 * プロパティ設定方法:
 *   GASエディタ左の「プロジェクトの設定(歯車)」→「スクリプト プロパティ」→ 追加
 */

/**
 * 投稿テキストを生成する。ここをお客様ごとに自由に実装する。
 * URLや改行(\n)もそのまま使える。
 */
function generateText() {
  const now = new Date();
  const date = Utilities.formatDate(now, 'Asia/Tokyo', 'M月d日');
  // 例: 日付入りの定型文 + URL
  return [
    `【${date}の更新】`,
    '本日の記事を公開しました📝',
    'https://example.com/blog/' + Utilities.formatDate(now, 'Asia/Tokyo', 'yyyyMMdd'),
    '#ブログ更新',
  ].join('\n');
}

/**
 * メイン: テキストを生成して GitHub Actions を起動する。
 * これを時間主導トリガーに登録する。
 */
function postToX() {
  const text = generateText();
  triggerWorkflow(text);
}

/**
 * GitHub の workflow_dispatch を叩いてワークフローを起動する。
 * @param {string} text 投稿するテキスト
 */
function triggerWorkflow(text) {
  const props = PropertiesService.getScriptProperties();
  const token = props.getProperty('GITHUB_TOKEN');
  const owner = props.getProperty('GITHUB_OWNER');
  const repo = props.getProperty('GITHUB_REPO');
  const workflow = props.getProperty('WORKFLOW_FILE') || 'post.yml';
  const ref = props.getProperty('GITHUB_REF') || 'main';

  if (!token || !owner || !repo) {
    throw new Error('スクリプトプロパティ GITHUB_TOKEN / GITHUB_OWNER / GITHUB_REPO を設定してください。');
  }

  const url = `https://api.github.com/repos/${owner}/${repo}/actions/workflows/${workflow}/dispatches`;
  const payload = {
    ref: ref,
    inputs: { text: text },
  };

  const res = UrlFetchApp.fetch(url, {
    method: 'post',
    contentType: 'application/json',
    headers: {
      Authorization: 'Bearer ' + token,
      Accept: 'application/vnd.github+json',
      'X-GitHub-Api-Version': '2022-11-28',
    },
    payload: JSON.stringify(payload),
    muteHttpExceptions: true,
  });

  const code = res.getResponseCode();
  if (code === 204) {
    Logger.log('ワークフロー起動に成功しました。投稿テキスト:\n' + text);
  } else {
    throw new Error('ワークフロー起動に失敗 (HTTP ' + code + '): ' + res.getContentText());
  }
}

/**
 * 動作確認用: 固定テキストで起動テストする。
 * GASエディタでこの関数を選んで「実行」する。
 */
function testTrigger() {
  triggerWorkflow('GASからのテスト投稿です\nhttps://example.com #テスト');
}
