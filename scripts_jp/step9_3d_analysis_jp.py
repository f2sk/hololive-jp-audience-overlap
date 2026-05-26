"""
活動年数・登録者数・チャット参加率の3次元相関分析（JP 35名版）

出力:
    data/plots/jp/bubble_chart.png     - バブルチャート（年数×参加率、サイズ=登録者数）
    data/plots/jp/3d_scatter.png       - 3D散布図
    data/plots/jp/regression_jp.md     - 重回帰・偏相関の結果
"""

import sys
from datetime import date
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from matplotlib.lines import Line2D
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401
import numpy as np
import pandas as pd
from scipy.stats import pearsonr

sys.path.insert(0, str(Path(__file__).parent))
from config_jp import DATA_DIR, DATA_DIR_JP, MEMBERS_JP, UNIT_COLOR
from step8_age_analysis_jp import DEBUT_DATE, ANALYSIS_DATE, years_since_debut, load_subscribers

matplotlib.use("Agg")
matplotlib.rcParams["axes.unicode_minus"] = False
_JP_FONTS = ["Yu Gothic", "Meiryo", "MS Gothic", "IPAexGothic"]
_available = {f.name for f in fm.fontManager.ttflist}
for _f in _JP_FONTS:
    if _f in _available:
        matplotlib.rcParams["font.family"] = _f
        break

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
PLOTS_DIR   = Path(DATA_DIR_JP)
EXCLUDED_KEYS = {"choco", "laplus", "niko"}


def partial_correlation(x, y, z):
    """zを統制した x と y の偏相関係数（Pearson r_{xy.z}）"""
    rxy, _ = pearsonr(x, y)
    rxz, _ = pearsonr(x, z)
    ryz, _ = pearsonr(y, z)
    denom = np.sqrt((1 - rxz**2) * (1 - ryz**2))
    return (rxy - rxz * ryz) / denom if denom > 0 else np.nan


