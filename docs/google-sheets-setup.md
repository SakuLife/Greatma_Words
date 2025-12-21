# Google Sheets タスク管理セットアップガイド

このプロジェクトのタスク管理をGoogle Sheetsで行うための設定手順です。

## セットアップ手順

### 1. Google Sheetsの作成

1. [Google Sheets](https://sheets.google.com/)にアクセス
2. 新しいスプレッドシートを作成
3. タイトルを「GreatMan Words - タスク管理」に変更

### 2. CSVファイルのインポート

1. 作成したスプレッドシートを開く
2. **ファイル > インポート** を選択
3. `docs/tasks-master.csv` をアップロード
4. インポート設定：
   - インポート場所: 新しいシートに挿入
   - 区切り文字の種類: カンマ
   - テキストを数値、日付、数式に変換: いいえ

### 3. 推奨シート構成

以下のシートを作成することを推奨します：

#### シート1: タスクマスター（CSVからインポート）
すべてのタスクの一覧

#### シート2: 週次スプリント
週ごとのタスク管理

| 週 | 開始日 | 終了日 | タスクID | タスク内容 | 計画工数(h) | 実績工数(number) | 達成率(%) | ステータス | ブロッカー |
|----|--------|--------|---------|-----------|-----------|----------|---------|----------|-----------|

#### シート3: 動画制作ログ
生成した動画の記録

| 日付 | 人物名 | テーマ | 動画時間(分) | 生成時間(分) | プロジェクトパス | YouTube URL | 視聴回数 | いいね数 | コメント数 | 備考 |
|------|--------|--------|------------|------------|--------------|-------------|---------|---------|----------|------|

#### シート4: コスト管理
API使用量とコスト追跡

| 日付 | サービス | 用途 | 使用量 | 単価 | 合計金額 | 累計金額 | 備考 |
|------|---------|------|--------|------|---------|---------|------|

**サービス例**:
- Claude API (Anthropic)
- OpenAI API (GPT-4, DALL-E 3)
- nanobanana API
- YouTube Data API

#### シート5: パフォーマンストラッキング
動画のパフォーマンス分析

| 動画ID | タイトル | 投稿日 | 7日後視聴回数 | 30日後視聴回数 | CTR(%) | 平均視聴時間 | いいね率(%) | コメント率(%) | 評価 |
|--------|---------|--------|-------------|--------------|--------|------------|----------|------------|------|

### 4. 便利な機能設定

#### データの入力規則

**ステータス列**に入力規則を設定:
1. ステータス列を選択
2. **データ > データの入力規則**
3. 条件: リストを直接指定
4. 項目: `未着手,進行中,完了,保留,中止`
5. セルにプルダウンリストを表示にチェック

**優先度列**に入力規則を設定:
1. 優先度列を選択
2. 同様に入力規則を設定
3. 項目: `高,中,低`

#### 条件付き書式

**ステータスに応じた色分け**:
1. ステータス列を選択
2. **表示形式 > 条件付き書式**
3. 以下のルールを追加:
   - 「完了」= 緑色背景
   - 「進行中」= 黄色背景
   - 「未着手」= 白色背景
   - 「保留」= オレンジ色背景
   - 「中止」= グレー背景

**優先度に応じた色分け**:
1. 優先度列を選択
2. 条件付き書式を追加:
   - 「高」= 赤色テキスト
   - 「中」= オレンジ色テキスト
   - 「低」= グレーテキスト

#### フィルタービュー

**自分のタスクだけ表示**:
1. **データ > フィルタ表示を作成**
2. 担当者列で自分の名前を選択
3. フィルタービューに名前を付けて保存

**今週のタスク**:
1. 新しいフィルタービューを作成
2. 期限列で「今週」の範囲を指定
3. ステータスで「未着手」「進行中」を選択

### 5. 自動化（Google Apps Script）

#### 完了タスクの自動アーカイブ

スクリプトエディタを開き、以下を追加:

```javascript
function archiveCompletedTasks() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const masterSheet = ss.getSheetByName('タスクマスター');
  const archiveSheet = ss.getSheetByName('完了タスク');

  const data = masterSheet.getDataRange().getValues();
  const completed = [];

  for (let i = data.length - 1; i >= 1; i--) {
    if (data[i][4] === '完了') { // ステータス列が5列目の場合
      completed.push(data[i]);
      masterSheet.deleteRow(i + 1);
    }
  }

  if (completed.length > 0) {
    archiveSheet.getRange(archiveSheet.getLastRow() + 1, 1, completed.length, completed[0].length)
      .setValues(completed);
  }
}
```

#### 週次レポート自動生成

```javascript
function generateWeeklyReport() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sprintSheet = ss.getSheetByName('週次スプリント');
  const data = sprintSheet.getDataRange().getValues();

  let totalPlanned = 0;
  let totalActual = 0;
  let completed = 0;

  for (let i = 1; i < data.length; i++) {
    totalPlanned += data[i][5];
    totalActual += data[i][6];
    if (data[i][8] === '完了') completed++;
  }

  const report = `週次レポート
完了タスク: ${completed}件
計画工数: ${totalPlanned}h
実績工数: ${totalActual}h
達成率: ${((completed / (data.length - 1)) * 100).toFixed(1)}%`;

  Logger.log(report);
  // Slackへの通知も可能
}
```

### 6. 共有設定

1. 右上の **共有** ボタンをクリック
2. チームメンバーのメールアドレスを入力
3. 権限を設定:
   - **編集者**: 全メンバー
   - **閲覧者**: ステークホルダー
4. リンクをコピーして `docs/task-management.md` に追記

### 7. モバイルアプリ連携

スマホからも確認できるように設定:
1. Google Sheetsアプリをインストール
2. スプレッドシートを開く
3. オフラインアクセスを有効化（設定 > オフラインで利用可能にする）

---

## ダッシュボード作成（オプション）

### Google Data Studioでビジュアライゼーション

1. [Google Data Studio](https://datastudio.google.com/)にアクセス
2. **作成 > データソース** を選択
3. Google Sheetsを接続
4. 以下のグラフを作成:
   - **円グラフ**: ステータス別タスク数
   - **棒グラフ**: カテゴリ別タスク数
   - **折れ線グラフ**: 週次完了タスク数推移
   - **テーブル**: 最優先タスク一覧

---

## テンプレート

スプレッドシートのテンプレートをコピーして使用できます：

**テンプレートURL**: （こちらにテンプレートのURLを記載）

---

## トラブルシューティング

### CSVインポート時に文字化けする

1. CSVファイルをUTF-8で保存し直す
2. または、Excelで開いて「名前を付けて保存」でCSV UTF-8形式を選択

### 数式が正しく動作しない

- 日本語版Sheetsの場合、関数名が日本語になっている可能性があります
- 例: `SUM` → `合計`, `IF` → `もし`

### 共有リンクが機能しない

- リンク共有設定を確認してください
- **リンクを知っている全員が閲覧可**に設定すると便利です

---

## 関連リンク

- [Google Sheets ヘルプ](https://support.google.com/docs/answer/6000292)
- [Google Apps Script ドキュメント](https://developers.google.com/apps-script)
- [Google Data Studio ガイド](https://support.google.com/datastudio)

---

**最終更新**: 2025-12-20
