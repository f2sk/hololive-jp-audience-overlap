# hololive-jp-audience-overlap

カバー・ホロライブプロダクション日本拠点35名のライブチャット投稿者IDに基づく
視聴者重複構造の定量分析。論文 [report_audience_paper_jp.pdf](reports_jp/report_audience_paper_jp.pdf) の
作成に用いたスクリプト・設定・集計済み派生データを公開する。

## 概要

YouTube公式チャンネルの登録者数は重複を含むため、複数タレントから構成される
グループの「実際のユニーク登録者数」は単純合算では把握できない。本研究では
分析期間中のサンプル件数を確保できた35名を対象に、ライブチャットリプレイから
抽出した投稿者YouTubeチャンネルIDを用いて、チャット参加者レベルでの視聴者
重複構造を推定し、その重複率を登録者数に外挿することでユニーク登録者数の
下限値を算出した。

主要な結果：

- 対象35名全体の推定ユニーク登録者数の下限 = **約 2,289万人**（合算 5,408万人の42.3%）
- 複推し数分布は1タレント単独60.9%を頂点とするべき乗則的減衰
- チャット参加率は活動年数と負の線形関係（Pearson r=-0.626）
- 期生別ユニット内ペア密度はゲーマーズが突出して高く、1期生が顕著に低い
- ぺこら×ヴィヴィ 15.66%（順位4位/595）が事務所横断ペアの最高位

詳細は論文本文を参照のこと。

## 公開ポリシー（個人情報保護）

本リポジトリは**生のチャット参加者個別ID（authorExternalChannelId）を含む
データを公開していない**。チャット投稿者IDは公開チャットから取得可能とはいえ、
個別単位での再配布は準個人情報の取扱いとして適切でないとの判断による。

公開しているのは以下のみ：

- 取得・分析パイプラインの全コード
- 配信単位の選定情報（video_id 単位、公開情報）
- 集計済み派生データ（個別IDを含まない統計値・図表）
- 論文本文と LaTeX/Quarto ソース

第三者が同じ分析を再現したい場合は、公開された video_id リストと
スクリプト群を用いて自前でチャットリプレイを取得し、同じパイプラインを
実行する必要がある（詳細は「再現手順」参照）。

## ディレクトリ構成

```
scripts_jp/        分析パイプライン（Python）
  scan_streams_jp.py     配信メタデータのスキャン
  step1_collect_urls_jp.py  除外規則の適用と10配信選定
  step2_fetch_chats_jp.py   チャットリプレイの取得
  step3_build_matrix_jp.py  バイナリ参加行列の構築
  step4_analyze_jp.py        基礎統計と UpSet Plot
  step5_fixed_fans_jp.py     固定ファン率分析
  step6_clustermap_jp.py     Jaccardクラスタマップ
  step7_extra_analysis_jp.py 上位ペア・複推し分布
  step8_age_analysis_jp.py   活動年数と参加率の相関
  step9_3d_analysis_jp.py    3次元相関とバブルチャート
  step10_linear_check_jp.py  リニア／対数フィット比較
  config_jp.py               メンバー定義（39名分のチャネルID、期生）

reports_jp/        論文と派生物
  report_audience_paper_jp.qmd   Quartoソース
  report_audience_paper_jp.pdf   論文PDF
  LICENSE                        CC-BY-4.0（論文用）

data/              公開対象データ（個別ID非含有）
  manual_exclude_jp.tsv       手動除外配信リスト（96件、video_id単位）
  jp_step1_selection_log.md   step1選定ログ
  scan_jp/                    配信メタデータ（video_id, title, upload_date）
  urls_jp/                    選定された配信URLリスト（タレント単位 .tsv）
  plots/jp/                   集計済み図表と統計サマリ

requirements.txt   依存ライブラリ
```

## 再現手順

### 環境

- Python 3.10+
- yt-dlp（pip install）
- 十分なディスク容量（チャットJSON取得時で数十GB程度）

```bash
python -m venv .venv
.venv/Scripts/activate    # Windows
# source .venv/bin/activate  # macOS / Linux
pip install -r requirements.txt
```

### パイプライン実行

```bash
# 1. 配信メタデータのスキャン（チャンネルあたり最大200本）
python scripts_jp/scan_streams_jp.py

# 2. 除外規則を適用して 10配信を選定
python scripts_jp/step1_collect_urls_jp.py

# 3. チャットリプレイを取得（期生単位の分割実行を推奨）
python scripts_jp/step2_fetch_chats_jp.py --gen all

# 4. バイナリ参加行列を構築
python scripts_jp/step3_build_matrix_jp.py

# 5. 各種分析・図表生成
python scripts_jp/step4_analyze_jp.py
python scripts_jp/step5_fixed_fans_jp.py
python scripts_jp/step6_clustermap_jp.py
python scripts_jp/step7_extra_analysis_jp.py
python scripts_jp/step8_age_analysis_jp.py
python scripts_jp/step9_3d_analysis_jp.py
python scripts_jp/step10_linear_check_jp.py

# 6. 論文ビルド（Quartoが必要）
cd reports_jp
quarto render report_audience_paper_jp.qmd --to pdf
```

### 再現性について

本リポジトリ公開のスクリプトを上記順で実行することで、本論文の分析パイプラインを
再構築できる。ただし以下に依存する：

- 対象 video_id のチャットリプレイが当該時点でYouTube上に公開されていること
- yt-dlp で取得可能な状態であること（メンバー限定・年齢制限・地域制限は取得不可）
- 登録者数（`data/plots/jp/subscribers_jp.tsv`）は yt-dlp 実行時点の値を取得するため、
  本論文の値（2026年5月25日時点スナップショット）から乖離し得る

**完全な数値一致は保証されないが、手法と統計推論の再現性は確保されている。**

## ライセンス

- **コード**（`scripts_jp/` および設定ファイル）: MIT License（[LICENSE](LICENSE)）
- **論文**（`reports_jp/` 内の .qmd, .pdf）: Creative Commons Attribution 4.0
  International（[reports_jp/LICENSE](reports_jp/LICENSE)）

## 引用

```
@f2sk (2026). チャット投稿者IDに基づくホロライブ日本拠点35名の
視聴者重複構造の推定. GitHub: hololive-jp-audience-overlap.
```

## 著者

@f2sk
