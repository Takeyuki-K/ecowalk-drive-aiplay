# ecowalk-drive-aiplay

## 1. Overview — Astra × ecowalk-drive!!

`ecowalk-drive-aiplay`は、Astraが決めた経路をK1に追従させる、MuJoCoゲーム **ecowalk-drive!!** 用コントローラーです。Stage 1〜3の安全な完走と消費エネルギー（Wh）の低減を目指します。

環境構築、Codex用プロンプト、結果・動画の確認方法を掲載しています。ゲーム・歩行ポリシー・採点規則は変更しません。

## 2. Architecture — 上位AI・下位制御・歩行ポリシー

```text
Codex上のAstra
  一人称画像・標準上面マップ・MuJoCo自己位置・ゲーム状態を確認
  安全性と消費エネルギーを考慮し、経由点と走行パラメータを決定
       │ ローカルHTTP API（CLI経由）
       ▼
AI Playコントローラー
  自己位置と経路の誤差をフィードバックし、約20Hzで前進速度・旋回速度を更新
       │ ゲームの速度指令API
       ▼
K1の既存歩行ポリシー → MuJoCo内で歩行 → 状態・画像・公式Whを記録
```

Astraが経路と速度を決め、下位コントローラーが約20Hzで追従します。Astraの推論中も追従・安全監視は継続します。

参考実行では開始前に経路を1回登録し、再計画せず完走しました。自己位置はMuJoCoの真値を使用し、実機での自律走行は未検証です。

## 3. Requirements — 動作環境

| 項目 | 条件・動作確認範囲 |
|---|---|
| OS | Ubuntu 22.04.5 LTS / Linux x86_64で走行・動画生成を確認。以下はUbuntu 22.04向けBash手順 |
| Python | パッケージ定義は3.10以上。参考実行は3.10.12。以下は`python3.10`を使用 |
| 描画 | Mesa/OpenGL・EGLが必要。AI Playの`serve`は`MUJOCO_GL=egl`を指定してゲームを起動 |
| Pythonライブラリ | ゲーム用：MuJoCo 3.15.0、NumPy 2.2.6、Torch 2.14.1+cpu、Pillow 12.3.0、GLFW 2.10.2、PyOpenGL 3.1.10。コントローラーの必須追加依存はPillow 12.3.0 |
| 動画 | `libx264`と`-fps_mode`を利用できるFFmpeg。参考実行は7.0.2。以下では専用venvの`imageio-ffmpeg`から実行ファイルを取得 |
| Codex | 端末コマンド実行とローカル画像閲覧ができるCodex環境、認証済みアカウント、`gpt-6-astra`へのアクセス |
| その他 | Git、依存ダウンロード用ネットワーク、ローカルTCPポート8128・8129、状態記録と6本の動画を保存できる空き容量 |

ROSや追加学習は不要です。Windows・macOSでの動作は未検証です。

## 4. Installation — リポジトリと環境の準備

### 4.1 必要なリポジトリ

