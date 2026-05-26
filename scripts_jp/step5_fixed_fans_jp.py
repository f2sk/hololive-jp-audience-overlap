"""
固定ファン比率算出スクリプト（ホロライブJP 35名版）

各タレントについて、分析期間内の配信のうち過半数以上に
チャット参加したユーザーを「固定ファン」と定義し、その比率を算出する。

実行方法:
    python scripts_jp/step5_fixed_fans_jp.py

出力:
    data/plots/jp/fixed_fans.md  - Markdown サマリー（タレント別・ユニット別）

依存ライブラリ: pandas (pip install pandas)
Python: 3.8+
"""

import json
import math
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from config_jp import DATA_DIR, DATA_DIR_JP, MEMBERS_JP

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

URLS_DIR  = Path(DATA_DIR) / "urls_jp"
CHATS_DIR = Path(DATA_DIR) / "chats"
PLOTS_DIR = Path(DATA_DIR_JP)
THRESHOLD = 0.5  # 固定ファンの閾値: 配信の50%以上に参加

# 分析対象外（step1 件数不足、step4 と同じ判定）
EXCLUDED_KEYS = {"choco", "laplus", "niko"}


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


def extract_author_ids(chat_file: Path) -> set[str]:
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
                for rtype in [
                    "liveChatTextMessageRenderer",
                    "liveChatPaidMessageRenderer",
                    "liveChatMembershipItemRenderer",
                    "liveChatPaidStickerRenderer",
                ]:
                    uid = item.get(rtype, {}).get("authorExternalChannelId")
                    if uid:
                        author_ids.add(uid)
    return author_ids


def main():
    PLOTS_DIR.mkdir(parents=True, exist_ok=True)

    rows = []
    print(f"固定ファン閾値: 配信の {THRESHOLD*100:.0f}% 以上参加\n")

    target_keys = [k for k in MEMBERS_JP.keys() if k not in EXCLUDED_KEYS]
    print(f"分析対象: {len(target_keys)} 名\n")

    for key in target_keys:
        member = MEMBERS_JP[key]
        video_ids = load_video_ids(key)
        if not video_ids:
            continue

        attendance: dict[str, int] = defaultdict(int)
        available = 0
        for vid in video_ids:
            chat_file = CHATS_DIR / f"{vid}.live_chat.json"
            if not chat_file.exists():
                continue
            available += 1
            for uid in extract_author_ids(chat_file):
                attendance[uid] += 1

        if not attendance:
            continue

        total_unique   = len(attendance)
        threshold_cnt  = max(2, math.ceil(available * THRESHOLD))
        fixed_fans     = sum(1 for cnt in attendance.values() if cnt >= threshold_cnt)
        fixed_fan_rate = fixed_fans / total_unique if total_unique > 0 else 0

        units_str = "/".join(member["units"])
        print(f"{member['name']:14s} ({available}配信) ユニーク {total_unique:6,} / 固定(≥{threshold_cnt}) {fixed_fans:5,} ({fixed_fan_rate:.1%})")

        rows.append({
            "key":             key,
            "タレント":         member["name"],
            "ユニット":         units_str,
            "primary_unit":    member["units"][0],
            "配信数":           available,
            "ユニーク視聴者":   total_unique,
            "固定ファン数":     fixed_fans,
            "固定ファン率":     fixed_fan_rate,
            "閾値":             threshold_cnt,
        })

    df = pd.DataFrame(rows).sort_values("固定ファン率", ascending=False)

    # ---- Markdown 出力 ----
    out_path = PLOTS_DIR / "fixed_fans.md"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(f"# 固定ファン比率（配信の {THRESHOLD*100:.0f}% 以上参加）\n\n")
        f.write(f"分析対象: {len(target_keys)} 名（{','.join(MEMBERS_JP[k]['name'] for k in EXCLUDED_KEYS)} 除外）\n\n")

        f.write("## タレント別（固定ファン率降順）\n\n")
        f.write("| タレント | ユニット | 配信数 | ユニーク視聴者 | 固定ファン数 | 固定ファン率 |\n")
        f.write("|----------|----------|--------|----------------|--------------|------------|\n")
        for _, r in df.iterrows():
            f.write(
                f"| {r['タレント']} | {r['ユニット']} | {r['配信数']} "
                f"| {r['ユニーク視聴者']:,} | {r['固定ファン数']:,} | {r['固定ファン率']:.1%} |\n"
            )

        # ユニット別集計（primary_unit ベース）
        f.write("\n## ユニット別（平均固定ファン率）\n\n")
        f.write("| ユニット | メンバー数 | 平均固定ファン率 | 中央値 | 最小〜最大 |\n")
        f.write("|----------|------------|------------------|--------|------------|\n")
        for unit in ["0期生", "1期生", "2期生", "ゲーマーズ", "3期生", "4期生", "5期生", "6期生", "ReGLOSS", "FLOW GLOW"]:
            sub = df[df["primary_unit"] == unit]
            if len(sub) == 0:
                continue
            mean_r = sub["固定ファン率"].mean()
            med_r  = sub["固定ファン率"].median()
            min_r  = sub["固定ファン率"].min()
            max_r  = sub["固定ファン率"].max()
            f.write(f"| {unit} | {len(sub)} | {mean_r:.1%} | {med_r:.1%} | {min_r:.1%}〜{max_r:.1%} |\n")

    print(f"\n保存: {out_path}")


if __name__ == "__main__":
    main()
