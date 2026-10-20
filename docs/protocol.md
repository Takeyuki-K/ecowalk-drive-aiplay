# ローカル操作プロトコル v1

ゲームAPIはruntime.jsonのgame_url、上位APIはcontroller_url。既定127.0.0.1:8128/8129。遠隔公開用の認証・TLSは実装しない。全POSTはJSON object、最大128KiB。NaN/Infinity、未知endpoint、不正入力はHTTP400 JSON error。異なるOriginのブラウザからは403。

`ecowalk-aiplay api --session SESSION ACTION --json JSON` または `--file FILE`。POST応答は通常snapshot、endは確定記録、shutdownはstopped。GET /statusもsnapshot。

|Endpoint|必須入力|動作|
|---|---|---|
|/start|stage:1〜3、name:英数_-の1〜80字|新規試行、カメラfirst/yaw0/pitch-16、全内部状態初期化。既存名拒否|
|/snap|{}|最新画像情報と最新stateを返す。画像未取得時にはimage_idなし|
|/route|seen、note、points、speed|入力検証後に追従開始。lookahead=1、corridor=.7、lease=120既定|
|/observe|seen、note|実際の観測に対する判断を記録|
|/camera|seen、note、yaw/pitchの一方以上推奨|firstカメラのyaw(-90..90度)、pitch(-65..45度)を設定|
|/stop|{}（seen/noteも指定可）|lock内で中立送信しACK記録。画像なしの緊急停止可|
|/end|{}|中立ACKを記録。playingならabortして原結果を保存。通信失敗はerrorとACK false|
|/shutdown|{}|activeをendし、中立送信後HTTPサーバー・所有ゲームプロセス終了|

snapshotのトップレベルは**画像取得時の**course/sim/result、`state`は**直近status取得時の**状態。ゲーム終了判断にはstate.resultを利用する。`source_image`は合成画像、`raw_image`はJPEG原画像、`image_id`は試行名:連番。`navigation`は最新追従状態。`last_stop`は最後の中立送信結果、`active_route`はid/progress/total。

観測時刻は `status_request_wall / state_received_wall / image_request_wall / image_received_wall / state_image_gap_s`。wallはUnix秒、monotonicはプロセス内の経過時刻。sim.tはゲーム時間。JPEGの受信時刻はレンダリング時刻ではない。同一瞬間の状態・画素とは扱わない。JPEG SHA256も保存する。

`seen`は現試行で保存済みのimage_idのみ受理する。保存記録はモデルが実際に開いたことを自動証明しない。上位が正しく申告し、画像閲覧のツール履歴と対応させる。image_use=model_viewed/automated_reference、model_identityは確認できた情報のみ。固定ランナーはautomated_reference。

点列は[[x,y],...]、2〜2048点、地図bounds内、総延長500m以下、重複点だけは不可。途中の重複点は元navigation同様にスキップする。speed:0.001〜1.5m/s、lookahead:.05〜5m、corridor:.01〜5m、lease:.001〜180秒。未知routeキー拒否。

tuning任意：corner_floor(.01..1)、corner_divisor(.01..1000)、slow_distance(.01..20)、end_base(0..1.5)、end_gain(0..5)。実験11では固定JSONを変更しない。tuningは追従器の既存オプションだけを露出する。

経路登録前に5cm刻みで中心距離0.30m以上を検査する。追従中の中心距離0.28m、逸脱、衝突増加、転倒、1.2秒の画像受信停止、2秒のsim時間停止、lease期限、terminalで中立化する。閾値は元実験を維持（sim時間停止監視は移植時に追加）。ガード後は自動で別経路を生成しない。

新経路を選ぶ際はexpected_route_idを観測済みIDにする（初回null）。現在IDと違えば拒否。入力不正は旧経路を変更しない。有効な交換はlockで古い制御送信を遮断し、中立ACK後に新Followerを適用する。ACK失敗なら旧経路も停止し、新経路は有効にならない。交換時は速度・進捗・旋回ヒステリシスを初期化する。

end/shutdownがHTTP200でも停止ACKは必ず確認する。通信が失われた場合は中立ACKを保証できず、ゲームの0.5秒入力期限に依存する。結果保存を完走と解釈しない。経路終端のgoal_neutralは途中状態であり、ゲームがfinishedを返すまで中立を続ける。