| 役割 | リポジトリ | 動作確認済みの版 |
|---|---|---|
| AI Playコントローラー | [ecowalk-drive-aiplay](https://github.com/Takeyuki-K/ecowalk-drive-aiplay) | 0.2.0 / `9506aed572c12fa5fa56a5e76cb14bf6398a186b`の実装 |
| ecowalk-drive!!（ゲーム） | [k1-mp-ecowalk-game](https://github.com/Takeyuki-K/k1-mp-ecowalk-game) | `1a4e9e747d8c71e5200c7badf91944c090a6883d` |
| K1歩行ポリシー | [k1-mp-ecowalk-public](https://github.com/Takeyuki-K/k1-mp-ecowalk-public) | `04b1c0fded94dcde76411e6bd9d914a56d41102a` / v5.6.3 |

**ecowalk-drive!!** は [k1-mp-ecowalk-teleop](https://github.com/Takeyuki-K/k1-mp-ecowalk-teleop)（`a5ea3dbf4f97501c18ff090f86ff4cd413f6aaea`）も使用します。歩行ポリシーとteleopは `k1-mp-ecowalk-game/vendor/` に配置します。

ゲームの著者名匿名化に伴う履歴書き換えにより、固定コミットを更新しました。新旧コミットのファイル内容（Git Tree）は同一です。過去の実験・環境記録に残る旧SHAは実行当時の値として保持しています。[新旧SHAの対応と検証記録](docs/game-commit-migration.md)を参照してください。

Privateリポジトリの取得にはGitHubのアクセス権が必要です。ライセンスは権利者確認中のため、`LICENSE`と`THIRD_PARTY_NOTICES.md`を確認してください。

### 4.2 新しい作業ディレクトリに取得する

**新しい作業ディレクトリ**で以下を順に実行してください。既存の仮想環境は変更しません。

```bash
sudo apt update
sudo apt install git curl python3.10-venv libgl1-mesa-dri libegl1 libosmesa6 fonts-dejavu-core

mkdir ecowalk-workspace
cd ecowalk-workspace
export ECOWALK_WORKSPACE="$PWD"
export PYTHONNOUSERSITE=1
unset PYTHONPATH PYTHONHOME

git clone https://github.com/Takeyuki-K/ecowalk-drive-aiplay.git
git clone https://github.com/Takeyuki-K/k1-mp-ecowalk-game.git
git -C k1-mp-ecowalk-game checkout --detach 1a4e9e747d8c71e5200c7badf91944c090a6883d

mkdir -p k1-mp-ecowalk-game/vendor
git clone https://github.com/Takeyuki-K/k1-mp-ecowalk-public.git k1-mp-ecowalk-game/vendor/k1-mp-ecowalk-public
git -C k1-mp-ecowalk-game/vendor/k1-mp-ecowalk-public checkout --detach 04b1c0fded94dcde76411e6bd9d914a56d41102a
git clone https://github.com/Takeyuki-K/k1-mp-ecowalk-teleop.git k1-mp-ecowalk-game/vendor/k1-mp-ecowalk-teleop
git -C k1-mp-ecowalk-game/vendor/k1-mp-ecowalk-teleop checkout --detach a5ea3dbf4f97501c18ff090f86ff4cd413f6aaea
```

動作確認済みのコントローラーはv0.2.0です。取得した版は `git -C ecowalk-drive-aiplay rev-parse HEAD` で確認できます。

`serve`はゲームとvendorの固定コミット・変更なし状態を検査します。歩行用の重みとMuJoCoモデルは取得済みリポジトリに含まれます。

### 4.3 2つのvenvを作成する

動作確認済みの依存関係を、ゲーム用とコントローラー用の別々のvenvに導入します。歩行ポリシーの学習用 `requirements.txt` は一括導入しません。

```bash
export GAME_ROOT="$ECOWALK_WORKSPACE/k1-mp-ecowalk-game"
export AIPLAY_ROOT="$ECOWALK_WORKSPACE/ecowalk-drive-aiplay"

python3.10 -m venv "$GAME_ROOT/.venv"
export GAME_PYTHON="$GAME_ROOT/.venv/bin/python"
"$GAME_PYTHON" -m pip install --upgrade pip
"$GAME_PYTHON" -m pip install setuptools==79.0.1 packaging==25.0 wheel==0.45.1
"$GAME_PYTHON" -m pip install torch==2.14.1 --index-url https://download.pytorch.org/whl/cpu
"$GAME_PYTHON" -m pip install mujoco==3.15.0 numpy==2.2.6 Pillow==12.3.0 glfw==2.10.2 PyOpenGL==3.1.10
"$GAME_PYTHON" -m pip install -e "$GAME_ROOT"

python3.10 -m venv "$AIPLAY_ROOT/.venv"
"$AIPLAY_ROOT/.venv/bin/python" -m pip install --upgrade pip
"$AIPLAY_ROOT/.venv/bin/python" -m pip install setuptools==79.0.1 packaging==25.0 wheel==0.45.1
"$AIPLAY_ROOT/.venv/bin/python" -m pip install "$AIPLAY_ROOT" imageio-ffmpeg==0.6.0

"$GAME_PYTHON" -m pip check
"$AIPLAY_ROOT/.venv/bin/python" -m pip check
"$AIPLAY_ROOT/.venv/bin/ecowalk-aiplay" --help
"$GAME_ROOT/.venv/bin/k1-game" --help
```

依存関係のインストールはここで完了です。実行プロンプトでは追加インストールを行いません。

### 4.4 パスを保存し、FFmpegを確認する

```bash
cat > "$ECOWALK_WORKSPACE/ecowalk-env.sh" <<'EOF'
export ECOWALK_WORKSPACE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export AIPLAY_ROOT="$ECOWALK_WORKSPACE/ecowalk-drive-aiplay"
export GAME_ROOT="$ECOWALK_WORKSPACE/k1-mp-ecowalk-game"
export GAME_PYTHON="$GAME_ROOT/.venv/bin/python"
export CLI="$AIPLAY_ROOT/.venv/bin/ecowalk-aiplay"
export OUTPUT="$ECOWALK_WORKSPACE/outputs"
export PYTHONNOUSERSITE=1
export PYTHONDONTWRITEBYTECODE=1
unset PYTHONPATH PYTHONHOME
export FFMPEG="$("$AIPLAY_ROOT/.venv/bin/python" -c 'import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())')"
EOF
source "$ECOWALK_WORKSPACE/ecowalk-env.sh"
mkdir -p "$OUTPUT"
"$FFMPEG" -version
"$FFMPEG" -hide_banner -loglevel error -f lavfi \
  -i 'color=c=black:s=32x32:r=30:d=0.1' \
  -c:v libx264 -fps_mode passthrough -f null -
```

FFmpegの動作確認が成功すれば準備完了です。既存のFFmpegを使う場合は `FFMPEG` に絶対パスを設定してください。

## 5. Quick Start — 起動確認とCodexの準備

### 5.1 ゲームとコントローラーの起動確認

ターミナルAで、作業ディレクトリから実行します。

```bash
source ./ecowalk-env.sh
SESSION="$("$CLI" init --output "$OUTPUT/smoke")"
printf '%s\n' "$SESSION" > "$OUTPUT/smoke-session.txt"
"$CLI" serve --session "$SESSION" --game-root "$GAME_ROOT" --game-python "$GAME_PYTHON"
```

`serve`が **ecowalk-drive!!** を起動します。起動情報が表示されたら、別のターミナルで次を実行してください。

```bash
source ./ecowalk-env.sh
SESSION="$(cat "$OUTPUT/smoke-session.txt")"
"$CLI" api --session "$SESSION" snap
"$CLI" api --session "$SESSION" shutdown
```

開始前の `snap` が `active: null` でも正常です。AI Play中はブラウザから操作しないでください。

起動できない場合は `SESSION/logs/game.log` を確認してください。ポート変更は `configs/runtime.example.json` と `init --config` で設定します。

### 5.2 Astraを選択してCodexを起動する

未導入の場合は[OpenAI公式のCodex CLI導入手順](https://learn.chatgpt.com/docs/codex/cli)に従ってインストールします。認証とモデル指定は[CLIリファレンス](https://learn.chatgpt.com/docs/cli/reference)、Astraの識別子と利用条件は[公式モデル案内](https://learn.chatgpt.com/docs/models)を参照してください。

```bash
# 未導入の場合のみ、公式インストーラーを実行
curl -fsSL https://chatgpt.com/codex/install.sh | sh
# インストーラーがPATHの再読み込みを案内した場合は、それを済ませてから続行
codex --version
codex login
codex login status
source ./ecowalk-env.sh
codex -C "$ECOWALK_WORKSPACE" -m gpt-6-astra
```

Codexで `gpt-6-astra` を選択し、次のプロンプトを入力します。Astraが利用できない場合は、別モデルの結果と区別してください。

Codexにはローカルの実行・画像閲覧・結果保存権限が必要です。対応環境では `--approve-for-me` を利用できます（詳細は `codex --help`）。

## 6. AI Play Prompt — Codexに貼り付ける実行プロンプト

以下をCodexに貼り付けます。画像はファイル名だけでなく、画像閲覧ツールで実際に開いてください。

```text
この作業ディレクトリにはecowalk-drive!!（k1-mp-ecowalk-game）、K1歩行ポリシー、ecowalk-drive-aiplayが準備済みです。
READMEのAI Play手順に従い、GPT-6 Astraを上位の経路判断AIとしてStage 1、2、3を順番に各1回だけ実行してください。

準備：
- ecowalk-drive-aiplay/README.mdを読み、端末で source ./ecowalk-env.sh を実行してください。
  CLI、AIPLAY_ROOT、GAME_ROOT、GAME_PYTHON、OUTPUT、FFMPEGの実パスと存在を確認してください。
  別のシェル実行枠では環境変数の継承を仮定せず、必要なら再度sourceしてください。
- 実行モデルがgpt-6-astraであることを利用可能な実行情報で確認し、確認方法を記録してください。
  未確認なら未確認とし、利用不可なら開始せず報告してください。
- 端末実行と画像の実閲覧ができること、ゲーム・vendorが固定版でcleanであることを確認してください。
- これはAI Playです。reproduceコマンドや保存済みの固定経路JSONの再送信は使わないでください。

各Stageの実行：
1. "$CLI" init --output "$OUTPUT/energy-aware" で新規SESSIONを作り、そのパスを保存してください。
2. "$CLI" serve --session "$SESSION" --game-root "$GAME_ROOT" --game-python "$GAME_PYTHON"
   を継続実行できる端末枠で起動してください。serveの終了を待ってから操作するのではなく、
   別の端末実行枠からAPIを操作してください。
3. Stage 1は以下で開始します。Stage 2・3ではstageとnameをそれぞれ変更してください。
   "$CLI" api --session "$SESSION" start --json '{"stage":1,"name":"energy_s1_01"}'
   "$CLI" api --session "$SESSION" snap
4. 初期画像が取得できたら速やかにsource_imageを実際に開いてください。
   合成画像内の一人称画像と標準上面マップを見て、stateの自己位置、ゴール、障害物情報も確認してください。
   画像未取得の場合は短い間隔でsnapを再取得し、取得失敗が続く場合は安全に終了して記録してください。
5. 安全な世界XY座標の経由点、速度、lookahead、corridor、終端の減速・停止方法を判断してください。
   優先順位は完走、無衝突・無転倒、公式総Wh削減、所要時間、追従安定性です。
   Stage 1は直線を中心に、Stage 2は障害物回避と少ない進路変更、Stage 3はS字通路に沿う滑らかな経路を重視してください。
   低速ほど省エネとは仮定せず、速度を単純に最大化せず、旋回・加減速・待機・終端停止も考慮してください。
6. SESSION/astra/を作り、decision.jsonに判断理由を含むroute要求を保存してください。
   必須項目はseen（実閲覧image_id）、note、points、speedです。
   image_use="model_viewed"、model_identity、lookahead、corridor、lease、expected_route_idも記録してください。
   pointsは[[x,y],...]形式のm単位の世界座標で2点以上。初回のexpected_route_idはnullです。
   speedは0.001〜1.5 m/s、lookaheadは0.05〜5 m、corridorは0.01〜5 m、leaseは0.001〜180秒です。
   leaseはwall時間です。安全な値を選び、既存の終端減速・中立化に任せてゴール範囲内で停止できる終点を選んでください。
   "$CLI" api --session "$SESSION" route --file "$SESSION/astra/decision.json" で送信してください。
7. 経路追従と約20Hzの速度指令更新は既存navigation.pyに任せてください。
   推論中もserveを動かし続け、必要に応じsnapで画像・進行を確認してください。
   実際に見た画像ID・閲覧回数・判断をSESSION/astra/へ保存してください。
   閲覧判断は試行中にobserve APIへseenとnoteを渡して記録できます。
   安定して追従している場合、不要な経路再登録・停止はしないでください。
   安全上必要な経路変更時だけ、新たな画像と現在位置から判断し、観測済みactive_route.idをexpected_route_idに指定してください。
   危険時は画像IDなしでもstopを呼べます。失敗時は理由を残し、勝手に再試行しないでください。
8. snapのstate.result.outcomeがfinishedになったことを確認してください。
   navigationのgoal_neutralだけでは完走ではありません。ゴール内の停止保持判定を待ってください。
   "$CLI" api --session "$SESSION" stop
   "$CLI" api --session "$SESSION" end
   endのstop.acknowledgedと保存結果を確認し、続いて以下で正常終了してください。
   "$CLI" api --session "$SESSION" shutdown
   通信失敗・中立ACK失敗は隠さず記録してください。
9. ゲーム終了後に、READMEのOutputsのvideoコマンドを実行してください。
   TRIALはenergy_s1_01、energy_s2_01、energy_s3_01の対応する名前です。
   一人称と後方三人称を1280×720・30fps・H.264 MP4で生成してください。
   --action-onlyで走行開始約1秒前から終了までとし、公式Whの集計区間は変えないでください。
   validation.jsonで全デコード、フレーム数、欠落、時刻、連続重複を確認してください。
   両視点のcontact-sheetと必要なフレームを開き、前方の見え方、三人称でのロボットの視認性・カメラの揺れも確認してください。
   検証後に次のStageへ進んでください。動画再描画は走行中に行わないでください。

エネルギー評価と報告：
- 各Stageについて完走、衝突回数、転倒回数、最初の非中立指令までのsim秒とwall秒を記録してください。
- 「動き出す」は実際の身体の動きの検出ではなく、最初のvまたはwが非ゼロの指令として集計してください。
- READMEのOutputsの定義で、待機と停止判定を含む公式総Whと、走行開始後の参考Whを分けて算出してください。
  ログが欠けて計算できない項目は推測せず未測定としてください。
- 3ステージをMarkdown表にまとめ、判断理由、モデル確認情報、実閲覧数、停止ACK、動画保存先、品質検証結果も報告してください。
  OUTPUT/energy-aware/内の新しい名前のMarkdownファイルに保存し、全sessionのパスを列挙してください。
- 失敗も含めて全試行を報告してください。各Stage1回なので統計的な優劣は断定しないでください。

制約：
- 既存のnavigation.pyと学習済み歩行ポリシーを使用し、Astraから関節角やトルクを直接指令しないでください。
- ゲーム、モデル、歩行ポリシー、制御ロジック、採点、エネルギー計算を変更しないでください。
- ゲームを一時停止して待機消費を除外しないでください。
- 不要なツール承認待ちを減らしつつ、安全確認・権限確認を省略しないでください。
- 追加インストール、既存環境・過去データの変更、ソースコードの改造、commit・push、外部アップロードは禁止です。
  権限や依存不足で実行できない場合は、原因と未実施範囲を報告してください。
```

## 7. Reference Results — Energy-Aware AI Play

2026年10月20日の参考結果です（Astraによる経路判断、各ステージ1回）。

| Stage | Initial wait (sim s) | Initial wait (wall s) | Energy after motion start (Wh) | Total energy (Wh) |
|---|---:|---:|---:|---:|
| Stage 1 | 14.76 | 16.758 | 0.850726 | 0.879600 |
| Stage 2 | 18.04 | 20.123 | 0.848088 | 0.881875 |
| Stage 3 | 13.24 | 15.273 | 1.301375 | 1.327971 |
| Total | 46.04 | 51.154 | 3.000189 | 3.089446 |

全3ステージ完走、衝突・転倒0回。一人称・三人称の30fps動画を生成しました。

Initial waitは最初の移動指令までの時間（wall秒は初期化・推論等を含む）、Total energyは待機・停止判定を含むゲーム公式Whです。Energy after motion startは待機分を除いた参考値です。消費エネルギーはシミュレーション上の推定値であり、結果の一致は保証しません。

## 8. Outputs — 動画・ログ・Whの確認

### 8.1 保存場所

結果はStageごとに `outputs/energy-aware/<session ID>/` に保存されます。

| SESSIONからの相対パス | 内容 |
|---|---|
| `observations/<TRIAL>/result.json` | 試行の確定記録、公式結果、開始wall時刻、転倒回数、中立ACK |
| `game-runs/<run_id>/result.json` | ゲームが保存した公式結果。`energy_wh`、`elapsed_s`、`outcome`、`collisions` |
| `game-runs/<run_id>/states.jsonl` | 約50Hzの物理状態、累積Wh、指令。動画の再描画元 |
| `logs/controls.jsonl` | 下位制御の指令、sim時刻、wall時刻、追従誤差 |
| `logs/decisions.jsonl` / `logs/events.jsonl` / `logs/results.jsonl` | 上位判断・参照画像ID、安全停止、結果の記録 |
| `observations/<TRIAL>/` | 観測JPEGと`frames.jsonl`。自動保存された画像すべてをAstraが見たとは限らない |
| `astra/` | プロンプトに従ってAstraが保存する判断JSON、実閲覧記録。CLIの自動生成物ではない |
| `video/<TRIAL>/first.mp4` / `third.mp4` | 一人称・後方追従の三人称動画 |
| `video/<TRIAL>/validation.json` / `*.validation.json` | 自動動画検証結果、カメラ変動の数値 |
| `video/<TRIAL>/*.contact-sheet.jpg` / `*.frame_map.jsonl` | 目視用サンプル一覧、動画時刻と元状態の対応 |
| `manifest.json` / `environment-game.json` / `runtime.json` | 実行コード・外部依存・Python環境・設定 |

### 8.2 二視点動画を生成する

終了後、対象の `SESSION` と `TRIAL` を指定して動画を生成します。

```bash
# SESSIONには対象Stageのsessionパスが設定済みであること
TRIAL=energy_s1_01
MUJOCO_GL=egl PYTHONPATH="$AIPLAY_ROOT/src" \
  "$GAME_PYTHON" -m ecowalk_drive_aiplay.cli video \
  --session "$SESSION" --trial "$TRIAL" \
  --game-root "$GAME_ROOT" --ffmpeg "$FFMPEG" --action-only
```

動画生成には **ゲーム用Python** を使います。再生成時は `--output` で別の保存先を指定してください。

保存した50Hzの状態から、一人称・後方三人称の30fps H.264 MP4（1280×720）を生成します。`--action-only` は動画区間だけを短縮し、公式Whには影響しません。

動画生成後は `validation.json` とcontact-sheetで、フレーム欠落・黒画面・見え方を確認してください。

### 8.3 待機時間とWhの集計定義

4指標の集計は専用コマンドではなく、Codexが保存ログから計算します。

1. `logs/controls.jsonl`で対象`name`の行を選び、`command.v != 0`または`command.w != 0`となる最初の行を取得します。
2. **Initial wait (sim s)**：その行の`sim_t`。ゲームのsim時刻は開始時に0へ戻ります。
3. **Initial wait (wall s)**：その行の`command_wall`から、`observations/<TRIAL>/result.json`の`start_wall`を引きます。`start_wall`はコントローラーがゲーム開始要求を送る直前の時刻で、サーバー起動前のセットアップ時間は含みません。
4. **Total energy**：確定記録の`result.energy_wh`。対応する`game-runs/<run_id>/result.json`の`energy_wh`と一致することを確認します。
5. **Energy after motion start**：`states.jsonl`から最初の指令の`sim_t`より前の最後の行を選び、その`result.energy_wh`を公式総Whから引きます。状態サンプルを用いた参考値で、公式得点とは別です。

完走・衝突・転倒は結果ログで確認し、欠損値は推測せず「未測定」としてください。

## 9. Limitations — 現状の制約と確認範囲

- MuJoCoの真値姿勢と標準コース情報を利用します。未知環境の地図作成、画像だけの位置推定、実機での自律走行は実証していません。
- 経路登録時はロボット中心と障害物・壁の距離を検査します。全身の非接触を幾何学的に保証するものではありません。
- 約20Hzはwall時間基準です。CPU負荷、描画、I/O、推論待ちで軌跡や総Whが変わります。画像と状態も非同期取得です。
- 安全ガードによる停止後に、下位コントローラーが自動で新しい回避経路を作ることはありません。経路交換時には中立化して追従状態を初期化します。
- 通信断では中立送信を試みますが、ACKを保証できません。指令が届かない場合はゲーム既存の入力期限による停止に依存します。
- 動画は保存状態のオフライン可視化です。Astraが走行中に見た画像列やwall時間の画面録画ではありません。
- 固定版での3ステージ走行と二視点動画生成は確認済みです。このガイドのCLI引数・依存定義・保存形式は実装と照合しています。README改訂時には、隔離venvへのコントローラー導入、FFmpeg取得とH.264対応確認、既存ゲーム環境を使う`serve → snap → shutdown`も確認しました。
- 別PCでのゲーム用依存の一括取得、OSパッケージ・EGL環境・Codexの新規導入、この掲載プロンプトによる3ステージの再実行、すべての端末・ブラウザでのMP4再生は、README改訂時には検証していません。
