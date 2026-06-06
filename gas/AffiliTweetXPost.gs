/**
 * ============================================
 * AffilTweet - X投稿 (API不使用版)  AffiliTweetXPost.gs
 * ============================================
 *
 * 旧 XService.gs(X API + OAuth1)の置き換え。
 * X APIを使わず、GitHub Actions(Playwright)を起動して投稿する。
 * 既存の postToX / postToXWithImage と同じ関数名・引数なので、
 * 呼び出し側のコードは変更不要(ドロップイン置き換え)。
 *
 * このファイルだけで完結する(OAuth1ライブラリ等は不要)。
 *
 * 【事前設定 — スクリプトプロパティ】
 *   GASエディタ左「プロジェクトの設定(歯車)」→「スクリプト プロパティ」に追加:
 *     GITHUB_TOKEN  : GitHub Personal Access Token(fine-grained / Actions=Read and write)
 *     GITHUB_OWNER  : 例 "digitarod"
 *     GITHUB_REPO   : 例 "xposter"
 *     WORKFLOW_FILE : "post.yml"(省略可)
 *     GITHUB_REF    : "main"(省略可)
 *
 * 【旧コードからの移行】
 *   不要になる関数: getXService / authCallback / uploadMediaToX /
 *                   postToXWithMediaId / getXAuthorizationUrl / resetXAuth /
 *                   testXConnection  (および OAuth1 ライブラリ)
 *   X_API_KEY 等の API キーも不要。
 *
 * 【注意】
 *   投稿は GitHub Actions 側で非同期に実行されるため、戻り値に postId は含まれない。
 *   success は「ワークフロー起動に成功したか」を表す。
 */

// 本文の最大文字数: 280 - t.co(23) - 改行"\n\n"(2) = 255
var AFFIL_MAX_CONTENT = 280 - 23 - 2;

/**
 * Xに投稿(テキスト + アフィリURL)
 * @param {string} content 投稿本文
 * @param {string} url 添付URL(アフィリエイトリンク)
 * @returns {Object} { success, content }
 */
function postToX(content, url) {
  console.log('X投稿開始(API不使用)...');
  var text = buildTweetText_(content, url);
  var ok = dispatchToActions_(text, null);
  return { success: ok, content: text };
}

/**
 * 画像付きでXに投稿
 * @param {string} content 投稿本文
 * @param {string} url 添付URL(アフィリエイトリンク)
 * @param {string} imageUrl 商品画像URL
 * @returns {Object} { success, content, hasImage }
 */
function postToXWithImage(content, url, imageUrl) {
  console.log('X画像付き投稿開始(API不使用)...');

  // 画像ON/OFFのランダム判定(従来仕様を踏襲)
  if (!shouldPostWithImage()) {
    console.log('画像なしモードが選択されました(ランダム判定)');
    return postToX(content, url);
  }
  if (!imageUrl) {
    console.log('画像URLがないため、テキストのみで投稿');
    return postToX(content, url);
  }

  // 画像URLを高解像度化してから渡す。投稿側(Playwright)が実行時にDLして添付する。
  var bigImageUrl = enlargeImageUrl_(imageUrl);
  var text = buildTweetText_(content, url);
  var ok = dispatchToActions_(text, bigImageUrl);
  return { success: ok, content: text, hasImage: true };
}

/**
 * 画像URLをできるだけ高解像度版に変換する。
 * 楽天のサムネイル(?_ex=WxH)はサイズ指定を大きくすると高画質になる。
 * 対応できないURLはそのまま返す。
 * @param {string} imageUrl
 * @returns {string}
 */
function enlargeImageUrl_(imageUrl) {
  if (!imageUrl) {
    return imageUrl;
  }
  // 楽天: 既に ?_ex=WxH が付いていれば 700x700 に置換
  if (imageUrl.indexOf('?_ex=') !== -1) {
    return imageUrl.replace(/\?_ex=\d+x\d+/, '?_ex=700x700');
  }
  // 楽天サムネイルでサイズ未指定なら 700x700 を付与
  if (imageUrl.indexOf('thumbnail.image.rakuten.co.jp') !== -1) {
    return imageUrl + '?_ex=700x700';
  }
  // その他(Amazon等)はそのまま
  return imageUrl;
}

/**
 * 画像投稿するかどうかをランダムに判定。
 * getConfig が定義されていればそれを使う。無ければ常に画像ありとみなす。
 * @returns {boolean}
 */
