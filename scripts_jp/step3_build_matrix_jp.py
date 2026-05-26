"""
バイナリマトリックス構築スクリプト（ホロライブJP全体版）

チャットログ (.live_chat.json) から authorExternalChannelId を抽出し、
ユーザー × タレントのバイナリマトリックスを Parquet で保存する。

実行方法:
    python scripts_jp/step3_build_matrix_jp.py

出力:
    data/matrix_jp.parquet  - 行=ユーザーID、列=タレント37名（0/1、uint8）

依存ライブラリ: pandas, pyarrow (pip install pandas pyarrow)
Python: 3.8+
"""

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from config_jp import MEMBERS_JP, DATA_DIR

URLS_DIR    = Path(DATA_DIR) / "urls_jp"
CHATS_DIR   = Path(DATA_DIR) / "chats"
MATRIX_PATH = Path(DATA_DIR) / "matrix_jp.parquet"

RENDERER_TYPES = [
    "liveChatTextMessageRenderer",
    "liveChatPaidMessageRenderer",
    "liveChatMembershipItemRenderer",
    "liveChatPaidStickerRenderer",
]


def extract_author_ids(chat_file: Path) -> set:
    """live_chat.json から authorExternalChannelId の集合を返す。"""
    author_ids = set()
    with open(chat_file, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            actions = obj.get("replayChatItemAction", {}).get("actions", [])
            for action in actions:
                item = action.get("addChatItemAction", {}).get("item", {})
                for rtype in RENDERER_TYPES:
                    uid = item.get(rtype, {}).get("authorExternalChannelId")
                    if uid:
                        author_ids.add(uid)
    return author_ids


def load_video_ids(key: str) -> list[str]:
    tsv_path = URLS_DIR / f"{key}.tsv"
    if not tsv_path.exists():
        return []
    with open(tsv_path, encoding="utf-8") as f:
        return [
            line.split("\t")[0]
            for line in f.readlines()[1:]
            if line.strip() and not line.startswith("video_id")
        ]


def main():
    member_users: dict[str, set] = {key: set() for key in MEMBERS_JP}

    for key, member in MEMBERS_JP.items():
        video_ids = load_video_ids(key)
        if not video_ids:
            print(f"{member['name']}: TSVなし（step1 未実行またはスキップ）")
            continue
        print(f"{member['name']}: {len(video_ids)} 配信を処理中...")

        for video_id in video_ids:
            chat_file = CHATS_DIR / f"{video_id}.live_chat.json"
            if not chat_file.exists():
                print(f"  スキップ（ファイルなし）: {video_id}")
                continue
            ids = extract_author_ids(chat_file)
            member_users[key].update(ids)
            print(f"  {video_id}: {len(ids):,} ユーザー（累計 {len(member_users[key]):,}）")

    all_users = set().union(*member_users.values())
    print(f"\n全タレント合計ユニークユーザー: {len(all_users):,} 人")

    # エッジリスト → pivot でマトリックス構築
    print("マトリックス構築中...")
    records = [
        {"user_id": uid, "member": key}
        for key, users in member_users.items()
        for uid in users
    ]
    if not records:
        print("エラー: チャットデータが空です。step2 を先に実行してください。")
        return

    edge_df = pd.DataFrame(records)
    matrix = (
        edge_df.assign(val=1)
        .pivot_table(index="user_id", columns="member", values="val", fill_value=0, aggfunc="max")
        .astype("uint8")
    )
    matrix.columns.name = None
    matrix = matrix.reindex(columns=list(MEMBERS_JP.keys()), fill_value=0)

    Path(DATA_DIR).mkdir(exist_ok=True)
    matrix.to_parquet(MATRIX_PATH)
    print(f"保存完了: {MATRIX_PATH}  ({matrix.shape[0]:,} 行 × {matrix.shape[1]} 列)")


if __name__ == "__main__":
    main()
