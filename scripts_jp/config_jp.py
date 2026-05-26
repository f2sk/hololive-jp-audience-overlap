"""
ホロライブJP全体分析 — メンバー設定と分析パラメータ

チャンネルIDはYouTubeチャンネルURLから取得し、検索結果で確認済み（2026/05/24）。
対象: 2026年5月初旬時点で活動中の37名（白上フブキは1期生・ゲーマーズ両所属）
除外: 卒業・契約解除済み（シオン、かなた、クロヱ等）、活動休止中（赤井はあと、虎金妃笑虎）
"""

from pathlib import Path as _Path

# --------------------------------------------------------------------------
# メンバー定義
# --------------------------------------------------------------------------
# units はリスト形式（白上フブキのような複数所属に対応）
# DEV_IS（ReGLOSS / FLOW GLOW）は既存チャットデータを流用する

MEMBERS_JP = {
    # ---- 0期生 ----
    "sora": {
        "name": "ときのそら",
        "units": ["0期生"],
        "channel_id": "UCp6993wxpyDPHUpavwDFqgg",
    },
    "roboco": {
        "name": "ロボ子さん",
        "units": ["0期生"],
        "channel_id": "UCDqI2jOz0weumE8s7paEk6g",
    },
    "azki": {
        "name": "AZKi",
        "units": ["0期生"],
        "channel_id": "UC0TXe_LYZ4scaW2XMyi5_kw",
    },
    "suisei": {
        "name": "星街すいせい",
        "units": ["0期生"],
        "channel_id": "UC5CwaMl1eIgY8h02uZw7u8A",
    },
    "miko": {
        "name": "さくらみこ",
        "units": ["0期生"],
        "channel_id": "UC-hM6YJuNYVAmUWxeIr9FeA",
    },

    # ---- 1期生 ----
    "fubuki": {
        "name": "白上フブキ",
        "units": ["1期生", "ゲーマーズ"],   # 両所属
        "channel_id": "UCdn5BQ06XqgXoAxIhbqw5Rg",
    },
    "matsuri": {
        "name": "夏色まつり",
        "units": ["1期生"],
        "channel_id": "UCQ0UDLQCjY0rmuxCDE38FGg",
    },
    "aki": {
        "name": "アキロゼ",
        "units": ["1期生"],
        "channel_id": "UCFTLzh12_nrtzqBPsTCqenA",
    },

    # ---- 2期生 ----
    "ayame": {
        "name": "百鬼あやめ",
        "units": ["2期生"],
        "channel_id": "UC7fk0CB07ly8oSl0aqKkqFg",
    },
    "choco": {
        "name": "癒月ちょこ",
        "units": ["2期生"],
        "channel_id": "UC1suqwovbL1kzsoaZgFZLKg",
    },
    "subaru": {
        "name": "大空スバル",
        "units": ["2期生"],
        "channel_id": "UCvzGlP9oQwU--Y0r9id_jnA",
    },

    # ---- ゲーマーズ ----
    # fubuki は 1期生 に既出。ゲーマーズ専属は以下3名
    "mio": {
        "name": "大神ミオ",
        "units": ["ゲーマーズ"],
        "channel_id": "UCp-5t9SrOQwXMU7iIjQfARg",
    },
    "okayu": {
        "name": "猫又おかゆ",
        "units": ["ゲーマーズ"],
        "channel_id": "UCvaTdHTWBGv3MKj3KVqJVCw",
    },
    "korone": {
        "name": "戌神ころね",
        "units": ["ゲーマーズ"],
        "channel_id": "UChAnqc_AY5_I3Px5dig3X1Q",
    },

    # ---- 3期生 ----
    "pekora": {
        "name": "兎田ぺこら",
        "units": ["3期生"],
        "channel_id": "UC1DCedRgGHBdm81E1llLhOQ",
    },
    "flare": {
        "name": "不知火フレア",
        "units": ["3期生"],
        "channel_id": "UCvInZx9h3jC2JzsIzoOebWg",
    },
    "noel": {
        "name": "白銀ノエル",
        "units": ["3期生"],
        "channel_id": "UCdyqAaZDKHXg4Ahi7VENThQ",
    },
    "marine": {
        "name": "宝鐘マリン",
        "units": ["3期生"],
        "channel_id": "UCCzUftO8KOVkV4wQG1vkUvg",
    },

    # ---- 4期生 ----
    "watame": {
        "name": "角巻わため",
        "units": ["4期生"],
        "channel_id": "UCqm3BQLlJfvkTsX_hvm0UmA",
    },
    "towa": {
        "name": "常闇トワ",
        "units": ["4期生"],
        "channel_id": "UC1uv2Oq6kNxgATlCiez59hw",
    },
    "luna": {
        "name": "姫森ルーナ",
        "units": ["4期生"],
        "channel_id": "UCa9Y57gfeY0Zro_noHRVrnw",
    },

    # ---- 5期生 ----
    "lamy": {
        "name": "雪花ラミィ",
        "units": ["5期生"],
        "channel_id": "UCFKOVgVbGmX65RxO3EtH3iw",
    },
    "nene": {
        "name": "桃鈴ねね",
        "units": ["5期生"],
        "channel_id": "UCAWSyEs_Io8MtpY3m-zqILA",
    },
    "botan": {
        "name": "獅白ぼたん",
        "units": ["5期生"],
        "channel_id": "UCUKD-uaobj9jiqB-VXt71mA",
    },
    "polka": {
        "name": "尾丸ポルカ",
        "units": ["5期生"],
        "channel_id": "UCK9V2B22uJYu3N7eR_BT9QA",
    },

    # ---- 6期生 (holoX) ----
    "laplus": {
        "name": "ラプラス・ダークネス",
        "units": ["6期生"],
        "channel_id": "UCENwRMx5Yh42zWpzURebzTw",
    },
    "lui": {
        "name": "鷹嶺ルイ",
        "units": ["6期生"],
        "channel_id": "UCs9_O1tRPMQTHQ-N_L6FU2g",
    },
    "koyori": {
        "name": "博衣こより",
        "units": ["6期生"],
        "channel_id": "UC6eWCld0KwmyHFbAqK3V-Rw",
    },
    "iroha": {
        "name": "風真いろは",
        "units": ["6期生"],
        "channel_id": "UC_vMYWcDjmfdpH6r4TTn1MQ",
    },

    # ---- DEV_IS: ReGLOSS ----
    "kanade": {
        "name": "音乃瀬奏",
        "units": ["ReGLOSS"],
        "channel_id": "UCWQtYtq9EOB4-I5P-3fh8lA",
    },
    "ririka": {
        "name": "一条莉々華",
        "units": ["ReGLOSS"],
        "channel_id": "UCtyWhCj3AqKh2dXctLkDtng",
    },
    "raden": {
        "name": "儒烏風亭らでん",
        "units": ["ReGLOSS"],
        "channel_id": "UCdXAk5MpyLD8594lm_OvtGQ",
    },
    "hajime": {
        "name": "轟はじめ",
        "units": ["ReGLOSS"],
        "channel_id": "UC1iA6_NT4mtAcIII6ygrvCw",
    },

    # ---- DEV_IS: FLOW GLOW ----
    "riona": {
        "name": "響咲リオナ",
        "units": ["FLOW GLOW"],
        "channel_id": "UC9LSiN9hXI55svYEBrrK-tw",
    },
    "su": {
        "name": "水宮枢",
        "units": ["FLOW GLOW"],
        "channel_id": "UCjk2nKmHzgH5Xy-C5qYRd5A",
    },
    "chihaya": {
        "name": "輪堂千速",
        "units": ["FLOW GLOW"],
        "channel_id": "UCKMWFR6lAstLa7Vbf5dH7ig",
    },
    "vivi": {
        "name": "綺々羅々ヴィヴィ",
        "units": ["FLOW GLOW"],
        "channel_id": "UCGzTVXqMQHa4AgJVJIVvtDQ",
    },
    "niko": {
        "name": "虎金妃笑虎",
        "units": ["FLOW GLOW"],
        "channel_id": "UCuI_opAVX6qbxZY-a-AxFuQ",
    },
}

