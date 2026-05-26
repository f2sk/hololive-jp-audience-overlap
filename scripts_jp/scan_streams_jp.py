"""
配信枠スキャンスクリプト（ホロライブJP全体版）

DATE_START 以降 DATE_END 以前の配信を最大 PLAYLIST_END 件取得し、
除外基準の確認や URL 選定 (step1) のための TSV データを生成する。

実行方法:
    python scripts_jp/scan_streams_jp.py

出力:
    data/scan_jp/<member_key>.tsv  - video_id / upload_date / title / flagged の TSV
    data/scan_jp/flagged.tsv       - 記念枠と判定された配信一覧
    data/scan_jp/windows.md        - 各メンバーの安全区間候補

依存ライブラリ: yt-dlp (pip install yt-dlp)
Python: 3.8+
"""

import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config_jp import DATE_START, DATE_END, MEMBERS_JP, DATA_DIR

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SCAN_DIR     = Path(DATA_DIR) / "scan_jp"
PLAYLIST_END = 200  # DATE_START(20260101)〜今日(約143日)＋余裕分。こより144件で150が限界寸前だったため増加

# venv 内の yt-dlp を優先使用
_PROJECT_ROOT = Path(DATA_DIR).parent
_YT_DLP_EXE = _PROJECT_ROOT / ".venv" / "Scripts" / "yt-dlp.exe"
YT_DLP = str(_YT_DLP_EXE) if _YT_DLP_EXE.exists() else "yt-dlp"

# 記念枠を検出するキーワード
MEMORIAL_KEYWORDS = re.compile(
    r"誕生日|バースデー|birthday|記念|周年|anniversary|"
    r"デビュー|debut|卒業|graduation|"
    r"フェス|festival|fes|コンサート|concert|(?<!ホロ)(?<!ド)ライブ|live.*tour|"
    r"3dお披露目|3dlive|立体|お披露目|耐久",
    re.IGNORECASE,
)


def fetch_stream_list(key: str, channel_id: str, name: str) -> tuple[str, list[dict], str]:
    import time
    url = f"https://www.youtube.com/channel/{channel_id}/streams"
    cmd = [
        YT_DLP,
        "--skip-download",
        "--print", "%(id)s\t%(upload_date)s\t%(title)s",
        "--dateafter", DATE_START,
        # --datebefore は使わない：playlist-end と併用すると全件スキップされる。
        # DATE_END 以前のフィルタリングは step1 の Python 側で実施。
        "--playlist-end", str(PLAYLIST_END),
        url,
    ]
    env = {**os.environ, "PYTHONUTF8": "1"}
    started = time.time()
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            encoding="utf-8", errors="replace", env=env,
            timeout=240,  # 1チャンネル最大4分
        )
        stdout = result.stdout
        stderr = result.stderr
        returncode = result.returncode
    except subprocess.TimeoutExpired as e:
        stdout = e.stdout or ""
        stderr = e.stderr or ""
        returncode = -1
    elapsed = int(time.time() - started)

    videos = []
    for line in (stdout or "").strip().splitlines():
        parts = line.split("\t", 2)
        if not parts or not parts[0]:
            continue
        videos.append({
            "id":    parts[0],
            "date":  parts[1] if len(parts) > 1 else "NA",
            "title": parts[2] if len(parts) > 2 else "NA",
        })

    warning = ""
    if returncode == -1:
        warning = "TIMEOUT (240s)"
    elif returncode != 0:
        first_err = (stderr or "").strip().splitlines()[0] if (stderr or "").strip() else ""
        warning = first_err[:120]

    return key, videos, warning, elapsed


def is_memorial(title: str) -> bool:
    return bool(MEMORIAL_KEYWORDS.search(title))


def find_safe_windows(videos: list[dict], window_size: int = 10) -> list[int]:
    """記念枠を含まない連続 window_size 本の開始インデックスを返す（古い順）。"""
    ordered = list(reversed(videos))
    flags = [is_memorial(v["title"]) for v in ordered]
    safe_starts = []
    for i in range(len(ordered) - window_size + 1):
        if not any(flags[i:i + window_size]):
            safe_starts.append(i)
    return safe_starts


def has_existing_data(key: str) -> bool:
    """既に2行以上（ヘッダー + データ1件以上）あればスキップ対象。"""
    tsv_path = SCAN_DIR / f"{key}.tsv"
    if not tsv_path.exists():
        return False
    with open(tsv_path, encoding="utf-8") as f:
        lines = f.readlines()
    return len(lines) >= 2


