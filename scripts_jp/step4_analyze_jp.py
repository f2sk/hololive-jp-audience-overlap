"""
分析・可視化スクリプト（ホロライブJP全体版）

matrix_jp.parquet を読み込み、37名のチャット参加者統計・ユニット別重複・
全体ユニーク登録者数推定を算出する。

実行方法:
    python scripts_jp/step4_analyze_jp.py

出力:
    data/plots/jp/upset.png     - UpSet風 Plot（37タレントの重複構造、上位パターン）
    data/plots/jp/summary.md    - ユニット別・タレント別集計 Markdown
    data/plots/jp/subscribers_jp.tsv  - 登録者数キャッシュ

依存ライブラリ: pandas, pyarrow, matplotlib, yt-dlp (pip install ...)
Python: 3.8+
"""

import copy
import os
import subprocess
import sys
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from config_jp import DATE_START, DATE_END, MEMBERS_JP, UNIT_COLOR, DATA_DIR, DATA_DIR_JP

matplotlib.use("Agg")
# 日本語フォント設定（Windows標準: Yu Gothic / Meiryo）
matplotlib.rcParams["font.family"] = ["Yu Gothic", "Meiryo", "MS Gothic", "sans-serif"]
matplotlib.rcParams["axes.unicode_minus"] = False

# Python 3.14 で copy.deepcopy(super()) が無限再帰するバグの回避
import matplotlib.path as _mpath
def _path_deepcopy_fix(self, memo):
    result = object.__new__(type(self))
    memo[id(self)] = result
    result.__dict__.update(copy.deepcopy(self.__dict__, memo))
    return result
_mpath.Path.__deepcopy__ = _path_deepcopy_fix

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

MATRIX_PATH = Path(DATA_DIR) / "matrix_jp.parquet"
URLS_DIR    = Path(DATA_DIR) / "urls_jp"
PLOTS_DIR   = Path(DATA_DIR_JP)
SUBS_CACHE  = PLOTS_DIR / "subscribers_jp.tsv"

# 分析対象外（urls_jpに1件もない or 件数不足で意図的除外）
# - 癒月ちょこ: 5件しか取れず step1 でTSV作成スキップ
# - ラプラス・ダークネス: 7件しか取れず step1 でTSV作成スキップ
# - 虎金妃笑虎: 活動低調期にコラボ・休止告知等を除外すると8件のため step1 スキップ
EXCLUDED_KEYS = {"choco", "laplus", "niko"}

# venv 内の yt-dlp を優先使用
_PROJECT_ROOT = Path(DATA_DIR).parent
_YT_DLP_EXE = _PROJECT_ROOT / ".venv" / "Scripts" / "yt-dlp.exe"
YT_DLP = str(_YT_DLP_EXE) if _YT_DLP_EXE.exists() else "yt-dlp"


def _run_yt_dlp_get_count(channel_id: str, end: int) -> int:
    cmd = [
        YT_DLP,
        "--skip-download",
        "--print", "%(channel_follower_count)s",
        "--playlist-end", str(end),
        "--ignore-errors",
        f"https://www.youtube.com/channel/{channel_id}",
    ]
    env = {**os.environ, "PYTHONUTF8": "1"}
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
    for line in result.stdout.strip().splitlines():
        line = line.strip()
        if line and line != "NA":
            try:
                return int(line)
            except (ValueError, TypeError):
                continue
    return 0


def fetch_subscriber_count(channel_id: str) -> int:
    """登録者数取得。--playlist-end 1 で速く試し、失敗時のみ 5 にフォールバック。"""
    n = _run_yt_dlp_get_count(channel_id, 1)
    if n > 0:
        return n
    # 最新動画がメン限/プレミア公開待機中で失敗したケース
    return _run_yt_dlp_get_count(channel_id, 5)


def load_or_fetch_subscribers() -> dict[str, int]:
    """登録者数キャッシュ(.tsv) があれば読み込み、なければ取得して保存。"""
    if SUBS_CACHE.exists():
        print(f"登録者数キャッシュ読み込み: {SUBS_CACHE}")
        with open(SUBS_CACHE, encoding="utf-8") as f:
            return {
                line.split("\t")[0]: int(line.strip().split("\t")[1])
                for line in f.readlines()[1:]
                if line.strip() and not line.startswith("key")
            }
    print("登録者数を取得中（yt-dlp 経由）...")
    counts = {}
    for key, member in MEMBERS_JP.items():
        c = fetch_subscriber_count(member["channel_id"])
        counts[key] = c
        print(f"  {member['name']}: {c:,}", flush=True)
    PLOTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(SUBS_CACHE, "w", encoding="utf-8") as f:
        f.write("key\tcount\tname\n")
        for key, c in counts.items():
            f.write(f"{key}\t{c}\t{MEMBERS_JP[key]['name']}\n")
    return counts


