# ecowalk-drive-aiplay

実験11の実使用コードを移植した、ecowalk-drive!!用の外部Python制御パッケージです。Astraが選んだ世界座標の経路を約20Hzで追従します。**経路追従器自身は大域経路探索を行いません。** ゲーム、歩行ポリシー、MuJoCoモデル、採点規則を変更せず、既存のローカルHTTP APIを利用します。

実験11の固定確認試験は各Stage 3回、計9回すべて完走・衝突0でした。平均消費量はStage1 0.855397 Wh、Stage2 0.959717 Wh、Stage3 1.324878 Whです。これは元実験の実績であり、新パッケージや別PCでの成功保証ではありません。今回の検証は [実装・検証レポート](docs/implementation-report.md) を参照してください。

## 必要なもの

基準環境はLinux x86_64 / Python 3.10.12 / EGL描画です。コントローラの追加依存はPillow 12.3.0のみです。ROS、モデルAPIキー、追加学習は不要です。Astraなしで固定再現試験を実行できます。

ゲームは外部チェックアウトとして用意します。モデル、ゲームソース、重み、フォント、仮想環境は本パッケージに同梱しません。

|依存|固定コミット／バージョン|
|---|---|
|[k1-mp-ecowalk-game](https://github.com/Takeyuki-K/k1-mp-ecowalk-game)|`1a4e9e747d8c71e5200c7badf91944c090a6883d`|
|ゲームのvendor/k1-mp-ecowalk-public|`04b1c0fded94dcde76411e6bd9d914a56d41102a`|
|ゲームのvendor/k1-mp-ecowalk-teleop|`a5ea3dbf4f97501c18ff090f86ff4cd413f6aaea`|
|MuJoCo / NumPy / Torch CPU|3.15.0 / 2.2.6 / 2.14.1+cpu|
|Pillow / GLFW / PyOpenGL|12.3.0 / 2.10.2 / 3.1.10|

ゲームの著者名匿名化に伴う履歴書き換えで固定コミットを更新しました。新旧コミットのGit Treeは同一です。過去の記録の旧SHAは保持しています。[新旧SHAの対応と検証記録](docs/game-commit-migration.md)を参照してください。

ゲームの固定コミットのREADMEに従って利用者が依存を事前準備してください。既存checkoutへのpullやインストールをコントローラは実行しません。別PCへのゲーム依存の全wheel取得は未検証です。[依存の固定範囲](locks/README.md) に詳細があります。

## インストール

環境作成・パッケージ導入は利用者が行います。共通プロンプトで動作するAstraにはこれらの環境変更を許可しません。既存ゲーム用venvを変更せず、専用venvを用意してください。

```bash
python3.10 -m venv .venv
.venv/bin/python -m pip install .
.venv/bin/ecowalk-aiplay --help
```

ソースからの実行も可能です。依存が導入済みなら、次の形式で以後の `ecowalk-aiplay` を置き換えられます。

```bash
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 /path/to/prepared/python -m ecowalk_drive_aiplay.cli --help
```

## Reproductionモード

各実行には新規sessionを作成します。`init` の出力を `SESSION` に設定してください。以下のパスは利用者の環境に置き換えます。

```bash
.venv/bin/ecowalk-aiplay init --output /path/to/new-results
export SESSION=/path/to/new-results/INITが出力したID
.venv/bin/ecowalk-aiplay serve --session "$SESSION" \
  --game-root /path/to/k1-mp-ecowalk-game \
  --game-python /path/to/k1-mp-ecowalk-game/.venv/bin/python
```

`serve` はゲームをEGL・30fps・専用出力先で起動し、制御サーバーを前面実行します。ゲームとvendorのコミット・clean状態を確認し、使用中のポートでは失敗します。別ターミナルから：

```bash
.venv/bin/ecowalk-aiplay reproduce --session "$SESSION"
.venv/bin/ecowalk-aiplay report --session "$SESSION"
.venv/bin/ecowalk-aiplay api --session "$SESSION" shutdown
```

既定でStage1〜3を各3回実行します。`--stages 2 --repeats 1` で個別確認もできます。固定JSONと展開済み経路を照合し、異なる地図では実行しません。同じ試行名は上書きせず、再試験には新規sessionが必要です。初期観測には期限があり、失敗・中断も保存します。元の実験11フォルダは不要です。インストール済み配布物の設定・プロンプトの場所は `ecowalk-aiplay resources` で確認できます。

ポート変更は `configs/runtime.example.json` を複製し、`init --config /path/to/runtime.json` へ渡します。CLI、試行ランナー、サーバーはsession内の同じ `runtime.json` を読みます。既定ゲーム8128、制御8129、接続先は127.0.0.1のみです。

## Codex/AstraによるAI Playモード

準備済み環境で [共通プロンプト](prompts/astra-common.ja.md) の入力欄を埋め、そのままCodex/Astraへ渡します。画像を開ける実行環境が必要です。モデル呼び出しをこのパッケージが代行する仕組みはありません。モデル名は自己申告と確認済み情報を区別します。

```bash
.venv/bin/ecowalk-aiplay api --session "$SESSION" start --json '{"stage":1,"name":"ai_stage1_01"}'
.venv/bin/ecowalk-aiplay api --session "$SESSION" snap
```

`snap` の `source_image` を実際に開きます。合成画像には一人称画像、標準上面地図、MuJoCo真値姿勢、ゲーム状態が含まれます。`image_id` を `seen` とし、判断理由と点列をJSONファイルへ保存して送信します。

```json
{"seen":"ai_stage1_01:000005","note":"閲覧した地図上で障害物がなく、終端で中立化できる直線を選ぶ","image_use":"model_viewed","model_identity":"利用者指定名。実行基盤の確認情報は別記","points":[[0,0],[19.55,0]],"speed":1.3,"lookahead":1.3,"corridor":0.8,"lease":120,"expected_route_id":null}
```

```bash
.venv/bin/ecowalk-aiplay api --session "$SESSION" route --file /path/to/decision.json
.venv/bin/ecowalk-aiplay api --session "$SESSION" snap
.venv/bin/ecowalk-aiplay api --session "$SESSION" stop
.venv/bin/ecowalk-aiplay api --session "$SESSION" end
.venv/bin/ecowalk-aiplay api --session "$SESSION" shutdown
```

経路の再判断では、新しい画像を確認し、現在の `active_route.id` を `expected_route_id` に指定します。新しい経路を検証した後、中立指令の応答を確認して交換します。追従器は進捗0で再開するため、新しい経路の始点は現在位置の近くに置きます。`stop` は画像IDなしで実行できます。

## 操作APIと制御方式

[API仕様](docs/protocol.md) を参照してください。速度m/s、旋回rad/s、位置m、ヨーradです。上位は点列・速度・先読み・許容逸脱範囲を選択し、下位が真値姿勢からv/wを計算します。点列は世界XY座標で、画面ピクセルではありません。元の先読み追従、旋回ヒステリシス、加減速定数、0.28m中心距離ガードを維持しています。経路登録時は0.30m以上の地図中心距離を要求します。

## 保存と評価

session内に `manifest.json`（コード・依存・外部ファイルハッシュ）、要求／展開設定、`logs/`（姿勢・指令・判断・停止・結果）、`observations/<試行>/`（JPEG・frames.jsonl）、`game-runs/`（ゲーム原記録）、`analysis/`（集計と比較）を保存します。インストール先や過去実験へ結果を書き込みません。

`analysis/comparison.md` は完走・衝突・転倒イベント・Wh・sim秒・周期・経路誤差・停止ACKを比較します。失敗を成功として扱わず、測定できない項目は未測定と記します。途中エラーも `*.failure.json` へ残ります。AI Playの集計を実験11固定再現試験と混ぜないでください。

## 制約

- MuJoCoの真値姿勢と標準コース情報を利用します。画像だけの認識、自律地図生成、未知環境の経路探索ではありません。
- 経路点と壁の距離はロボット中心の近似であり、全身の非接触保証ではありません。
- 約20Hzはwall時間基準です。CPU、OS、描画、I/Oで物理軌跡・消費量に差が出ます。
- JPEGと状態は非同期取得です。受信時刻差を記録しますが完全同期ではありません。同じJPEGを返し続ける描画故障を確実には識別できません。
- 通信断では中立送信を試行し、ACK失敗を記録します。通信が届かない場合の最終停止はゲーム既存の0.5秒入力期限に依存します。SIGKILL・電源断でのACK送信はできません。
- 終端中立とゲームの完走は異なります。ゴール内のstand・速度等を1秒保持するゲーム判定が完走を決めます。
- 消費量はゲームの23モータ推定モデルです。PC電力・実機電池計測ではありません。
- 別PC・Windows・macOS、完全なwheelハッシュlock、ブラウザごとの動画再生は未検証です。

本パッケージはApache-2.0で配布します。第三者の個別条件は [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) を参照してください。

## 二視点動画とAstra AI Play検証

観測候補の取得は約5fps、下位制御は約20Hzを維持し、試行終了後に50Hzのゲーム状態から30fpsの一人称・三人称を再描画できます。動画は1280×720 H.264 MP4。単純な観測画像の複製ではなく姿勢補間で生成し、全フレームの状態対応・PTS・重複・欠落・デコードを検証します。Astraが実際に開いた画像IDを別に記録し、再描画映像や未閲覧の観測JPEGと区別します。

[動画作成手順](docs/video-recording.md) と [Astra AI Play・動画検証レポート](docs/astra-ai-play-video-report.md) を参照してください。ソースcheckoutからAPIだけを使う場合は `tools/aiplay api --session SESSION ...` も利用できます。`--brief` は状態応答を短くし、原記録はそのまま保存します。
