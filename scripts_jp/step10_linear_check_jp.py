"""
活動年数 vs チャット参加率: リニアスケール vs 対数スケールの比較
"""
import sys
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from matplotlib.lines import Line2D
import numpy as np
import pandas as pd
from scipy.stats import pearsonr

sys.path.insert(0, str(Path(__file__).parent))
from config_jp import DATA_DIR, DATA_DIR_JP, MEMBERS_JP, UNIT_COLOR
from step8_age_analysis_jp import DEBUT_DATE, years_since_debut, load_subscribers

matplotlib.use("Agg")
_JP_FONTS = ["Yu Gothic", "Meiryo", "MS Gothic"]
_av = {f.name for f in fm.fontManager.ttflist}
for _f in _JP_FONTS:
    if _f in _av:
        matplotlib.rcParams["font.family"] = _f
        break

import copy as _copy
import matplotlib.path as _mpath
def _fix(self, memo):
    r = object.__new__(type(self)); memo[id(self)] = r
    r.__dict__.update(_copy.deepcopy(self.__dict__, memo)); return r
_mpath.Path.__deepcopy__ = _fix

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

MATRIX_PATH = Path(DATA_DIR) / "matrix_jp.parquet"
PLOTS_DIR   = Path(DATA_DIR_JP)
EXCLUDED_KEYS = {"choco", "laplus", "niko"}


