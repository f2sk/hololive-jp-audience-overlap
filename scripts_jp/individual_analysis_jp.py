"""
個別タレント深掘り分析スクリプト

指定タレント X を軸に、本論文の手法（Jaccard、3項lift、複推し分布、配信間多様性等）
を一人に絞って詳細に展開する。論文の§5に対する個別タレント版の付録的位置づけ。

実行方法:
    python scripts_jp/individual_analysis_jp.py --talent kanade

出力:
    data/plots/jp/individual_<key>/      # 図表PNG群
    reports_jp/individuals_jp/individual_<key>_jp.md   # Markdownレポート

依存: pandas, matplotlib, scipy, numpy, pyarrow
Python: 3.10+
"""

import argparse
import copy
import json
import sys
from itertools import combinations
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from config_jp import DATA_DIR, DATA_DIR_JP, MEMBERS_JP, UNIT_COLOR
from step8_age_analysis_jp import years_since_debut, load_subscribers

matplotlib.use("Agg")
matplotlib.rcParams["axes.unicode_minus"] = False

import matplotlib.path as _mpath
def _path_deepcopy_fix(self, memo):
    result = object.__new__(type(self))
    memo[id(self)] = result
    result.__dict__.update(copy.deepcopy(self.__dict__, memo))
    return result
_mpath.Path.__deepcopy__ = _path_deepcopy_fix

_JP_FONTS = ["Yu Gothic", "Meiryo", "MS Gothic", "IPAexGothic"]
_av = {f.name for f in fm.fontManager.ttflist}
for _f in _JP_FONTS:
    if _f in _av:
        matplotlib.rcParams["font.family"] = _f
        break

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

MATRIX_PATH = Path(DATA_DIR) / "matrix_jp.parquet"
URLS_DIR    = Path(DATA_DIR) / "urls_jp"
CHATS_DIR   = Path(DATA_DIR) / "chats"
EXCLUDED_KEYS = {"choco", "laplus", "niko"}

RENDERER_TYPES = [
    "liveChatTextMessageRenderer",
    "liveChatPaidMessageRenderer",
    "liveChatMembershipItemRenderer",
    "liveChatPaidStickerRenderer",
]


