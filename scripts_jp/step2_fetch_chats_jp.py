"""
チャットログ取得スクリプト（ホロライブJP全体版）

step1 で収集した配信 video_id のライブチャットリプレイを JSON 形式で保存する。
取得済みファイルはスキップするため、途中で止まっても再開可能。

--gen 引数で期生単位に分割実行できる（37タレント×10配信=370配信のため、
期生ごとに分割して中断・再開を安全に行う）。

実行方法:
    # 期生別実行（推奨）
    python scripts_jp/step2_fetch_chats_jp.py --gen gen0
    python scripts_jp/step2_fetch_chats_jp.py --gen gen1
    python scripts_jp/step2_fetch_chats_jp.py --gen gen2
    python scripts_jp/step2_fetch_chats_jp.py --gen gamers
    python scripts_jp/step2_fetch_chats_jp.py --gen gen3
    python scripts_jp/step2_fetch_chats_jp.py --gen gen4
    python scripts_jp/step2_fetch_chats_jp.py --gen gen5
    python scripts_jp/step2_fetch_chats_jp.py --gen gen6
    # DEV_IS は既存データ流用のためスキップ可能
    # python scripts_jp/step2_fetch_chats_jp.py --gen regloss
    # python scripts_jp/step2_fetch_chats_jp.py --gen flowglow

    # 全期生まとめて実行
    python scripts_jp/step2_fetch_chats_jp.py --gen all

    # 利用可能な --gen 値を確認
    python scripts_jp/step2_fetch_chats_jp.py --list-gens

出力:
    data/chats/<video_id>.live_chat.json  - 配信ごとのチャットログ
    （DEV_IS版と同じディレクトリ。共通利用可能）

依存ライブラリ: yt-dlp (pip install yt-dlp)
Python: 3.8+
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config_jp import MEMBERS_JP, DATA_DIR

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

URLS_DIR  = Path(DATA_DIR) / "urls_jp"
CHATS_DIR = Path(DATA_DIR) / "chats"

# venv 内の yt-dlp を優先使用
_PROJECT_ROOT = Path(DATA_DIR).parent
_YT_DLP_EXE = _PROJECT_ROOT / ".venv" / "Scripts" / "yt-dlp.exe"
YT_DLP = str(_YT_DLP_EXE) if _YT_DLP_EXE.exists() else "yt-dlp"

# ------------------------------------------------------------------ #
# 期生グループ定義
# ------------------------------------------------------------------ #
# MEMBERS_JP のキーリストを期生ごとにまとめる。
# gen と units の対応は config_jp.py の MEMBERS_JP["xxx"]["units"] に準拠。

GEN_GROUPS: dict[str, list[str]] = {
    "gen0":     ["sora", "roboco", "azki", "suisei", "miko"],
    "gen1":     ["fubuki", "matsuri", "aki"],
    "gen2":     ["ayame", "choco", "subaru"],
    "gamers":   ["mio", "okayu", "korone"],       # fubuki は gen1 に含む
    "gen3":     ["pekora", "flare", "noel", "marine"],
    "gen4":     ["watame", "towa", "luna"],
    "gen5":     ["lamy", "nene", "botan", "polka"],
    "gen6":     ["laplus", "lui", "koyori", "iroha"],
    "regloss":  ["kanade", "ririka", "raden", "hajime"],
    "flowglow": ["riona", "su", "chihaya", "vivi", "niko"],
}
GEN_GROUPS["all"] = [k for keys in GEN_GROUPS.values() for k in keys]


def fetch_chat(video_id: str) -> str:
    """
    チャットリプレイを取得する。
    戻り値: "ok" / "no_chat" / "error"
    """
    out_template = str(CHATS_DIR / "%(id)s")
    cmd = [
        YT_DLP,
        "--write-subs",
        "--sub-langs", "live_chat",
        "--skip-download",
        "--output", out_template,
        "--sleep-interval", "3",
        f"https://www.youtube.com/watch?v={video_id}",
    ]
    env = {**os.environ, "PYTHONUTF8": "1"}
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)

    if (CHATS_DIR / f"{video_id}.live_chat.json").exists():
        return "ok"

    stderr_lower = result.stderr.lower()
    if "there are no subtitles" in stderr_lower or "requested format is not available" in stderr_lower:
        return "no_chat"
    return "error"


def load_video_ids(keys: list[str]) -> list[tuple[str, str, str]]:
    """指定キーの TSV から (member_key, video_id, title) を返す。"""
    rows = []
    for key in keys:
        tsv_path = URLS_DIR / f"{key}.tsv"
        if not tsv_path.exists():
            print(f"[警告] {tsv_path} が見つかりません。step1 を先に実行してください。")
            continue
        with open(tsv_path, encoding="utf-8") as f:
            for line in f.readlines()[1:]:
                parts = line.strip().split("\t", 2)
                if parts and parts[0] and parts[0] != "video_id":
                    title = parts[2] if len(parts) > 2 else ""
                    rows.append((key, parts[0], title))
    return rows


def main():
    parser = argparse.ArgumentParser(description="JP チャットログ取得（期生別実行対応）")
    parser.add_argument(
        "--gen", default="all",
        help="取得する期生グループ名。例: gen0, gen1, gamers, gen3, ... all",
    )
    parser.add_argument(
        "--list-gens", action="store_true",
        help="利用可能な --gen 値とメンバー数を表示して終了",
    )
    args = parser.parse_args()

    if args.list_gens:
        print("利用可能な --gen 値:")
        for gen, keys in GEN_GROUPS.items():
            if gen == "all":
                continue
            names = [MEMBERS_JP[k]["name"] for k in keys if k in MEMBERS_JP]
            print(f"  {gen:<10} ({len(keys)}名): {', '.join(names)}")
        print(f"  {'all':<10} ({len(GEN_GROUPS['all'])}名): 全期生")
        return

    gen_name = args.gen
    if gen_name not in GEN_GROUPS:
        print(f"エラー: --gen '{gen_name}' は不正な値です。")
        print(f"有効な値: {', '.join(GEN_GROUPS.keys())}")
        sys.exit(1)

    target_keys = GEN_GROUPS[gen_name]
    # MEMBERS_JP に存在するキーのみ処理
    target_keys = [k for k in target_keys if k in MEMBERS_JP]

    CHATS_DIR.mkdir(parents=True, exist_ok=True)

    target_names = [MEMBERS_JP[k]["name"] for k in target_keys]
    print(f"=== {gen_name} ({len(target_keys)}名): {', '.join(target_names)} ===\n")

    videos = load_video_ids(target_keys)
    print(f"合計 {len(videos)} 件を処理します。\n")

    counts = {"ok": 0, "skipped": 0, "no_chat": 0, "error": 0}

    for i, (key, video_id, title) in enumerate(videos, 1):
        chat_file = CHATS_DIR / f"{video_id}.live_chat.json"
        prefix = f"[{i:03d}/{len(videos)}]"

        if chat_file.exists():
            print(f"{prefix} スキップ（取得済み）: {video_id}")
            counts["skipped"] += 1
            continue

        member_name = MEMBERS_JP[key]["name"]
        print(f"{prefix} {member_name}: {title[:50]}...")
        status = fetch_chat(video_id)
        counts[status] += 1

        if status == "no_chat":
            print(f"         → チャットリプレイなし")
        elif status == "error":
            print(f"         → 取得失敗")

    print(f"\n完了 [{gen_name}]: 取得成功 {counts['ok']} 件 / スキップ {counts['skipped']} 件 "
          f"/ チャットなし {counts['no_chat']} 件 / エラー {counts['error']} 件")


if __name__ == "__main__":
    main()
