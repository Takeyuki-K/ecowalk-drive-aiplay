# 実装・再現性検証レポート

この文書は初版の固定再現検証時点の記録です。同日後続のAI Play・二視点動画実装と追加検証は [Astra AI Play・二視点動画検証](astra-ai-play-video-report.md) を参照してください。以下の「未実装・未検証」は初版時点の状態を示します。

検証日：2026-10-19。実験11直下の実使用コードから移植し、同じPCの既存ゲーム環境でStage1〜3各3回を実走した。**9/9完走、衝突0、転倒0、終了中立ACK 9/9**。別PCやAstraによる新規攻略の成功は未確認。

## 実装済み

- install可能なPythonパッケージとCLI。server / game_client / recording / trial / batch / config / provenance / analysisを分離。importでサーバーは起動しない。
- Reproduction：固定JSON、Stage3の展開規則、展開済み9経路、地図照合、各Stage3回、自動比較レポート。Astra不要。
- AI Play：実ゲームJPEG＋上面地図＋真値姿勢＋状態、画像ID・ハッシュ・各取得時刻、上位判断・理由・指令の保存。route / observe / camera / stop / end / shutdown。
- 単一runtime.jsonでゲーム／制御ポート統一。試行ごとの全追従状態初期化。独立session、既存試行名拒否。
- 終了・経路交換時のlock内中立送信とACK記録、HTTPサーバー終了、所有ゲームプロセス終了。交換前に完全検証し、旧経路の送信との競合を防止。
- 通信タイムアウト、有限の起動／画像待ち／試行期限、不正経路・NaN・無限大・全重複点・壁への近接等の拒否。画像受信監視、sim時刻停滞監視。
- 日本語README、共通プロンプト、操作プロトコル、JSON Schema、ライセンス確認記録。プロンプトは環境変更・ゲーム／政策編集を禁止する。

ディレクトリは移植計画に沿った。設定はPython3.10標準ライブラリだけで読めるJSONを採用し、提案のruntime.example.tomlはruntime.example.jsonに変更した。任意の動画・グラフ生成機能は同梱していない。

## 通常追従の一致と周辺修正

`navigation.py` は原本とバイト同一。SHA256：`f07499a1d0eced5f0d4baac6a9a7fd13c4778247a15b069fd8677a93f1c37d55`。

保存済み25試行から14,417姿勢サンプルを取り出し、新旧Followerへ同じ姿勢・前回指令・dt・wall時刻を与えた。v/w、進捗、旋回状態、停止理由を含む出力・内部状態の不一致0、最大指令差0。tracking 14,392件、goal_neutral 25件。[比較結果](follower-comparison.json)。

参照expanded-routesでは元実行設定のseen絶対パスだけを除去した。点列・数値は維持し、原ファイルハッシュはsource-manifest.jsonで追跡する。

元ログはループ入口時刻を記録していないため、比較のdtにはstatus要求時刻差を両実装へ共通に与えた。この比較は新旧演算の一致であり、過去に送信した時系列をビット単位に再現したとの主張ではない。元ログに1件、終了競合でcontrolsのnameがnullになる箇所があり、追従なしの当該行を除外した。通常追従の14,417件は省略していない。

変更したのはライフサイクル・入力検証・通信・記録。時計は制御間隔／lease／反転待ちにmonotonicを使用し、監査にはUnix wall時刻も残す。画像と状態の非同期性を記録し、完全同期とは表示しない。終了時・経路交換時は即時中立ACK、異常時は期限付きで結果保存する。元の20Hz目標、先読み式、加減速、旋回ヒステリシス、0.28mガード、0.30m経路検査、固定パラメータは維持した。

## 固定9試行の結果

|Stage|完走|衝突/転倒|今回Wh 平均±標本SD|実験11 Wh|差|今回sim秒 / 元|今回平均Hz / 元|最大追従誤差m / 元|
|---|---:|---:|---:|---:|---:|---:|---:|---:|
|1|3/3|0/0|0.857204 ± 0.001141|0.855397|+0.211%|21.620 / 21.640|19.542 / 19.379|0.135000 / 0.110000|
|2|3/3|0/0|0.959974 ± 0.000688|0.959717|+0.027%|33.340 / 33.400|19.590 / 19.692|0.294920 / 0.286700|
|3|3/3|0/0|1.324584 ± 0.002709|1.324878|−0.022%|36.160 / 36.267|19.412 / 19.676|0.372679 / 0.378979|

全9件の保存結果とゲーム標準result.jsonが一致。各試行のmetadataも元実験の各Stageと一致（seed5、physics_dt=.005、policy、rules、地図、消費モデル等）。停止理由は全件goal_neutral、その後ゲームのfinishedを確認してtrial_end。転倒数はstatusのfalse→true遷移数で、全件0。

実走前の比較目安は完走・無衝突・無転倒・中立ACKを必須、Wh平均差±5%、sim時間平均差±10%、平均制御18〜22Hz。すべて満たした。統計的な一般保証や元3回のSD内での一致を意味しない。