def main():
    PLOTS_DIR.mkdir(parents=True, exist_ok=True)

    df = pd.read_parquet(MATRIX_PATH)
    print(f"マトリックス読み込み: {df.shape[0]:,} ユーザー × {df.shape[1]} タレント")

    # 分析対象タレント = 全37名から EXCLUDED_KEYS を除く（urls_jp 件数不足のため）
    target_keys = [k for k in MEMBERS_JP.keys() if k not in EXCLUDED_KEYS]
    excluded_names = [MEMBERS_JP[k]["name"] for k in EXCLUDED_KEYS]
    print(f"分析対象: {len(target_keys)} 名（除外: {', '.join(excluded_names)}）")

    subscriber_counts = load_or_fetch_subscribers()

    # ---- タレント別ユニークチャット参加者数 ----
    print("\n=== タレント別チャット参加ユニークユーザー数 ===")
    talent_rows = []
    for key in target_keys:
        member = MEMBERS_JP[key]
        if key not in df.columns:
            print(f"  {member['name']}: 列なし（スキップ）")
            continue
        unique_chatters = int(df[key].sum())
        subs = subscriber_counts.get(key, 0)
        chat_rate = unique_chatters / subs if subs > 0 else 0
        units_str = "/".join(member["units"])
        talent_rows.append({
            "key":               key,
            "タレント":           member["name"],
            "ユニット":           units_str,
            "登録者数":           subs,
            "チャット参加ユニーク数": unique_chatters,
            "チャット参加率":     chat_rate,
        })
        print(f"  {member['name']:14s}: {unique_chatters:7,} 人  (登録者比 {chat_rate:.3%})")

    # ---- ユニット別集計（フブキは1期生・ゲーマーズ両所属で重複カウント、対象外は除く）----
    unit_to_keys: dict[str, list[str]] = {u: [] for u in UNIT_COLOR.keys()}
    for key in target_keys:
        for u in MEMBERS_JP[key]["units"]:
            unit_to_keys[u].append(key)
    # 対象35名のJP全体
    unit_to_keys["JP全体（35名）"] = target_keys

    print("\n=== ユニット別ユニーク数 ===")
    unit_stats = {}
    for unit_name, keys in unit_to_keys.items():
        cols = [k for k in keys if k in df.columns]
        if not cols:
            continue
        unique_count = int(df[cols].any(axis=1).sum())
        total_count  = sum(int(df[k].sum()) for k in cols)
        unique_rate  = unique_count / total_count if total_count > 0 else 0
        # ユニット内登録者数合計
        unit_subs = sum(subscriber_counts.get(k, 0) for k in cols)
        # ユニットのユニーク登録者下限推定
        unit_estimated = int(unit_subs * unique_rate) if unique_rate > 0 else 0
        unit_stats[unit_name] = {
            "メンバー数":  len(cols),
            "ユニーク数":  unique_count,
            "延べ数":      total_count,
            "ユニーク率":  unique_rate,
            "登録者数合計": unit_subs,
            "推定登録者数": unit_estimated,
        }
        print(f"  {unit_name:10s} ({len(cols):2d}名): ユニーク {unique_count:7,} / 延べ {total_count:7,} = {unique_rate:.3%}, 登録者{unit_subs:,} → 推定{unit_estimated:,}")

    # ---- Markdown サマリー ----
    summary_path = PLOTS_DIR / "summary.md"
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(f"# ホロライブJP 全体チャット分析サマリー\n\n")
        f.write(f"分析期間: {DATE_START}〜{DATE_END}（DATE_END以前で各メンバー最大10配信）\n\n")
        f.write(f"全体: {df.shape[0]:,} ユニークユーザー × {df.shape[1]} タレント\n\n")

        f.write("## タレント別\n\n")
        f.write("| タレント | ユニット | 登録者数 | チャット参加ユニーク | 参加率 |\n")
        f.write("|----------|----------|----------|---------------------|--------|\n")
        for r in talent_rows:
            f.write(
                f"| {r['タレント']} | {r['ユニット']} | {r['登録者数']:,} "
                f"| {r['チャット参加ユニーク数']:,} | {r['チャット参加率']:.3%} |\n"
            )

        f.write("\n## ユニット別\n\n")
        f.write("| ユニット | メンバー数 | ユニーク数 | 延べ数 | ユニーク率 | 登録者数合計 | 推定登録者数（下限） |\n")
        f.write("|----------|------------|------------|--------|------------|--------------|----------------------|\n")
        for unit_name, s in unit_stats.items():
            f.write(
                f"| {unit_name} | {s['メンバー数']} | {s['ユニーク数']:,} | {s['延べ数']:,} "
                f"| {s['ユニーク率']:.3%} | {s['登録者数合計']:,} | {s['推定登録者数']:,} |\n"
            )

    print(f"\nサマリー保存: {summary_path}")

    # ---- UpSet Plot（独自matplotlib実装、対象タレントのみ）----
    print("UpSet Plot 作成中...")
    keys = [k for k in target_keys if k in df.columns]
    n = len(keys)

    pattern_counts: dict[tuple, int] = {}
    for row in df[keys].itertuples(index=False):
        pattern_counts[row] = pattern_counts.get(row, 0) + 1

    # 上位 N パターン
    top_n = 40
    sorted_patterns = sorted(
        [(cnt, pat) for pat, cnt in pattern_counts.items() if any(pat)],
        reverse=True,
    )[:top_n]
    counts = [c for c, _ in sorted_patterns]
    patterns = [p for _, p in sorted_patterns]
    m = len(patterns)

    # ---- 縦長UpSet（タレントを横軸・パターンを縦軸に転置）----
    # 棒グラフを右、ドット行列を左に配置することで35タレントの読みやすさを確保
    labels = []
    label_colors = []
    for k in keys:
        m_obj = MEMBERS_JP[k]
        labels.append(m_obj["name"])
        label_colors.append(UNIT_COLOR.get(m_obj["units"][0], "#666"))

    fig, (ax_mat, ax_bar) = plt.subplots(
        1, 2,
        figsize=(11, max(10, m * 0.30)),
        gridspec_kw={"width_ratios": [3, 2]},
        sharey=True,
    )
    fig.subplots_adjust(wspace=0.04)

    # 左: ドット行列 (横軸=タレント、縦軸=パターン上から下に降順)
    ax_mat.set_xlim(-0.5, n - 0.5)
    ax_mat.set_ylim(m - 0.5, -0.5)  # 上から順位1
    ax_mat.set_xticks(range(n))
    ax_mat.set_xticklabels(labels, fontsize=8, rotation=90)
    for tick_label, color in zip(ax_mat.get_xticklabels(), label_colors):
        tick_label.set_color(color)
        tick_label.set_fontweight("bold")
    ax_mat.xaxis.set_ticks_position("top")
    ax_mat.set_yticks(range(m))
    ax_mat.set_yticklabels([f"#{i+1}" for i in range(m)], fontsize=7)
    ax_mat.tick_params(left=False, top=False, bottom=False)
    ax_mat.grid(False)
    ax_mat.set_title(f"JP 35 talents chat overlap (top {m} patterns)", fontsize=11, pad=10)

    for x in np.arange(-0.5, n, 1):
        ax_mat.axvline(x, color="#f0f0f0", linewidth=0.3)
    for y in np.arange(-0.5, m, 1):
        ax_mat.axhline(y, color="#f0f0f0", linewidth=0.3)

    for yi, pat in enumerate(patterns):
        filled = [xi for xi, v in enumerate(pat) if v]
        empty  = [xi for xi, v in enumerate(pat) if not v]
        if filled:
            ax_mat.plot([min(filled), max(filled)], [yi, yi], color="#4C72B0", linewidth=1.5, zorder=1)
        ax_mat.scatter(filled, [yi] * len(filled), color="#4C72B0", s=35, zorder=2)
        ax_mat.scatter(empty,  [yi] * len(empty),  color="#dcdcdc", s=35, zorder=2)

    # 右: 横向き棒グラフ
    ax_bar.barh(range(m), counts, color="#4C72B0", height=0.7)
    ax_bar.set_xlabel("Users")
    ax_bar.tick_params(left=False, labelleft=False)
    for i, c in enumerate(counts):
        ax_bar.text(c + max(counts) * 0.01, i, str(c), ha="left", va="center", fontsize=7)
    ax_bar.set_xlim(0, max(counts) * 1.15)

    plot_path = PLOTS_DIR / "upset.png"
    plt.savefig(plot_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"UpSet Plot 保存: {plot_path}")

    # ---- 全体ユニーク登録者数推定（対象35名のみ）----
    print("\n=== 最終推定: JP全体 ユニーク登録者数（下限値、対象35名）===")
    total_subs = sum(subscriber_counts.get(k, 0) for k in target_keys)
    jp_rate = unit_stats["JP全体（35名）"]["ユニーク率"]
    jp_estimated = int(total_subs * jp_rate)
    print(f"  Σ登録者数 (対象{len(target_keys)}名): {total_subs:,}")
    print(f"  チャットユニーク率:   {jp_rate:.3%}")
    print(f"  推定ユニーク登録者数: {jp_estimated:,} 人 ({jp_estimated/10000:.0f}万人)")
    print(f"  （除外: {', '.join(excluded_names)} = {sum(subscriber_counts.get(k,0) for k in EXCLUDED_KEYS):,} 名）")


if __name__ == "__main__":
    main()