def main():
    PLOTS_DIR.mkdir(parents=True, exist_ok=True)

    df = pd.read_parquet(MATRIX_PATH)
    target_keys = [k for k in MEMBERS_JP if k not in EXCLUDED_KEYS and k in df.columns]
    df = df[target_keys]
    subs = load_subscribers()

    rows = []
    for key in target_keys:
        unique = int(df[key].sum())
        s = subs.get(key, 0)
        rows.append({
            "key":    key,
            "name":   MEMBERS_JP[key]["name"],
            "unit":   MEMBERS_JP[key]["units"][0],
            "years":  years_since_debut(key),
            "subs":   s,
            "unique": unique,
            "rate":   unique / s if s > 0 else 0,
        })
    rate_df = pd.DataFrame(rows)
    rate_df["log_rate"]   = np.log10(rate_df["rate"].clip(lower=1e-6))
    rate_df["log_subs"]   = np.log10(rate_df["subs"].clip(lower=1))
    rate_df["log_unique"] = np.log10(rate_df["unique"].clip(lower=1))

    # =====================================================
    # 1. 相関係数・偏相関係数
    # =====================================================
    print("=== 相関係数 (Pearson) ===")
    pairs = [
        ("years", "rate"),
        ("years", "log_rate"),
        ("years", "subs"),
        ("years", "log_subs"),
        ("subs", "rate"),
        ("log_subs", "log_rate"),
        ("subs", "unique"),
        ("log_subs", "log_unique"),
        ("years", "log_unique"),
    ]
    pearson_results = {}
    for x_col, y_col in pairs:
        r, p = pearsonr(rate_df[x_col], rate_df[y_col])
        print(f"  {x_col:>10s} vs {y_col:<10s}  r = {r:+.3f}, p = {p:.4f}")
        pearson_results[(x_col, y_col)] = (r, p)

    print("\n=== 偏相関（zを統制した x と y、リニア空間）===")
    partial_results = []
    partials = [
        ("活動年数 vs 参加率 | 登録者数を統制", "years", "rate", "subs"),
        ("登録者数 vs 参加率 | 活動年数を統制", "subs", "rate", "years"),
        ("活動年数 vs 登録者数 | 参加率を統制", "years", "subs", "rate"),
    ]
    for label, x_col, y_col, z_col in partials:
        r = partial_correlation(rate_df[x_col], rate_df[y_col], rate_df[z_col])
        print(f"  {label}: r = {r:+.3f}")
        partial_results.append((label, r))

    # =====================================================
    # 2. 重回帰: 参加率(%) ~ 年数 + 登録者数(万人)（リニア空間）
    # =====================================================
    print("\n=== 重回帰: 参加率(%) = a × 年数 + b × 登録者数(万人) + c ===")
    # 単位を分かりやすく: 参加率は%(0-2程度)、登録者数は万人(10-500程度)
    rate_pct = rate_df["rate"].values * 100
    subs_man = rate_df["subs"].values / 10000
    X = np.column_stack([rate_df["years"].values, subs_man, np.ones(len(rate_df))])
    coef, _, _, _ = np.linalg.lstsq(X, rate_pct, rcond=None)
    a, b, c = coef
    yhat = X @ coef
    r2 = 1 - np.sum((rate_pct - yhat)**2) / np.sum((rate_pct - rate_pct.mean())**2)
    print(f"  a (年数係数):       {a:+.5f} (%/年)")
    print(f"  b (登録者係数):     {b:+.6f} (%/万人)")
    print(f"  c (定数項):         {c:+.4f} (%)")
    print(f"  R²:                 {r2:.4f}")

    print("\n=== 重回帰: log(unique参加数) = a × 年数 + b × log(登録者数) + c ===")
    X2 = np.column_stack([rate_df["years"], rate_df["log_subs"], np.ones(len(rate_df))])
    y2 = rate_df["log_unique"].values
    coef2, _, _, _ = np.linalg.lstsq(X2, y2, rcond=None)
    a2, b2, c2 = coef2
    yhat2 = X2 @ coef2
    r2_2 = 1 - np.sum((y2 - yhat2)**2) / np.sum((y2 - y2.mean())**2)
    print(f"  a (年数係数):      {a2:+.4f}")
    print(f"  b (log登録者係数): {b2:+.4f}")
    print(f"  c (定数項):        {c2:+.4f}")
    print(f"  R²:                {r2_2:.4f}")

    # =====================================================
    # 3. バブルチャート（X=年数, Y=参加率(log), マーカーサイズ=登録者数）
    # =====================================================
    fig, ax = plt.subplots(figsize=(16, 11))

    # 登録者数を 300px〜3500px の範囲にマップ（フォント拡大に合わせバブルも拡大）
    s_min, s_max = rate_df["subs"].min(), rate_df["subs"].max()
    size_arr = 300 + (rate_df["subs"] - s_min) / (s_max - s_min) * 3200

    for unit, color in UNIT_COLOR.items():
        sub = rate_df[rate_df["unit"] == unit]
        if len(sub) == 0:
            continue
        sizes = 300 + (sub["subs"] - s_min) / (s_max - s_min) * 3200
        # label を空にしてscatter自身は凡例から外す（後で固定サイズで凡例追加）
        ax.scatter(sub["years"], sub["rate"] * 100, s=sizes, c=color,
                   alpha=0.6, edgecolor="black", linewidth=0.8, zorder=3)

    for _, r in rate_df.iterrows():
        ax.annotate(r["name"], (r["years"], r["rate"] * 100),
                    fontsize=18, alpha=1.0, fontweight="bold",
                    xytext=(10, 7), textcoords="offset points")

    # 線形フィット（年数のみ）
    coef_simple = np.polyfit(rate_df["years"], rate_df["rate"] * 100, 1)
    a_simple, b_simple = coef_simple
    xs = np.linspace(rate_df["years"].min() - 0.3, rate_df["years"].max() + 0.3, 100)
    ys = np.polyval(coef_simple, xs)
    fit_line, = ax.plot(xs, ys, "--", color="#555555", linewidth=2.0, alpha=0.7, zorder=2)

    ax.set_xlabel("活動年数（年、デビューから 2026-05-25 時点）", fontsize=22)
    ax.set_ylabel("チャット参加率（%）", fontsize=22)
    ax.tick_params(axis="both", labelsize=18)
    ax.set_title(
        f"活動年数 × チャット参加率 × 登録者数（バブル径=登録者数 47〜436万）\n"
        f"重回帰 R² = {r2:.3f} （参加率(%) = {a:+.3f}×年数 {b:+.5f}×登録者(万人) + 定数）",
        fontsize=22, fontweight="bold",
    )
    ax.grid(alpha=0.3)

    # 凡例: 固定サイズマーカー（データ点のサイズと独立）
    legend_handles = [
        Line2D([0], [0], marker="o", color="w", markerfacecolor=color,
               markeredgecolor="black", markeredgewidth=0.5,
               markersize=14, alpha=0.8, label=unit)
        for unit, color in UNIT_COLOR.items()
    ]
    legend_handles.append(
        Line2D([0], [0], color="#555555", linestyle="--", linewidth=2.0,
               label=f"線形フィット（年数のみ） y={a_simple:.3f}x+{b_simple:.3f}")
    )
    ax.legend(handles=legend_handles, fontsize=17, loc="lower left", ncol=2)
    fig.tight_layout()
    out_bubble = PLOTS_DIR / "bubble_chart.png"
    fig.savefig(out_bubble, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"\n保存: {out_bubble}")

    # =====================================================
    # 4. Markdown 出力
    # =====================================================
    out_md = PLOTS_DIR / "regression_jp.md"
    with open(out_md, "w", encoding="utf-8") as f:
        f.write("# 3次元相関分析（活動年数 × 登録者数 × チャット参加率、35名）\n\n")

        f.write("## 単純相関（Pearson）\n\n")
        f.write("| X | Y | r | p |\n|---|---|---:|---:|\n")
        for (x_col, y_col), (r, p) in pearson_results.items():
            f.write(f"| {x_col} | {y_col} | {r:+.3f} | {p:.4f} |\n")

        f.write("\n## 偏相関（zを統制）\n\n")
        f.write("| 関係 | r |\n|---|---:|\n")
        for label, r in partial_results:
            f.write(f"| {label} | {r:+.3f} |\n")

        f.write("\n## 重回帰\n\n")
        f.write(f"**log(参加率) = {a:+.4f}×年数 + {b:+.4f}×log(登録者数) + {c:+.4f}**, R² = {r2:.4f}\n\n")
        f.write(f"**log(ユニーク参加数) = {a2:+.4f}×年数 + {b2:+.4f}×log(登録者数) + {c2:+.4f}**, R² = {r2_2:.4f}\n\n")

        f.write("## データ\n\n")
        f.write("| タレント | 期生 | 活動年数 | 登録者数 | ユニーク参加 | 参加率 |\n")
        f.write("|---|---|---:|---:|---:|---:|\n")
        for _, r in rate_df.sort_values("years").iterrows():
            f.write(f"| {r['name']} | {r['unit']} | {r['years']:.2f}年 "
                    f"| {int(r['subs']):,} | {int(r['unique']):,} | {r['rate']*100:.2f}% |\n")

    print(f"保存: {out_md}")


if __name__ == "__main__":
    main()