def write_tsv(key: str, videos: list[dict]) -> Path:
    """TSVを即時書き込みする。データが0件の場合はヘッダーのみ。"""
    tsv_path = SCAN_DIR / f"{key}.tsv"
    with open(tsv_path, "w", encoding="utf-8") as f:
        f.write("video_id\tupload_date\ttitle\tflagged\n")
        for v in videos:
            flag = "1" if is_memorial(v["title"]) else ""
            f.write(f"{v['id']}\t{v['date']}\t{v['title']}\t{flag}\n")
    return tsv_path


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="既存データがあっても再取得する")
    args = parser.parse_args()

    SCAN_DIR.mkdir(parents=True, exist_ok=True)

    # 欠損メンバー（ヘッダーのみ or ファイルなし）のみ対象にする（--force で全件再取得）
    if args.force:
        targets = list(MEMBERS_JP.items())
        print(f"--force モード: 全 {len(targets)} チャンネルを再取得\n")
    else:
        targets = [(k, m) for k, m in MEMBERS_JP.items() if not has_existing_data(k)]
        skipped = len(MEMBERS_JP) - len(targets)
        print(f"欠損 {len(targets)} チャンネルを取得（{skipped} チャンネルはスキップ）\n")
        if not targets:
            print("全チャンネルのデータが揃っています。終了します。")
            return

    n = len(targets)
    print(f"{DATE_START}〜{DATE_END} の配信を最大 {PLAYLIST_END} 件取得中... ({n} チャンネル)\n")

    tasks = [(key, m["channel_id"], m["name"]) for key, m in targets]
    all_videos: dict[str, list[dict]] = {k: [] for k in MEMBERS_JP}
    # 既存データは保持（書き直さない）
    for key, _ in MEMBERS_JP.items():
        if has_existing_data(key):
            tsv_path = SCAN_DIR / f"{key}.tsv"
            with open(tsv_path, encoding="utf-8") as f:
                lines = f.readlines()[1:]
            videos = []
            for line in lines:
                parts = line.rstrip("\n").split("\t")
                if len(parts) >= 3 and parts[0]:
                    videos.append({"id": parts[0], "date": parts[1], "title": parts[2]})
            all_videos[key] = videos

    # 全タスクを並列ワーカー2で処理（即時書き込みで途中クラッシュ時も部分結果保持）
    print(f"\n{n} チャンネルを並列取得開始（最大2並列、各240秒タイムアウト）...", flush=True)
    completed = 0
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = {executor.submit(fetch_stream_list, *t): t[0] for t in tasks}
        for future in as_completed(futures):
            fkey = futures[future]
            fname = MEMBERS_JP[fkey]["name"]
            completed += 1
            try:
                key, videos, warning, elapsed = future.result()
                all_videos[key] = videos
                write_tsv(key, videos)  # 即時書き込み
                status = f"{len(videos)} 件 ({elapsed}s)"
                if warning:
                    status += f"  [警告] {warning[:80]}"
                print(f"  [{completed}/{n}] {fname}: {status}", flush=True)
            except Exception as e:
                print(f"  [{completed}/{n}] {fname}: 失敗 ({type(e).__name__}: {e})", flush=True)

    # 記念枠集計（全メンバーのデータから再構築）
    print("\n記念枠集計中...", flush=True)
    flagged_rows = []
    for key in MEMBERS_JP:
        for v in all_videos.get(key, []):
            if is_memorial(v["title"]):
                flagged_rows.append({**v, "member": MEMBERS_JP[key]["name"]})

    # 記念枠一覧
    flagged_path = SCAN_DIR / "flagged.tsv"
    with open(flagged_path, "w", encoding="utf-8") as f:
        f.write("member\tvideo_id\tupload_date\ttitle\n")
        for r in sorted(flagged_rows, key=lambda x: x["date"]):
            f.write(f"{r['member']}\t{r['id']}\t{r['date']}\t{r['title']}\n")
    print(f"\n記念枠候補: {len(flagged_rows)} 件 → {flagged_path}")

    # 安全区間（連続10配信で記念枠なし）
    print("\n=== 各メンバーの安全区間（記念枠なし連続10配信）===")
    window_results = {}
    for key in MEMBERS_JP:
        name   = MEMBERS_JP[key]["name"]
        videos = all_videos.get(key, [])
        if len(videos) < 10:
            print(f"  {name}: 配信数不足 ({len(videos)} 件)")
            window_results[key] = []
            continue
        ordered = list(reversed(videos))
        safe = find_safe_windows(ordered)
        window_results[key] = safe
        if safe:
            first = ordered[safe[0]]
            last  = ordered[safe[0] + 9]
            print(f"  {name}: 最初の安全区間 = {first['date']}〜{last['date']}")
        else:
            print(f"  {name}: 安全区間なし")

    # Markdown 出力
    md_path = SCAN_DIR / "windows.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# 安全区間候補（記念枠なし連続10配信）\n\n")
        f.write(f"取得期間: {DATE_START}〜{DATE_END} / 最大取得数: {PLAYLIST_END}\n\n")
        for key in MEMBERS_JP:
            name   = MEMBERS_JP[key]["name"]
            videos = all_videos.get(key, [])
            ordered = list(reversed(videos))
            safe = window_results.get(key, [])
            f.write(f"## {name}\n\n")
            if not safe:
                f.write("安全区間なし\n\n")
                continue
            f.write("| # | 開始配信 | 開始日 | 終了配信 | 終了日 |\n")
            f.write("|---|---------|--------|---------|--------|\n")
            for rank, idx in enumerate(safe[:5], 1):
                s = ordered[idx]
                e = ordered[idx + 9]
                f.write(f"| {rank} | {s['id']} | {s['date']} | {e['id']} | {e['date']} |\n")
            f.write("\n")
    print(f"\n安全区間レポート → {md_path}")


if __name__ == "__main__":
    main()
