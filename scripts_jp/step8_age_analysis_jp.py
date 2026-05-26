"""
活動年数分析 & 期生別ペア分析（JP 35名版）

1. 各タレントの活動年数（デビュー日からの経過月数/年数）とチャット参加率の関係を散布図化
2. 各期生のユニット内ペアJaccard係数と595中の順位を集計

実行方法:
    python scripts_jp/step8_age_analysis_jp.py

出力:
    data/plots/jp/activity_vs_chatrate.png  - 活動年数 vs チャット参加率 散布図
    data/plots/jp/unit_internal_pairs.md    - 各期生内ペアのJaccard順位
"""

import sys
from datetime import date
from itertools import combinations
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import numpy as np
import pandas as pd
from scipy.stats import pearsonr, spearmanr

sys.path.insert(0, str(Path(__file__).parent))
from config_jp import DATA_DIR, DATA_DIR_JP, MEMBERS_JP, UNIT_COLOR

matplotlib.use("Agg")
matplotlib.rcParams["axes.unicode_minus"] = False
_JP_FONTS = ["Yu Gothic", "Meiryo", "MS Gothic", "IPAexGothic"]
_available = {f.name for f in fm.fontManager.ttflist}
for _f in _JP_FONTS:
    if _f in _available:
        matplotlib.rcParams["font.family"] = _f
        break

# Python 3.14 deepcopy 回避
import copy as _copy
import matplotlib.path as _mpath
def _path_deepcopy_fix(self, memo):
    result = object.__new__(type(self))
    memo[id(self)] = result
    result.__dict__.update(_copy.deepcopy(self.__dict__, memo))
    return result
_mpath.Path.__deepcopy__ = _path_deepcopy_fix

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

MATRIX_PATH = Path(DATA_DIR) / "matrix_jp.parquet"
SUBS_CACHE  = Path(DATA_DIR_JP) / "subscribers_jp.tsv"
PLOTS_DIR   = Path(DATA_DIR_JP)

EXCLUDED_KEYS = {"choco", "laplus", "niko"}

# Wikipedia ホロライブプロダクション ページより取得
DEBUT_DATE = {
    "sora":     "2017-12-12",
    "roboco":   "2018-03-04",
    "miko":     "2018-08-01",
    "suisei":   "2018-03-22",
    "azki":     "2018-11-15",
    "fubuki":   "2018-06-01",
    "matsuri":  "2018-06-01",
    "aki":      "2018-06-01",
    "ayame":    "2018-09-03",
    "subaru":   "2018-09-16",
    "mio":      "2018-12-07",
    "okayu":    "2019-04-06",
    "korone":   "2019-04-13",
    "pekora":   "2019-07-17",
    "flare":    "2019-08-07",
    "noel":     "2019-08-08",
    "marine":   "2019-08-11",
    "watame":   "2019-12-29",
    "towa":     "2020-01-03",
    "luna":     "2020-01-04",
    "lamy":     "2020-08-12",
    "nene":     "2020-08-13",
    "botan":    "2020-08-14",
    "polka":    "2020-08-16",
    "lui":      "2021-11-27",
    "koyori":   "2021-11-28",
    "iroha":    "2021-11-30",
    "kanade":   "2023-09-09",
    "ririka":   "2023-09-09",
    "raden":    "2023-09-10",
    "hajime":   "2023-09-10",
    "riona":    "2024-11-09",
    "su":       "2024-11-09",
    "chihaya":  "2024-11-09",
    "vivi":     "2024-11-09",
}

# 分析時点（matrix_jp.parquet生成日）を基準とする
ANALYSIS_DATE = date(2026, 5, 25)


def years_since_debut(key: str) -> float:
    """デビューから ANALYSIS_DATE までの年数（小数）。"""
    d = DEBUT_DATE[key]
    debut = date.fromisoformat(d)
    days = (ANALYSIS_DATE - debut).days
    return days / 365.25