# --------------------------------------------------------------------------
# 分析期間
# --------------------------------------------------------------------------
# 全タレントの上限を博衣こよりの活動休止前（2026-05-10以前）に統一
DATE_START = "20260101"   # 4ヶ月程度を遡れる安全値
DATE_END   = "20260510"   # こよりの休止前最終配信日（ユーザー確認済み）

# --------------------------------------------------------------------------
# グループ配色（clustermap ラベル色分け用）
# --------------------------------------------------------------------------
UNIT_COLOR = {
    "0期生":    "#E91E8C",  # ピンク
    "1期生":    "#FF9800",  # オレンジ
    "2期生":    "#4CAF50",  # グリーン
    "ゲーマーズ": "#00BCD4", # シアン
    "3期生":    "#FF5722",  # ディープオレンジ
    "4期生":    "#9C27B0",  # パープル
    "5期生":    "#2196F3",  # ブルー
    "6期生":    "#795548",  # ブラウン
    "ReGLOSS":   "#c0392b", # レッド（DEV_IS既存色）
    "FLOW GLOW": "#1a6fa8", # ネイビーブルー（DEV_IS既存色）
}

# --------------------------------------------------------------------------
# データディレクトリ（絶対パス）
# --------------------------------------------------------------------------
DATA_DIR    = str(_Path(__file__).parent.parent / "data")
DATA_DIR_JP = str(_Path(__file__).parent.parent / "data" / "plots" / "jp")