平均指令間隔50.66〜51.74ms、p95 77.38〜82.51ms、全試行中の最大435.66ms。20Hzは目標であり、厳密な周期保証はない。初期描画のHTTP503が1件あり、その後回復。制御例外・失敗試行は0。6,210制御行・1,585観測フレームを保存した。

[各試行の詳細](reproduction-comparison.md)、[機械可読metrics](reproduction-metrics.json)、[判定](reproduction-assessment.json)。

## テスト

- 最新コードのオフライン15テスト成功。不正入力が旧経路を変更しないこと、9固定経路の展開、状態初期化、中立ACK、交換時の通信断、画像待ち期限、試行期限、継続通信断／不正statusの終了、ランナー割り込み時のstop/end、各ガードを確認。
- 実ローカルHTTPの1テスト成功。JSONエラー、未知endpoint、不正試行名、stop/end、shutdown後プロセス終了を確認。
- 実ゲームのAI Play APIスモークテストを別sessionで実施。走行中の不正経路拒否と旧経路維持、現在位置からの経路交換、中立ACK、camera/observe、stop/end/shutdownの6判定が成功。意図的にabortedで終了。これは完走試験でもAstraの画像判断試験でもない。画像参照はautomated_referenceとして記録した。
- wheelビルドとソースディレクトリ外への導入確認は [package-validation.json](package-validation.json) に記録。

固定9試行の実行時ソースハッシュはsession/manifest.jsonにある。その後、継続通信断・不正statusの終了処理、起動完了基準の画像待ち期限、失敗試行のCLI終了コードと割り込み時の停止、判定JSON、フォント来歴記録を補強した。通常追従の演算・固定経路は変更していない。補強部分は上記テストで確認し、固定9試行を追加でやり直したとは扱わない。

再実行用：

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
ECOWALK_HTTP_TESTS=1 PYTHONPATH=src python -m unittest discover -s tests -v
PYTHONPATH=src python tools/compare_followers.py --source /path/to/original-experiment11 --output /path/to/new-comparison.json
```

## 環境・保存・保全

本検証の保存先（リポジトリ外）：

- 固定再現：`../aiplay-validation/20261019T055045Z-0b64e47698/`
- 実API検証：`../aiplay-api-validation/20261019T060045Z-677a1ab290/`
- 起動失敗履歴：`../aiplay-validation/20261019T053234Z-9babfbf496/`（sandboxでソケット作成禁止）、`../aiplay-validation/20261019T053259Z-ff05646942/`（起動入口・venvパス解決の不備、修正済み）。これらは試走成功数に含めない。

今回と元実験のOS/PythonはLinux 6.8.0-138-generic x86_64、glibc2.35、Python3.10.12で一致。ゲームvenvに列挙された29配布物は元185件中の同名同バージョンと一致。元一覧のROS関連156件は今回の配布物一覧に現れない。ROSを使わない標準HTTPモードで試験した。MuJoCo3.15.0、NumPy2.2.6、Torch2.14.1+cpu、Pillow12.3.0は一致。

EGL・30fps・外部画像保存5fps・元Notoフォントを使用。nvidia-smiはこの環境に存在せず、GPUドライバ同一性は確認していない。libEGL/libGLX MesaとlibOSMesaが存在することを読み取り確認した。依存wheelハッシュ、OSグラフィックス全スタックの完全lockは未作成。

[環境比較](environment-comparison.json)。ゲーム・public・teleopは固定コミットでclean、実行前後の追跡ファイルSHA256も一致。実験11の9,757ファイルを全件SHA256比較し、追加0・削除0・変更0：[保全結果](source-preservation.json)。元ゲーム・政策・MuJoCoモデル・採点・既存実験成果物は編集していない。追加学習、commit、pushは行っていない。

## 未実装・未検証・残課題

- 別PCへの新規インストール、全依存wheelの取得とハッシュ固定、Windows/macOS対応は未検証。今回の結果を「どのPCでも再現」と扱わない。
- Astraが共通プロンプトを使って画像を実際に認識し、新しい経路を判断する一連の攻略は未検証。AI Play操作機能は実装・実ゲーム検証済み。モデルAPI呼出し機能は不要な設計とした。
- 動画生成、ブラウザ再生検査、Matplotlibグラフ、探索履歴UIは未移植。raw/合成JPEGとframe対応記録は保存する。
- JPEGの古い内容が再送される故障の完全検出、厳密20Hz、全身の衝突回避保証、画像のみの自己位置推定、大域経路探索は提供しない。
- 通信が届かない場合は中立ACK不可を明記し、ゲーム既存の0.5秒入力期限に依存する。SIGKILLや電源断は正常終了と扱わない。
- ライセンスは外部依存の条件を確認したが、実験11外部制御コード自身の明示的ライセンスが見つからなかった。権利者確認までパッケージ全体の配布ライセンスは未確定。ゲームのApache-2.0が自動的に適用されるとは扱わない。[LICENSE](../LICENSE)、[第三者表示](../THIRD_PARTY_NOTICES.md)。
