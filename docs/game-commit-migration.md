# ゲーム固定コミットの履歴書き換えへの対応

2026-10-20、`k1-mp-ecowalk-game` のGitコミット著者名匿名化に伴い、実行時に要求する固定コミットを更新しました。

| 項目 | SHA |
|---|---|
| 旧コミット（過去の実行記録） | `d1ef1562e463b5cfd0c97a8f24d1962b96c89357` |
| 新コミット（今後のcheckout・実行） | `1a4e9e747d8c71e5200c7badf91944c090a6883d` |
| 新旧共通のGit Tree | `4630f4942030db7ba1596c5f4702616ce9736eb8` |

Git Treeが同一のため、ゲームの追跡ファイルの内容・モード・構成は変わりません。コントローラーの変更は `cli.py` の `EXPECTED['game']` のみです。歩行ポリシー・推論方法・制御ロジック・採点・過去の測定値は変更していません。publicとteleopの固定SHAも変更していません。

## 過去の記録の扱い

以下の旧SHAは実行・確認当時の記録なので、そのまま保持しています。新SHAで過去の実験を実行したことを意味しません。

- `docs/environment-comparison.json`
- `reference/experiment11/environment.json`
- `THIRD_PARTY_NOTICES.md` の2026-10-19の確認記録
- 上記の `src/ecowalk_drive_aiplay/data/` 内の同梱コピー

READMEの固定版・checkoutコマンド、同梱README、CLIの固定SHA、第三者表示へのGitHubリンクは新SHAを使用します。既存の旧SHAのcheckoutでは固定版検査が失敗するため、READMEに従い新しい作業ディレクトリへ取得してください。

## 検証（2026-10-20）

- GitHubからゲーム・public・teleopを新規cloneし、READMEに記載した3つの固定SHAへcheckoutできることを確認。
- 既存の旧ゲームと新しいゲームの `git rev-parse HEAD^{tree}` が上記Tree SHAで一致。追跡ファイル全件のSHA256も一致。
- 修正版コントローラーを新しいPython 3.10 venvへビルド・インストール。CLIのhelp、ゲーム・コントローラー両Pythonの `pip check`、READMEのFFmpeg H.264 / `-fps_mode` チェックに成功。
- ソース版とインストール済み配布物の両方で、ローカルHTTPを有効にした既存21テストがすべて成功。動画テストはMuJoCo導入済みPythonで実行。
- 実際の `serve` で新SHAとvendorの固定SHA・clean状態の検査を通過。旧SHAはゲーム起動前に拒否されることも確認。
- READMEの `init → serve → snap` が成功。起動前の `active: null` を確認。READMEのBashブロック7個は `bash -n` に成功。
- 同梱READMEの固定再現コマンドを `reproduce --stages 1 2 3 --repeats 1` で実行。3/3完走、衝突0、転倒0、終了時の中立ACK 3/3。`report` と `shutdown` も成功し、サーバーの終了コードは0。過去の測定値との一致を要求する試験ではありません。
- 既存ゲーム・public・teleop（vendorコピーを含む）のHEAD・Git状態・追跡ファイルSHA256は実行前後で一致。新規checkoutも実行前後で一致。過去の環境JSON4ファイルは修正前とバイト同一。

検証には `/tmp/ecowalk-sha-update-20261020/` の新規checkout・venv・出力先を使用しました。ゲームのPython依存は既存venvを読み取り利用し、ゲームモジュールは新SHAのcheckoutからロードされたことを確認しました。OSパッケージ・ゲームの全Python依存・Codexの新規導入、Astraによる新しい経路判断、二視点動画の再生成は今回の検証範囲に含みません。

旧SHAは追跡対象に加え、無視対象・未追跡ファイルを含めて検索しました。既存の未追跡 `README_simplified.md` と過去の `build/`・`*.egg-info/` 生成物は変更・commit対象に含めていません。配布物の検証は古いビルド生成物を含めない新規ソースコピーから行いました。
