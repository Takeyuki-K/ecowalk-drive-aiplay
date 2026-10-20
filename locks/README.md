# 依存の固定範囲

controller-linux-py310.txt は直接依存Pillow 12.3.0を固定する。実験時Pythonは3.10.12。
ゲーム互換環境の観測済み全配布物はreference/experiment11/environment.json、今回実測はsession/environment-game.json。

これらはwheelハッシュ付きの完全なインストールlockではない。元一覧にはROSを含み、別PCで同一wheelが取得可能か未検証。Torch CPU版は元環境の2.14.1+cpuを使った。公開レジストリでの取得可否を推測してインストールコマンドを捏造しない。

数値集計は標準ライブラリのみ。二視点動画出力には準備済みゲーム環境のMuJoCo・NumPy等と外部FFmpegを使用する。実測バージョンと検証範囲は [動画検証レポート](../docs/astra-ai-play-video-report.md) を参照。動画用依存の完全なwheelハッシュlockは未作成で、Matplotlib解析は未移植。EGL・GPUドライバ・フォントはOS依存。起動時のフォントは指定→Noto CJK→DejaVu→Pillow組込の順で選択し、同梱しない。フォールバックでは日本語表示が欠ける場合がある。

参照環境一覧のeditable_project_locationは、配布時にローカル絶対パスを`<GAME_ROOT>`へ置換している。元の環境記録は実験11側に保持し、source-manifest.jsonのSHA256で追跡する。
