# 出典と再配布条件

確認日：2026-10-19。ゲーム・policy・モデル・フォント・外部ライブラリのバイナリを同梱していません。

- 移植元：実験11直下のcontroller/navigation.py（バイト同一）、display.py（フォント解決のみ変更）、controller.py/trial.py/batch.pyの制御・展開仕様。source-manifest.jsonに元ファイルSHA256を保存。original10は使用していません。独立成果物の配布ライセンスはLICENSEに確認状態を記載。
- ゲーム：Takeyuki-K/k1-mp-ecowalk-game、Apache-2.0。固定commit d1ef1562e463b5cfd0c97a8f24d1962b96c89357 のLICENSE、NOTICE、THIRD_PARTY_LICENSES.mdをローカルで確認。
- public：Takeyuki-K/k1-mp-ecowalk-public、固定commit 04b1c0fded94dcde76411e6bd9d914a56d41102a。コード・方策Apache-2.0。teleop：固定commit a5ea3dbf4f97501c18ff090f86ff4cd413f6aaea、Apache-2.0。
- モデル出典ROBOTIS-GIT/ai_sapiens：Apache-2.0、元NOTICE_MODIFICATIONSを保持。
- 歩行参照BMClab/BMC：非ソフトウェアCC BY 4.0、コードMIT。Marcos Duarte、Renato Naville Watanabe、DOI 10.5281/zenodo.4599319、変換内容の帰属を保持。
- CMU/BVH参照：CMU Graphics LabとB. HahneのREADMEFIRSTの利用条件・CMU/NSF EIA-0196217への謝辞を保持。Apacheへ一括変更しない。
- 実行依存：Pillow MIT-CMU、MuJoCo Apache-2.0、NumPy BSD-3-Clause、PyTorch BSD系と同梱コードの個別表示。各外部checkoutのLICENSE/NOTICEを削除しない。

[Apache-2.0公式本文](https://www.apache.org/licenses/LICENSE-2.0) §4に基づき、Apache対象を再配布する場合はライセンス本文、帰属・NOTICE、変更表示を保持する。ライブラリ、フォント、モデル、コンテナ等を追加同梱する場合は、実際に同梱する版の個別条件を改めて確認する。本一覧は推移的依存全件のSBOMではない。

外部依存の詳細な帰属の出典：[ゲーム固定版の第三者表示](https://github.com/Takeyuki-K/k1-mp-ecowalk-game/blob/d1ef1562e463b5cfd0c97a8f24d1962b96c89357/THIRD_PARTY_LICENSES.md)。本パッケージはROBOTIS公認を意味しない。