def extract_chat_ids(p: Path) -> set:
    """live_chat.json から authorExternalChannelId の集合を取得。"""
    ids = set()
    with open(p, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            actions = obj.get("replayChatItemAction", {}).get("actions", [])
            for a in actions:
                item = a.get("addChatItemAction", {}).get("item", {})
                for rt in RENDERER_TYPES:
                    if rt in item:
                        cid = item[rt].get("authorExternalChannelId")
                        if cid:
                            ids.add(cid)
                        break
    return ids


def load_per_stream_users(talent_key: str) -> dict[str, dict]:
    """{video_id: {'date': str, 'title': str, 'users': set}} を返す。"""
    tsv = URLS_DIR / f"{talent_key}.tsv"
    result = {}
    with open(tsv, encoding="utf-8") as f:
        for line in f.readlines()[1:]:
            parts = line.strip().split("\t")
            if parts[0] == "video_id" or not parts[0]:
                continue
            vid, date, title = parts[0], parts[1], parts[2] if len(parts) > 2 else ""
            chat_path = CHATS_DIR / f"{vid}.live_chat.json"
            if chat_path.exists():
                ids = extract_chat_ids(chat_path)
                result[vid] = {"date": date, "title": title, "users": ids}
    return result


def main():
    parser = argparse.ArgumentParser(description="個別タレント深掘り分析")
    parser.add_argument("--talent", default="kanade",
                        help="対象タレントのキー（例: kanade, vivi, pekora）")
    args = parser.parse_args()

    TARGET = args.talent
    if TARGET not in MEMBERS_JP:
        print(f"エラー: '{TARGET}' は MEMBERS_JP に存在しません")
        sys.exit(1)

    target_name = MEMBERS_JP[TARGET]["name"]
    target_unit = MEMBERS_JP[TARGET]["units"][0]
    print(f"=== {target_name}（{target_unit}）個別分析 ===\n")

    out_dir = Path(DATA_DIR_JP) / f"individual_{TARGET}"
    out_dir.mkdir(parents=True, exist_ok=True)
    report_dir = Path("reports_jp") / "individuals_jp"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"individual_{TARGET}_jp.md"

    # --------------------------------------------------------------
    # データロード
    # --------------------------------------------------------------
    df = pd.read_parquet(MATRIX_PATH)
    keys = [k for k in MEMBERS_JP if k not in EXCLUDED_KEYS and k in df.columns]
    if TARGET in EXCLUDED_KEYS:
        print(f"警告: {TARGET} は EXCLUDED_KEYS に含まれています")
        sys.exit(1)
    df = df[keys]
    arr = df.values.astype(bool)
    N = len(df)
    n = len(keys)
    subs = load_subscribers()
    i_t = keys.index(TARGET)
    A = arr[:, i_t]
    A_total = int(A.sum())

    # --------------------------------------------------------------
    # 1. 基本プロファイル
    # --------------------------------------------------------------
    print("[1] 基本プロファイル計算中...")
    target_subs = subs.get(TARGET, 0)
    participation_rate = A_total / target_subs * 100 if target_subs else 0
    debut_years = years_since_debut(TARGET)

    other_arr = np.delete(arr, i_t, axis=1)
    no_other = ~other_arr.any(axis=1)
    exclusive = (A & no_other).sum()
    exclusive_rate = exclusive / A_total * 100

    multi_counts = arr.sum(axis=1)[A]
    mean_multi = multi_counts.mean()
    median_multi = float(np.median(multi_counts))

    # 複推し数分布
    unique_vals, counts = np.unique(multi_counts, return_counts=True)
    distrib = list(zip(unique_vals.tolist(), counts.tolist()))

    # 複推し分布図
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(unique_vals, counts, color="#4488cc", edgecolor="black", linewidth=0.3)
    ax.set_xlabel(f"{target_name}参加者が同時参加した他タレント数（自分含む）", fontsize=12)
    ax.set_ylabel("人数", fontsize=12)
    ax.set_title(f"{target_name}参加者の複推し数分布（N={A_total:,}）", fontsize=13, fontweight="bold")
    ax.set_yscale("log")
    ax.grid(alpha=0.3, axis="y", which="both")
    fig.tight_layout()
    fig.savefig(out_dir / "multitalent_distrib.png", dpi=140, bbox_inches="tight")
    plt.close(fig)

    # --------------------------------------------------------------
    # 2. 重複ネットワーク
    # --------------------------------------------------------------
    print("[2] 重複ネットワーク計算中...")
    jaccards = []
    for j in range(n):
        if j == i_t:
            continue
        B = arr[:, j]
        inter = int((A & B).sum())
        uni = int((A | B).sum())
        jac = inter / uni if uni > 0 else 0
        out_rate = inter / A_total if A_total > 0 else 0
        jaccards.append({
            "key": keys[j], "name": MEMBERS_JP[keys[j]]["name"],
            "unit": MEMBERS_JP[keys[j]]["units"][0],
            "jaccard": jac, "intersection": inter, "outflow_rate": out_rate,
        })

    jac_sorted = sorted(jaccards, key=lambda x: -x["jaccard"])
    out_sorted = sorted(jaccards, key=lambda x: -x["outflow_rate"])

    # Jaccard 上位10 を棒グラフ化（規模補正済みのペアワイズ強度を視覚化）
    top10_jac = jac_sorted[:10]
    fig, ax = plt.subplots(figsize=(11, 6.5))
    names = [r["name"] for r in top10_jac][::-1]
    vals = [r["jaccard"] * 100 for r in top10_jac][::-1]
    colors = [UNIT_COLOR.get(r["unit"], "#888") for r in top10_jac][::-1]
    ax.barh(names, vals, color=colors, edgecolor="black", linewidth=0.4)
    ax.set_xlabel(f"{target_name} と当該タレントの Jaccard 係数（%）", fontsize=11)
    ax.set_title(f"{target_name} と他タレントのペア重複（Jaccard 上位10、規模補正済み）",
                 fontsize=13, fontweight="bold")
    ax.grid(alpha=0.3, axis="x")
    for i, v in enumerate(vals):
        ax.text(v + 0.05, i, f"{v:.2f}%", va="center", fontsize=9, color="#333")
    fig.tight_layout()
    fig.savefig(out_dir / "jaccard_top10.png", dpi=140, bbox_inches="tight")
    plt.close(fig)

    # 視聴者共有率 vs Jaccard 散布図（規模効果と結合強度の対比を可視化）
    import matplotlib.patches as mpatches
    try:
        from adjustText import adjust_text
        HAS_ADJUST = True
    except ImportError:
        HAS_ADJUST = False

    fig, ax = plt.subplots(figsize=(14, 10))
    texts = []
    xs_data, ys_data = [], []
    # マーカーサイズは共視聴者数 |A∩B| に比例（最小50〜最大1200）
    max_inter = max(r["intersection"] for r in jaccards)
    min_inter = min(r["intersection"] for r in jaccards)
    for r in jaccards:
        color = UNIT_COLOR.get(r["unit"], "#888")
        x = r["outflow_rate"] * 100; y = r["jaccard"] * 100
        # 線形スケール（共視聴者数比例）
        size = 80 + (r["intersection"] - min_inter) / (max_inter - min_inter + 1e-9) * 1200
        ax.scatter(x, y, s=size, c=color, alpha=0.7, edgecolor="black", linewidth=0.7, zorder=3)
        t = ax.annotate(r["name"], (x, y), fontsize=13, fontweight="bold",
                        alpha=0.95, zorder=4)
        texts.append(t)
        xs_data.append(x); ys_data.append(y)

    # 軸範囲をデータに合わせて設定（視聴者共有率はマリン等で大きくなりやすいが、Jaccardはタイトに）
    x_max = max(xs_data) * 1.10
    y_max = max(ys_data) * 1.15
    ax.set_xlim(0, x_max); ax.set_ylim(0, y_max)

    ax.set_xlabel(f"{target_name} 視点での当該タレントへの視聴者共有率（%）", fontsize=14)
    ax.set_ylabel(f"Jaccard 係数（%）", fontsize=14)
    ax.set_title(f"{target_name} と他34タレント: 視聴者共有率 × Jaccard 散布図\n"
                 f"マーカーサイズ=共視聴者数。右=規模効果で共有率高め / 上=規模補正済みでも強い結合",
                 fontsize=13, fontweight="bold")
    ax.tick_params(axis="both", labelsize=12)
    ax.grid(alpha=0.3, zorder=0)

    legend_patches = [mpatches.Patch(color=col, label=u) for u, col in UNIT_COLOR.items()]
    ax.legend(handles=legend_patches, loc="lower right", ncol=2, fontsize=11, frameon=True)

    # ラベル衝突回避（adjustText が利用可能なら使用）
    if HAS_ADJUST:
        adjust_text(texts, xs_data, ys_data, ax=ax,
                    expand_points=(1.3, 1.3), expand_text=(1.1, 1.2),
                    arrowprops=dict(arrowstyle="-", color="#888", lw=0.5, alpha=0.5))

    fig.tight_layout()
    fig.savefig(out_dir / "metric_scatter.png", dpi=140, bbox_inches="tight")
    plt.close(fig)

    # ペア順位（全 595中）
    pairs = []
    for i, j in combinations(range(n), 2):
        inter = int((arr[:, i] & arr[:, j]).sum())
        uni = int((arr[:, i] | arr[:, j]).sum())
        jac = inter / uni if uni else 0
        pairs.append((keys[i], keys[j], jac, inter))
    pairs.sort(key=lambda x: -x[2])

    target_ranks = []
    for rank, (a, b, jac, c) in enumerate(pairs, 1):
        if a == TARGET or b == TARGET:
            partner = b if a == TARGET else a
            target_ranks.append({
                "rank": rank, "partner": partner,
                "partner_name": MEMBERS_JP[partner]["name"],
                "partner_unit": MEMBERS_JP[partner]["units"][0],
                "jaccard": jac, "intersection": c,
            })

    # 3項 lift は小規模 B・C で値が増幅されてノイズに支配されるため、
    # 個別レポートでは指標として採用しない（過去版では §2.3 にあった）

    # --------------------------------------------------------------
    # 3. ファン構造分解
    # --------------------------------------------------------------
    print("[3] ファン構造分解中...")
    # ユニット別
    unit_groups = {}
    for k in keys:
        if k == TARGET:
            continue
        u = MEMBERS_JP[k]["units"][0]
        unit_groups.setdefault(u, []).append(k)

    unit_stats = []
    for unit, ks in unit_groups.items():
        unit_arr = np.zeros(len(A), dtype=bool)
        for k in ks:
            unit_arr |= arr[:, keys.index(k)]
        inter = int((A & unit_arr).sum())
        jacs = []
        for k in ks:
            B = arr[:, keys.index(k)]
            i = (A & B).sum(); u_ = (A | B).sum()
            if u_ > 0:
                jacs.append(i / u_ * 100)
        unit_stats.append({
            "unit": unit, "n_members": len(ks),
            "outflow_count": inter, "outflow_rate": inter / A_total * 100,
            "mean_pair_jaccard": float(np.mean(jacs)) if jacs else 0,
        })

    # 世代別
    age_buckets = [
        ("2018年以前(7年超)", 7, 99),
        ("2019-2020(5-7年)", 5, 7),
        ("2021-2023(2-5年)", 2, 5),
        ("2024-(2年未満)",   0, 2),
    ]
    age_stats = []
    for label, lo, hi in age_buckets:
        ks = [k for k in keys if k != TARGET and lo <= years_since_debut(k) < hi]
        if not ks:
            continue
        grp_arr = np.zeros(len(A), dtype=bool)
        for k in ks:
            grp_arr |= arr[:, keys.index(k)]
        inter = int((A & grp_arr).sum())
        jacs = []
        for k in ks:
            B = arr[:, keys.index(k)]
            i = (A & B).sum(); u_ = (A | B).sum()
            if u_ > 0:
                jacs.append(i / u_ * 100)
        age_stats.append({
            "label": label, "n_members": len(ks),
            "outflow_count": inter, "outflow_rate": inter / A_total * 100,
            "mean_pair_jaccard": float(np.mean(jacs)) if jacs else 0,
        })

    # 規模別
    scale_buckets = [
        ("メガ(300万人超)",   3_000_000, 99_000_000),
        ("大(200-300万)",    2_000_000, 3_000_000),
        ("中(100-200万)",    1_000_000, 2_000_000),
        ("小(50-100万)",       500_000, 1_000_000),
        ("極小(50万未満)",            0,   500_000),
    ]
    scale_stats = []
    for label, lo, hi in scale_buckets:
        ks = [k for k in keys if k != TARGET and lo <= subs.get(k, 0) < hi]
        if not ks:
            continue
        grp_arr = np.zeros(len(A), dtype=bool)
        for k in ks:
            grp_arr |= arr[:, keys.index(k)]
        inter = int((A & grp_arr).sum())
        jacs = []
        for k in ks:
            B = arr[:, keys.index(k)]
            i = (A & B).sum(); u_ = (A | B).sum()
            if u_ > 0:
                jacs.append(i / u_ * 100)
        scale_stats.append({
            "label": label, "n_members": len(ks),
            "outflow_count": inter, "outflow_rate": inter / A_total * 100,
            "mean_pair_jaccard": float(np.mean(jacs)) if jacs else 0,
        })

    # --------------------------------------------------------------
    # 4. 構造的位置
    # --------------------------------------------------------------
    print("[4] 構造的位置計算中...")
    n_top30 = sum(1 for r in target_ranks if r["rank"] <= 30)
    n_top100 = sum(1 for r in target_ranks if r["rank"] <= 100)
    best_rank = target_ranks[0]["rank"]

    # 平均Jaccard
    avg_jaccards = {}
    for k in keys:
        i = keys.index(k)
        js = []
        for jj in range(n):
            if jj == i:
                continue
            B = arr[:, i]; Bp = arr[:, jj]
            inter = (B & Bp).sum()
            uni = (B | Bp).sum()
            if uni > 0:
                js.append(inter / uni * 100)
        avg_jaccards[k] = float(np.mean(js)) if js else 0
    ranked = sorted(avg_jaccards.items(), key=lambda x: x[1])
    target_avg_j = avg_jaccards[TARGET]
    target_avg_j_rank = next(i for i, (k, v) in enumerate(ranked, 1) if k == TARGET)

    # 上位10ペアのユニット分散
    top10 = target_ranks[:10]
    unit_diversity = len(set(r["partner_unit"] for r in top10))

    # --------------------------------------------------------------
    # 5. 配信間多様性
    # --------------------------------------------------------------
    print("[5] 配信間多様性（生チャット処理）中...")
    streams = load_per_stream_users(TARGET)
    if not streams:
        print(f"警告: {TARGET}の生チャットが取得できない。配信間多様性をスキップします")

    stream_analysis = None
    if streams:
        vids = list(streams.keys())
        # 配信間Jaccard
        inter_jaccards = []
        for i, j in combinations(range(len(vids)), 2):
            a, b = streams[vids[i]]["users"], streams[vids[j]]["users"]
            if not a or not b:
                continue
            jac = len(a & b) / len(a | b) * 100
            inter_jaccards.append(jac)

        # 各配信の独自参加者率
        unique_rates = {}
        for vid, info in streams.items():
            others = set()
            for v, inf in streams.items():
                if v != vid:
                    others |= inf["users"]
            unique = len(info["users"] - others)
            pct = unique / len(info["users"]) * 100 if info["users"] else 0
            unique_rates[vid] = {"unique": unique, "pct": pct, "total": len(info["users"])}

        # 累積カーブ（古い順）
        sorted_vids = sorted(vids, key=lambda v: streams[v]["date"])
        cumul_users = set()
        cumul = []
        for i, vid in enumerate(sorted_vids, 1):
            cumul_users |= streams[vid]["users"]
            cumul.append({
                "step": i, "vid": vid, "date": streams[vid]["date"],
                "title": streams[vid]["title"],
                "stream_n": len(streams[vid]["users"]),
                "cumul_n": len(cumul_users),
            })

        # 累積カーブ図
        fig, ax = plt.subplots(figsize=(11, 5.5))
        steps = [c["step"] for c in cumul]
        cumul_n = [c["cumul_n"] for c in cumul]
        stream_n = [c["stream_n"] for c in cumul]
        ax.bar(steps, stream_n, color="#88aacc", alpha=0.5, edgecolor="black",
               linewidth=0.4, label="配信ごとの参加者数")
        ax2 = ax.twinx()
        ax2.plot(steps, cumul_n, marker="o", color="#cc3333", linewidth=2.2,
                 markersize=10, label="累積ユニーク参加者数")
        for i, c in enumerate(cumul):
            ax2.annotate(f'{c["cumul_n"]:,}', (c["step"], c["cumul_n"]),
                         xytext=(0, 10), textcoords="offset points",
                         ha="center", fontsize=9, color="#aa2222")
        ax.set_xlabel("配信数（古い順）", fontsize=11)
        ax.set_ylabel("配信ごとの参加者数", fontsize=11)
        ax2.set_ylabel("累積ユニーク参加者数", fontsize=11, color="#cc3333")
        ax.set_title(f"{target_name}の配信ごとの参加者数と累積ユニーク参加者カーブ",
                     fontsize=12, fontweight="bold")
        ax.set_xticks(steps)
        ax.grid(alpha=0.3, axis="y")
        fig.tight_layout()
        fig.savefig(out_dir / "cumulative_unique.png", dpi=140, bbox_inches="tight")
        plt.close(fig)

        stream_analysis = {
            "inter_jaccard_min": min(inter_jaccards),
            "inter_jaccard_max": max(inter_jaccards),
            "inter_jaccard_mean": float(np.mean(inter_jaccards)),
            "inter_jaccard_median": float(np.median(inter_jaccards)),
            "unique_rates": unique_rates,
            "cumul": cumul,
        }

    # --------------------------------------------------------------
    # Markdownレポート生成
    # --------------------------------------------------------------
    print("[6] Markdownレポート生成中...")
    md = []
    md.append(f"# {target_name}（{target_unit}）個別深掘り分析\n")
    md.append(f"本論文の手法を {target_name} 一人に絞って詳細展開する個別レポート。"
              f"集計時点: 2026年5月、10配信固定サンプル。\n")

    md.append("## 1. 基本プロファイル\n")
    md.append(f"| 項目 | 値 |\n|---|---:|")
    md.append(f"| 所属ユニット | {target_unit} |")
    md.append(f"| 活動年数（2026-05-25時点） | {debut_years:.2f}年 |")
    md.append(f"| 登録者数 | {target_subs:,} |")
    md.append(f"| チャット参加者数（10配信総ユニーク） | {A_total:,} |")
    md.append(f"| 参加率（=ユニーク数/登録者数） | {participation_rate:.2f}% |")
    md.append(f"| 専属ファン（{target_name}のみ参加） | {exclusive:,}（{exclusive_rate:.1f}%） |")
    md.append(f"| 平均複推し数（自分含む） | {mean_multi:.2f} |")
    md.append(f"| 中央値複推し数 | {median_multi:.1f} |\n")

    md.append(f"### 1.1 複推し数分布\n")
    md.append(f"{target_name}参加者を「同時参加した他タレント数」で集計した分布（自分含む、1=単独）。\n")
    md.append(f"![複推し数分布](../../data/plots/jp/individual_{TARGET}/multitalent_distrib.png)\n")

    md.append("## 2. 重複ネットワーク\n")
    md.append("### 2.1 Jaccard 上位10タレント\n")
    md.append(f"{target_name}と他タレントとのペアJaccard係数（規模補正済み）。"
              f"$|A \\cap B|/|A \\cup B|$ で計算し、両タレントの規模差に依存しない結合強度を示す。"
              f"順位は全595ペア中の順位。\n")
    md.append(f"![Jaccard 上位10](../../data/plots/jp/individual_{TARGET}/jaccard_top10.png)\n")
    md.append("| 順位 | タレント | ユニット | Jaccard | 共視聴者数 |\n|---:|---|---|---:|---:|")
    for r in target_ranks[:10]:
        md.append(f"| {r['rank']} | {r['partner_name']} | {r['partner_unit']} | "
                  f"{r['jaccard']*100:.2f}% | {r['intersection']:,} |")
    md.append("")

    md.append(f"### 2.2 視聴者共有率上位と 視聴者共有率 × Jaccard 散布図\n")
    md.append(f"**{target_name}視点での他タレントへの視聴者共有率** = $|A \\cap B|/|A|$、"
              f"すなわち「{target_name}の参加者のうち、当該タレント B にも参加した割合」。"
              f"**視聴者共有率は B の規模に比例するため、絶対値は B が大規模であるほど自然に高くなる**。"
              f"以下の散布図では、視聴者共有率（X軸）と Jaccard（Y軸）を同時にプロットする。"
              f"**右方向に位置 = 規模効果で視聴者共有率が押し上げられている**、"
              f"**上方向に位置 = 規模補正済みでも強い結合** と読める。\n")
    md.append(f"![視聴者共有率 × Jaccard 散布図](../../data/plots/jp/individual_{TARGET}/metric_scatter.png)\n")
    md.append(f"**視聴者共有率上位15**: 巨大タレント（マリン・スバル・すいせい等）が上位を占めるのは規模効果。"
              f"その中に非巨大タレントが食い込む場合は、Jaccard でも上位にあるか確認すると規模補正済みの結合強度が判断できる。\n")
    md.append("| 順位 | タレント | 視聴者共有率 | 共視聴者数 | Jaccard |\n|---:|---|---:|---:|---:|")
    for i, r in enumerate(out_sorted[:15], 1):
        md.append(f"| {i} | {r['name']} | {r['outflow_rate']*100:.1f}% | "
                  f"{r['intersection']:,} | {r['jaccard']*100:.2f}% |")
    md.append("")

    md.append("## 3. ファン構造分解\n")
    md.append("### 3.1 ユニット別重複\n")
    md.append(f"{target_name}参加者の中で各ユニットのタレントいずれかに参加した人の割合と、"
              f"当該ユニット内タレントとの平均ペアJaccard。\n")
    md.append("| ユニット | 人数 | 視聴者共有率 | 共視聴者数 | 平均ペアJaccard |\n|---|---:|---:|---:|---:|")
    for s in unit_stats:
        md.append(f"| {s['unit']} | {s['n_members']} | {s['outflow_rate']:.1f}% | "
                  f"{s['outflow_count']:,} | {s['mean_pair_jaccard']:.2f}% |")
    md.append("")

    md.append("### 3.2 活動年数（世代）別重複\n")
    md.append(f"{target_name}参加者の各世代タレント群への重複度。\n")
    md.append("| 世代 | 人数 | 視聴者共有率 | 平均ペアJaccard |\n|---|---:|---:|---:|")
    for s in age_stats:
        md.append(f"| {s['label']} | {s['n_members']} | {s['outflow_rate']:.1f}% | "
                  f"{s['mean_pair_jaccard']:.2f}% |")
    md.append("")

    md.append("### 3.3 登録者規模別重複\n")
    md.append(f"{target_name}参加者の規模別タレント群への重複度。\n")
    md.append("| 規模 | 人数 | 視聴者共有率 | 平均ペアJaccard |\n|---|---:|---:|---:|")
    for s in scale_stats:
        md.append(f"| {s['label']} | {s['n_members']} | {s['outflow_rate']:.1f}% | "
                  f"{s['mean_pair_jaccard']:.2f}% |")
    md.append("")

    md.append("## 4. 構造的位置\n")
    md.append(f"### 4.1 ハブ性指標\n")
    md.append(f"- {target_name}絡みペアの最高順位: **{best_rank}/595**")
    md.append(f"- 上位30以内に入る{target_name}絡みペアの数: **{n_top30}/30**")
    md.append(f"- 上位100以内に入る{target_name}絡みペアの数: **{n_top100}/100**\n")

    md.append(f"### 4.2 横断接続性\n")
    md.append(f"{target_name}のJaccard上位10ペアの所属ユニット数: **{unit_diversity}/10ユニット**\n")
    md.append("Jaccard上位10ペアの内訳:")
    for r in target_ranks[:10]:
        md.append(f"- {r['partner_name']}（{r['partner_unit']}）J={r['jaccard']*100:.2f}%, 順位{r['rank']}")
    md.append("")

    md.append(f"### 4.3 外れ値度（平均Jaccard）\n")
    md.append(f"- {target_name}の他34名との平均Jaccard: **{target_avg_j:.2f}%**")
    md.append(f"- 35名中の順位（小さい順、外れ値ほど上位）: **{target_avg_j_rank}/35**\n")
    md.append("**解釈**: 値が小さいほど他タレントとの重なりが薄く外れ値的位置、"
              "大きいほどハブ的位置。35名中で見て中央付近にあれば「平均的な接続度」、"
              "上位5位以内なら外れ値、下位5位以内ならハブ。\n")

    if stream_analysis:
        md.append("## 5. 配信間多様性\n")
        md.append(f"### 5.1 配信ペア間Jaccard\n")
        md.append(f"{target_name}の10配信間で、ペアごとに参加者集合のJaccard係数を計算した分布。\n")
        md.append(f"| 統計 | 値 |\n|---|---:|")
        md.append(f"| 最小 | {stream_analysis['inter_jaccard_min']:.1f}% |")
        md.append(f"| 平均 | {stream_analysis['inter_jaccard_mean']:.1f}% |")
        md.append(f"| 中央値 | {stream_analysis['inter_jaccard_median']:.1f}% |")
        md.append(f"| 最大 | {stream_analysis['inter_jaccard_max']:.1f}% |\n")
        md.append("**解釈**: 値が高ければ配信間で「常連層」が中心、"
                  "値が低ければ配信ごとに「一見さん層」が多い。\n")

        md.append(f"### 5.2 各配信の独自参加者率\n")
        md.append("他9配信に参加していない「その配信だけに来た独自参加者」の割合。"
                  "値が高い配信は特異な層を呼び込んだ可能性を示す。\n")
        md.append("| 配信日 | 参加者数 | 独自参加者 | 独自率 | タイトル |\n|---|---:|---:|---:|---|")
        for c in stream_analysis["cumul"]:
            ur = stream_analysis["unique_rates"][c["vid"]]
            md.append(f"| {c['date']} | {ur['total']:,} | {ur['unique']:,} | "
                      f"{ur['pct']:.1f}% | {c['title'][:40]} |")
        md.append("")

        md.append(f"### 5.3 累積ユニーク参加者カーブ\n")
        md.append("古い配信から順に1本ずつ追加していった時の累積ユニーク参加者数。"
                  "カーブが早く頭打ちになるほど常連が多く、長く伸び続けるほど新規流入が多い。\n")
        md.append(f"![累積カーブ](../../data/plots/jp/individual_{TARGET}/cumulative_unique.png)\n")
        md.append("| 本数 | 配信日 | 配信参加者 | 累積ユニーク |\n|---:|---|---:|---:|")
        for c in stream_analysis["cumul"]:
            md.append(f"| {c['step']}本目 | {c['date']} | {c['stream_n']:,} | {c['cumul_n']:,} |")
        md.append("")

    md.append("## 6. まとめ\n")
    md.append(f"- {target_name}は活動 {debut_years:.1f}年・登録者 {target_subs/10000:.1f}万人。")
    md.append(f"  チャット参加コア層は {A_total:,}人で参加率 {participation_rate:.2f}%。")
    md.append(f"- 専属ファンは {exclusive_rate:.1f}%、平均複推し数は {mean_multi:.2f}人。")
    md.append(f"- Jaccard 最高ペアは {target_ranks[0]['partner_name']}（{target_ranks[0]['jaccard']*100:.2f}%、全595ペア中{target_ranks[0]['rank']}位）。")
    md.append(f"- 視聴者共有率絶対数では人気古参（{out_sorted[0]['name']} {out_sorted[0]['outflow_rate']*100:.1f}%、"
              f"{out_sorted[1]['name']} {out_sorted[1]['outflow_rate']*100:.1f}%）が上位だが、"
              f"Jaccard では同世代・同規模タレント（{target_ranks[0]['partner_name']}、{target_ranks[1]['partner_name']}）が上位。")
    md.append(f"- ハブ性指標は弱め（上位30以内ペアは {n_top30} 組）、")
    md.append(f"  平均Jaccard {target_avg_j:.2f}% は35名中 {target_avg_j_rank} 位（小さい順）。")
    if stream_analysis:
        md.append(f"- 配信間ユーザー重複は平均 {stream_analysis['inter_jaccard_mean']:.1f}%、"
                  f"累積カーブは10本で {stream_analysis['cumul'][-1]['cumul_n']:,}人に到達。")
    md.append("")

    md.append("---")
    md.append("*分析時点: 2026年5月25日。本論文 `report_audience_paper_jp.pdf` の方法論を流用。"
              "個別タレントへの応用例として作成。*")

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md))

    print(f"\n保存:")
    print(f"  レポート: {report_path}")
    print(f"  図表:    {out_dir}/")


if __name__ == "__main__":
    main()