function shouldPostWithImage() {
  if (typeof getConfig !== 'function') {
    return true;
  }
  var enabled = getConfig('IMAGE_POST_ENABLED');
  if (enabled !== 'TRUE' && enabled !== true) {
    return false;
  }
  var rate = parseInt(getConfig('IMAGE_POST_RATE') || '50', 10);
  var random = Math.floor(Math.random() * 100);
  console.log('画像投稿判定: 確率' + rate + '% vs ランダム値' + random);
  return random < rate;
}

/**
 * 本文 + URL を組み立てる。本文が長い場合は句読点で自然に切り詰める。
 * (従来の文字数調整ロジックを踏襲)
 * @returns {string}
 */
function buildTweetText_(content, url) {
  if (content.length > AFFIL_MAX_CONTENT) {
    console.warn('本文が' + AFFIL_MAX_CONTENT + '文字を超過: ' + content.length + '文字');
    var truncated = content.substring(0, AFFIL_MAX_CONTENT);
    var lastPunctuation = Math.max(
      truncated.lastIndexOf('。'),
      truncated.lastIndexOf('！'),
      truncated.lastIndexOf('？'),
      truncated.lastIndexOf('!'),
      truncated.lastIndexOf('?')
    );
    if (lastPunctuation > AFFIL_MAX_CONTENT * 0.7) {
      content = truncated.substring(0, lastPunctuation + 1);
    } else {
      content = truncated;
    }
    console.log('切り詰め後の本文: ' + content.length + '文字');
  }
  return content + '\n\n' + url;
}

/**
 * GitHub Actions の投稿ワークフローを起動する(内部関数)。
 * @param {string} text 投稿テキスト
 * @param {string|null} images 添付画像。URL or リポジトリ内パス。カンマ区切り可。null可。
 * @returns {boolean} 起動成功で true
 */
function dispatchToActions_(text, images) {
  var props = PropertiesService.getScriptProperties();
  var token = props.getProperty('GITHUB_TOKEN');
  var owner = props.getProperty('GITHUB_OWNER');
  var repo = props.getProperty('GITHUB_REPO');
  var workflow = props.getProperty('WORKFLOW_FILE') || 'post.yml';
  var ref = props.getProperty('GITHUB_REF') || 'main';

  if (!token || !owner || !repo) {
    throw new Error('スクリプトプロパティ GITHUB_TOKEN / GITHUB_OWNER / GITHUB_REPO を設定してください。');
  }

  // 画像はオプション。指定があるときだけ inputs に含める。
  var inputs = { text: text };
  if (images) {
    inputs.images = images;
  }

  var apiUrl = 'https://api.github.com/repos/' + owner + '/' + repo +
    '/actions/workflows/' + workflow + '/dispatches';

  var response = UrlFetchApp.fetch(apiUrl, {
    method: 'post',
    contentType: 'application/json',
    headers: {
      Authorization: 'Bearer ' + token,
      Accept: 'application/vnd.github+json',
      'X-GitHub-Api-Version': '2022-11-28'
    },
    payload: JSON.stringify({ ref: ref, inputs: inputs }),
    muteHttpExceptions: true
  });

  var code = response.getResponseCode();
  if (code === 204) {
    console.log('ワークフロー起動に成功しました');
    if (typeof logToSheet === 'function') {
      logToSheet('INFO', 'dispatchToActions', '起動成功');
    }
    return true;
  } else {
    var body = response.getContentText();
    console.error('ワークフロー起動に失敗: ' + code + ' - ' + body);
    if (typeof logToSheet === 'function') {
      logToSheet('ERROR', 'dispatchToActions', '起動失敗: ' + code + ' - ' + body);
    }
    return false;
  }
}

/**
 * ライブテスト(実際に投稿される)。GASエディタでこの関数を選んで実行。
 */
function testPostToXLive() {
  console.log('=== X投稿ライブテスト(API不使用) ===');
  var testContent = '🧪 AffilTweet テスト投稿\n' + new Date().toLocaleString('ja-JP');
  var testUrl = 'https://example.com';
  var result = postToX(testContent, testUrl);
  console.log('結果: ' + JSON.stringify(result));
  return result;
}

/**
 * 画像付きライブテスト(実際に投稿される)。
 */
function testPostToXWithImageLive() {
  console.log('=== X画像付き投稿ライブテスト(API不使用) ===');
  var testContent = '🧪 AffilTweet 画像テスト\n' + new Date().toLocaleString('ja-JP');
  var testUrl = 'https://example.com';
  // 公開されている適当な画像URLに置き換えてテストする
  var testImageUrl = 'https://via.placeholder.com/600x400.png';
  var result = postToXWithImage(testContent, testUrl, testImageUrl);
  console.log('結果: ' + JSON.stringify(result));
  return result;
}