def load_subscribers() -> dict[str, int]:
    if not SUBS_CACHE.exists():
        raise FileNotFoundError(f"登録者数キャッシュなし: {SUBS_CACHE}（先に step4 を実行してください）")
    with open(SUBS_CACHE, encoding="utf-8") as f:
        return {
            line.split("\t")[0]: int(line.strip().split("\t")[1])
            for line in f.readlines()[1:]
            if line.strip() and not line.startswith("key")
        }


def main():
    PLOTS_DIR.mkdir(parents=True, exist_ok=True)

    df = pd.read_parquet(MATRIX_PATH)
    target_keys = [k for k in MEMBERS_JP if k not in EXCLUDED_KEYS and k in df.columns]
    df = df[target_keys]
    subs = load_subscribers()

    # =====================================================
    # 1. 活動年数 vs チャット参加率 散布図
    # =====================================================
    print("=== 1. 活動年数 vs チャット参加率 ===")
    rows = []
    for key in target_keys:
        name = MEMBERS_JP[key]["name"]
        u = MEMBERS_JP[key]["units"][0]
        y = years_since_debut(key)
        unique = int(df[key].sum())
        s = subs.get(key, 0)
        rate = unique / s if s > 0 else 0
        rows.append({
            "key": key, "name": name, "unit": u,
            "years": y, "unique": unique, "subs": s, "rate": rate,
        })
    rate_df = pd.DataFrame(rows)

    # 相関係数
    r_p, p_p = pearsonr(rate_df["years"], rate_df["rate"])
    r_s, p_s = spearmanr(rate_df["years"], rate_df["rate"])
    # 対数線形のSpearmanとPearson on log(rate)
    log_rate = np.log(rate_df["rate"].clip(lower=1e-6))
    r_p_log, p_p_log = pearsonr(rate_df["years"], log_rate)

    print(f"Pearson  (年数 vs 参加率):       r = {r_p:+.3f}, p = {p_p:.4f}")
    print(f"Spearman (年数 vs 参加率):       ρ = {r_s:+.3f}, p = {p_s:.4f}")
    print(f"Pearson  (年数 vs log参加率):    r = {r_p_log:+.3f}, p = {p_p_log:.4f}")

    # ---- 散布図描画 ----
    fig, ax = plt.subplots(figsize=(11, 8))
    for unit, color in UNIT_COLOR.items():
        sub = rate_df[rate_df["unit"] == unit]
        if len(sub) == 0:
            continue
        ax.scatter(sub["years"], sub["rate"] * 100, s=110, c=color,
                   alpha=0.85, edgecolor="black", linewidth=0.6, label=unit, zorder=3)

    # 各点にタレント名
    for _, r in rate_df.iterrows():
        ax.annotate(r["name"], (r["years"], r["rate"] * 100),
                    fontsize=7, alpha=0.8,
                    xytext=(5, 3), textcoords="offset points")

    # 対数線形フィット
    coef = np.polyfit(rate_df["years"], log_rate, 1)
    xs = np.linspace(rate_df["years"].min() - 0.3, rate_df["years"].max() + 0.3, 100)
    ys = np.exp(np.polyval(coef, xs)) * 100
    ax.plot(xs, ys, "--", color="#555555", linewidth=1.5, alpha=0.7, zorder=2,
            label=f"対数線形フィット (Pearson r={r_p_log:+.2f})")

    ax.set_xlabel("活動年数（年、デビューから 2026-05-25 時点）", fontsize=12)
    ax.set_ylabel("チャット参加率（%、対数スケール）", fontsize=12)
    ax.set_yscale("log")
    ax.set_title("活動年数 vs チャット参加率（35名）", fontsize=13, fontweight="bold")
    ax.grid(alpha=0.3, which="both")
    ax.legend(fontsize=8, loc="lower left", ncol=2)

    out_scatter = PLOTS_DIR / "activity_vs_chatrate.png"
    fig.tight_layout()
    fig.savefig(out_scatter, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"保存: {out_scatter}\n")

    # =====================================================
    # 2. 各期生のユニット内ペアJaccard順位
    # =====================================================
    print("=== 2. 期生別ユニット内ペア分析 ===")

    arr = df.values.astype(np.int32)
    C = arr.T @ arr
    diag = np.diag(C).astype(float)

    pairs = []
    for i, j in combinations(range(len(target_keys)), 2):
        c = C[i, j]
        if c == 0:
            continue
        denom = diag[i] + diag[j] - c
        jac = c / denom if denom > 0 else 0.0
        pairs.append({
            "i": target_keys[i], "j": target_keys[j], "jac": jac, "cooccur": c,
        })
    pair_df = pd.DataFrame(pairs).sort_values("jac", ascending=False).reset_index(drop=True)
    pair_df["rank"] = pair_df.index + 1
    total_pairs = len(pair_df)
    print(f"総ペア数: {total_pairs}")

    # 期生別のメンバーキー（target_keysに含まれるもののみ）
    UNITS_ORDER = ["0期生", "1期生", "2期生", "ゲーマーズ", "3期生",
                   "4期生", "5期生", "6期生", "ReGLOSS", "FLOW GLOW"]
    unit_members: dict[str, list[str]] = {u: [] for u in UNITS_ORDER}
    for k in target_keys:
        for u in MEMBERS_JP[k]["units"]:
            if u in unit_members:
                unit_members[u].append(k)

    # 各期生の内部ペア順位を抽出
    unit_results = {}
    for unit, members in unit_members.items():
        if len(members) < 2:
            continue
        ranks = []
        for ki, kj in combinations(members, 2):
            row = pair_df[((pair_df["i"] == ki) & (pair_df["j"] == kj)) |
                          ((pair_df["i"] == kj) & (pair_df["j"] == ki))]
            if len(row) == 0:
                continue
            r = row.iloc[0]
            ranks.append({
                "name_i": MEMBERS_JP[ki]["name"],
                "name_j": MEMBERS_JP[kj]["name"],
                "jac": r["jac"],
                "rank": int(r["rank"]),
            })
        ranks.sort(key=lambda x: x["rank"])
        unit_results[unit] = ranks
        print(f"\n--- {unit} ({len(members)}名, 内部ペア{len(ranks)}通り) ---")
        for r in ranks:
            print(f"  順位 {r['rank']:>4d}/{total_pairs}: {r['name_i']:8s} × {r['name_j']:8s}  Jaccard {r['jac']*100:.2f}%")

    # =====================================================
    # Markdown 出力
    # =====================================================
    out_md = PLOTS_DIR / "unit_internal_pairs.md"
    with open(out_md, "w", encoding="utf-8") as f:
        f.write("# 期生別ユニット内ペア Jaccard 順位（35名、総ペア595）\n\n")
        f.write("## 活動年数 vs チャット参加率 相関係数\n\n")
        f.write(f"- Pearson  (年数 vs 参加率): r = {r_p:+.3f}, p = {p_p:.4f}\n")
        f.write(f"- Spearman (年数 vs 参加率): ρ = {r_s:+.3f}, p = {p_s:.4f}\n")
        f.write(f"- Pearson  (年数 vs log参加率): r = {r_p_log:+.3f}, p = {p_p_log:.4f}\n\n")
        f.write(f"対数線形フィット: log10(参加率%) = {coef[0]/np.log(10):.3f} × 年数 + {coef[1]/np.log(10):.3f}\n\n")

        f.write("## 期生別ユニット内ペアの順位\n\n")
        for unit, ranks in unit_results.items():
            f.write(f"### {unit}（内部 {len(ranks)} ペア）\n\n")
            f.write("| 全体順位 | タレントA | タレントB | Jaccard |\n")
            f.write("|---:|---|---|---:|\n")
            for r in ranks:
                f.write(f"| {r['rank']}/{total_pairs} | {r['name_i']} | {r['name_j']} | {r['jac']*100:.2f}% |\n")
            f.write("\n")

    print(f"\n保存: {out_md}")


if __name__ == "__main__":
    main()
