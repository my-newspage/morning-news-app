# 朝のニュース Webアプリ

Googleアカウント不要のニュースリーダー。日経平均・不動産・世界情勢・金融市場・ファッション業界を毎日各2件、合計最大10件RSSから収集します。既読・お気に入り・前回の記事とスクロール位置を**同じ端末・同じブラウザー内**に保存します。

## 公開手順（GitHubアカウントは必要）
1. GitHubで新しい **Public** リポジトリ（例 `morning-news`）を作る。
2. このフォルダー内の `index.html`、`update_news.py`、`data/news.json`、`.github/workflows/update.yml` を**フォルダー構造ごと**アップロードする。
3. リポジトリの **Settings → Pages → Build and deployment → Deploy from a branch → main / (root) → Save** を選ぶ。
4. **Actions → 朝のニュース自動更新 → Run workflow** で初回更新を実行する。
5. 数分後、`https://ユーザー名.github.io/morning-news/` にアクセスする。Android Chromeのメニューから「ホーム画面に追加」でアプリのように起動できる。

## 注意事項
- GitHub Actionsの定時実行は遅延することがあり、**9時ちょうどの反映は保証されません**。
- このアプリは**公開RSSから記事見出しと概要を収集**します。ChatGPTが生成する5分ニュースブリーフを自動転記するものではありません。独自のAI要約・分析は別途API等の接続が必要です。
- Google News RSSの取得制限、ニュース配信側の変更、GitHub Actionsの停止により更新できない場合があります。
- 既読情報はブラウザーのlocalStorageに保存します。別端末への同期やバックアップはありません。
- RSSの配信元へのリンクを表示します。記事本文の無断転載はしません。
- GitHub Pagesの公開リポジトリに保存する記事データは**公開情報**です。
- アーカイブは最大60日分です。
