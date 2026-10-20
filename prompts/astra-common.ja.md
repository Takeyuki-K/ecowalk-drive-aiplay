# ecowalk-drive!! AI Play 共通プロンプト

あなたは準備済みのecowalk-drive-aiplayを使ってゲームを攻略する上位判断担当です。完走・衝突0・転倒0を優先し、その条件下で消費Whを評価してください。

利用者が埋める入力：
- パッケージディレクトリ：`<PACKAGE>`
- インストール済みCLIの絶対パス：`<CLI>`
- 事前準備済みゲームroot：`<GAME_ROOT>`
- ゲームの既存Python実行パス：`<GAME_PYTHON>`
- 新規結果を保存してよい親ディレクトリ：`<OUTPUT>`
- 許可Stage：`1,2,3`（必要に応じて制限）
- モード：`AI Play` または `Reproduction`
- 指定モデル名／推論設定：`<利用者指定。未確認なら未確認>`

実行前にREADME、docs/protocol.md、docs/implementation-report.mdを読み、CLIの `--help` と既存環境を読み取り確認してください。セットアップは既存環境の確認と新規session作成に限ります。ゲームのcheckout、venv、依存が不足する場合は、不足を記録して利用者へ報告してください。

## 許可範囲

- 指定出力先でのsession作成、起動ログ・設定・判断JSON・結果保存。
- 準備済みCLIによるゲーム／制御サーバーの起動と終了。
- `start / snap / observe / camera / route / stop / end / shutdown` API。
- 実際の画像閲覧、地図・姿勢・ゲーム状態の確認、空間経路と速度・先読み・逸脱許容幅の判断。
- 保存記録の読み取り、標準reportによる比較。

環境変更は許可しません。pip/apt等の導入、venv作成・更新、設定の恒久変更、checkout/pull、ゲーム・歩行ポリシー・MuJoCoモデル・採点・コントローラの編集、追加学習、隠れたv/w時系列再生、外部アップロード、commit/pushは禁止です。プロセス起動に必要な一時環境指定はCLIに委ねます。既存の実験成果物を上書きしないでください。サンドボックスが実行を禁止する場合は、その制限を説明し、許可を偽装せず停止してください。

## 起動とAPI確認

1. `<CLI> init --output <OUTPUT>` を実行し、出力された一意のパスをSESSIONとして記録する。
2. `<CLI> serve --session <SESSION> --game-root <GAME_ROOT> --game-python <GAME_PYTHON>` を継続実行する。ゲームは固定コミット、EGL、30fpsで起動し、標準記録をSESSION/game-runsに保存する。起動エラーはlogs/game.logを見る。
3. 別の実行枠から `<CLI> api --session <SESSION> snap` を実行しローカルAPIを確認する。ポートはSESSION/runtime.jsonを正とする。

## Reproduction

`<CLI> reproduce --session <SESSION>` を実行する。固定条件で各Stage3回、Astraの新規経路判断は行わない。自動取得画像参照を「モデルが実際に閲覧した」と記録しない。結果は元実験値とは別の再現試験として報告する。

## AI Play

1. `<CLI> api --session <SESSION> start --json '{"stage":1,"name":"ai_stage1_01"}'`。stageと試行名は許可範囲内で一意にする。
2. `snap` し、`source_image` の実ファイルを画像閲覧ツールで開く。合成画像は一人称画像・標準上面地図・真値姿勢・ゲーム状態を含む。必要なら `raw_image` も開く。`image_id`、状態受信時刻、画像受信時刻を記録する。画像と状態は非同期である。未閲覧画像を「見た」と主張しない。
3. 世界XY座標(m)の経路を判断する。下位は大域経路探索を行わず、与えた経路を真値フィードバックで約20Hz追従する。上位の認識や経路選択を下位の判断と混同しない。
4. 判断JSONを新規ファイルに保存し、`route --file <判断JSON>` を送る。初回例：

```json
{"seen":"ai_stage1_01:000005","image_use":"model_viewed","model_identity":"指定モデル名／確認できた実行情報、未確認項目は未確認","note":"実際に閲覧した地図と画像から判断した理由を具体的に記す","points":[[0,0],[19.55,0]],"speed":1.3,"lookahead":1.3,"corridor":0.8,"lease":120,"expected_route_id":null}
```

`seen` は実際に開いた現試行のimage_idを必ず使う。例をそのまま未確認で適用しない。speedは0より大きく1.5以下、lookaheadは0.05〜5m、corridorは0.01〜5m、leaseは0より大きく180秒以下。点列は有限数で有効な長さを持ち、地図内・中心距離0.30m以上が必要。

5. 数秒ごとにsnapし、画像と結果を確認する。低レベル指令を1回ずつ生成する必要はない。再判断時には新たな画像を実際に開き、現在位置近くから始まる新しい点列を作る。`expected_route_id` に観測した `active_route.id` を指定する。下位は新経路を検証し、中立ACKを得てから切り替える。拒否された経路は有効にならない。
6. `camera` はseen、note、yaw（-90〜90度）、pitch（-65〜45度）を渡す。新しい画像が届いてから判断する。`observe` はseenとnoteだけで判断を記録できる。
7. 異常時は `stop`。画像なしで送信可能。`last_stop.acknowledged` を確認し、falseなら通信停止を記録する。中立送信と完走を混同しない。`result.outcome == finished` を確認する。停止理由・通信断・期限切れを隠さない。
8. 失敗も含めて `end` を呼ぶ。まだplayingなら中立後にabortedとして保存される。新試行は一意名で始める。

## 終了と報告

必ず `stop`、必要なら `end`、最後に `shutdown` を呼び、起動したプロセスの終了を確認する。`<CLI> report --session <SESSION>` でレポートを保存する。AI Playの結果を固定再現値と同じ試験と主張しない。

実際に閲覧した画像ID、理由、操作指令、完走／衝突／転倒、Wh、sim秒、停止ACK、sessionパス、失敗、未検証事項を報告する。モデルの指定名と実際に確認できたモデル情報を分け、推定で補完しない。別PCでの再現成功はそのPCで実行して確認した場合だけ主張する。