def main():
    df = pd.read_parquet(MATRIX_PATH)
    target_keys = [k for k in MEMBERS_JP if k not in EXCLUDED_KEYS and k in df.columns]
    subs = load_subscribers()
    rows = []
    for k in target_keys:
        unique = int(df[k].sum()); s = subs.get(k, 0)
        rows.append({"name": MEMBERS_JP[k]["name"], "unit": MEMBERS_JP[k]["units"][0],
                     "years": years_since_debut(k), "subs": s,
                     "rate": (unique / s if s > 0 else 0) * 100})
    d = pd.DataFrame(rows)
    x, y = d["years"].values, d["rate"].values
    log_y = np.log(y)

    # ---- 線形フィット (y = a*x + b) ----
    coef_lin = np.polyfit(x, y, 1); a_lin, b_lin = coef_lin
    y_pred_lin = np.polyval(coef_lin, x)
    r2_lin = 1 - np.sum((y - y_pred_lin)**2) / np.sum((y - y.mean())**2)
    r_lin, p_lin = pearsonr(x, y)
    rmse_lin = np.sqrt(np.mean((y - y_pred_lin)**2))

    # ---- 指数フィット (log y = a*x + b → y = exp(b) * exp(a*x)) ----
    coef_exp = np.polyfit(x, log_y, 1); a_exp, b_exp = coef_exp
    y_pred_exp = np.exp(np.polyval(coef_exp, x))
    r2_exp = 1 - np.sum((y - y_pred_exp)**2) / np.sum((y - y.mean())**2)  # リニア空間での R²
    r2_exp_logspace = 1 - np.sum((log_y - np.polyval(coef_exp, x))**2) / np.sum((log_y - log_y.mean())**2)
    r_exp, p_exp = pearsonr(x, log_y)
    rmse_exp = np.sqrt(np.mean((y - y_pred_exp)**2))

    print("=== 線形フィット y = a*x + b ===")
    print(f"  a={a_lin:+.4f}, b={b_lin:+.4f}")
    print(f"  Pearson r (年数 vs 参加率): {r_lin:+.4f} (p={p_lin:.4f})")
    print(f"  R² (リニア空間): {r2_lin:.4f}")
    print(f"  RMSE (リニア空間): {rmse_lin:.4f} %")
    print()
    print("=== 指数フィット y = exp(b) * exp(a*x) ===")
    print(f"  a={a_exp:+.4f}, b={b_exp:+.4f}  ->  y = {np.exp(b_exp):.4f} * exp({a_exp:+.4f}*x)")
    print(f"  Pearson r (年数 vs log参加率): {r_exp:+.4f} (p={p_exp:.4f})")
    print(f"  R² (リニア空間で評価): {r2_exp:.4f}")
    print(f"  R² (log空間で評価): {r2_exp_logspace:.4f}")
    print(f"  RMSE (リニア空間): {rmse_exp:.4f} %")
    print()
    print(f"=== 残差比較（リニア空間でのRMSE）===")
    print(f"  線形フィット: {rmse_lin:.4f} %")
    print(f"  指数フィット: {rmse_exp:.4f} %")
    print(f"  → {'線形' if rmse_lin < rmse_exp else '指数'} フィットの方が当てはまりが良い")

    # ---- プロット: リニアスケール vs 対数スケール 並列 ----
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 7))

    for unit, color in UNIT_COLOR.items():
        sub = d[d["unit"] == unit]
        if len(sub) == 0: continue
        ax1.scatter(sub["years"], sub["rate"], s=80, c=color,
                    alpha=0.8, edgecolor="black", linewidth=0.5)
        ax2.scatter(sub["years"], sub["rate"], s=80, c=color,
                    alpha=0.8, edgecolor="black", linewidth=0.5)

    xs = np.linspace(x.min() - 0.3, x.max() + 0.3, 100)

    # リニアフィット線
    ys_lin = np.polyval(coef_lin, xs)
    # 指数フィット線
    ys_exp = np.exp(np.polyval(coef_exp, xs))

    ax1.plot(xs, ys_lin, "-", color="#0066cc", linewidth=2, alpha=0.8,
             label=f"線形 y={a_lin:.3f}x+{b_lin:.3f} (R²={r2_lin:.3f})")
    ax1.plot(xs, ys_exp, "--", color="#cc3333", linewidth=2, alpha=0.8,
             label=f"指数 R²={r2_exp:.3f}")
    ax1.set_xlabel("活動年数（年）", fontsize=11)
    ax1.set_ylabel("チャット参加率（%）", fontsize=11)
    ax1.set_title(f"リニアスケール (Pearson r={r_lin:.3f})", fontsize=12, fontweight="bold")
    ax1.grid(alpha=0.3)
    ax1.legend(fontsize=9, loc="upper right")
    for _, r in d.iterrows():
        ax1.annotate(r["name"], (r["years"], r["rate"]),
                     fontsize=6, alpha=0.7, xytext=(4, 3), textcoords="offset points")

    ax2.plot(xs, ys_lin, "-", color="#0066cc", linewidth=2, alpha=0.8,
             label=f"線形")
    ax2.plot(xs, ys_exp, "--", color="#cc3333", linewidth=2, alpha=0.8,
             label=f"指数 (R²={r2_exp_logspace:.3f} log空間)")
    ax2.set_xlabel("活動年数（年）", fontsize=11)
    ax2.set_ylabel("チャット参加率（%、対数スケール）", fontsize=11)
    ax2.set_yscale("log")
    ax2.set_title(f"対数スケール (Pearson r={r_exp:.3f} on log参加率)", fontsize=12, fontweight="bold")
    ax2.grid(alpha=0.3, which="both")
    ax2.legend(fontsize=9, loc="upper right")
    for _, r in d.iterrows():
        ax2.annotate(r["name"], (r["years"], r["rate"]),
                     fontsize=6, alpha=0.7, xytext=(4, 3), textcoords="offset points")

    # ユニット凡例（共通）
    legend_handles = [
        Line2D([0], [0], marker="o", color="w", markerfacecolor=color,
               markeredgecolor="black", markersize=8, label=u)
        for u, color in UNIT_COLOR.items()
    ]
    fig.legend(handles=legend_handles, loc="lower center", ncol=10, fontsize=8,
               bbox_to_anchor=(0.5, -0.02))

    fig.tight_layout()
    out = PLOTS_DIR / "linear_vs_log_check.png"
    fig.savefig(out, dpi=130, bbox_inches="tight")
    plt.close()
    print(f"\n保存: {out}")


if __name__ == "__main__":
    main()
