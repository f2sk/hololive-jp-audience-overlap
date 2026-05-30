"""
共有率×Jaccard 散布図の3パターン（線形・平坦・逆相関）の3パネル比較図を生成

代表3名:
  - 星街すいせい: 線形パターン（共有率と Jaccard が概ね比例）
  - 桃鈴ねね:     平坦パターン（共有率に対し Jaccard がほぼ一定）
  - 音乃瀬奏:     逆相関パターン（共有率増で Jaccard が下がる）

実行方法:
    python scripts_jp/step12_3pattern_scatter_jp.py

依存:
    pandas, numpy, matplotlib, adjustText
    Python 3.10+

出力:
    data/plots/jp/scatter_3patterns.png
"""

import sys
from itertools import combinations
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from config_jp import DATA_DIR, DATA_DIR_JP, MEMBERS_JP, UNIT_COLOR
from step8_age_analysis_jp import load_subscribers

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

# 規模降順に4名を選定し、2x2 グリッドで「規模効果による同一構造の連続変形」を可視化
# 上段: 大規模ハブ2名（線形パターン）、下段: 中〜小規模2名（平坦・逆相関に見える）
TARGETS = [
    ("marine", "巨大ハブ・線形パターン",   "自身大規模 → 直線性が極めて強い"),
    ("suisei", "大規模ハブ・線形パターン", "自身大規模 → 直線性が高い"),
    ("nene",   "中規模・平坦パターン",     "自身中規模 → 同期生に上振れ、ハブが下振れ"),
    ("kanade", "小規模・逆相関パターン",   "自身小規模 → 規模補正でハブが右下に外れる"),
]


def compute_scatter_data(target_key: str, df: pd.DataFrame, arr: np.ndarray, keys: list[str]):
    """指定タレント視点での 視聴者共有率 × Jaccard × 共視聴者数 を計算"""
    i_t = keys.index(target_key)
    A = arr[:, i_t]
    A_total = int(A.sum())
    rows = []
    for j, k in enumerate(keys):
        if j == i_t:
            continue
        B = arr[:, j]
        inter = int((A & B).sum())
        uni = int((A | B).sum())
        jac = inter / uni if uni > 0 else 0
        share = inter / A_total if A_total > 0 else 0
        rows.append({
            "key":          k,
            "name":         MEMBERS_JP[k]["name"],
            "unit":         MEMBERS_JP[k]["units"][0],
            "jaccard":      jac * 100,
            "share":        share * 100,
            "intersection": inter,
        })
    return rows


def main():
    PLOTS_DIR.mkdir(parents=True, exist_ok=True)
    try:
        from adjustText import adjust_text
        HAS_ADJUST = True
    except ImportError:
        HAS_ADJUST = False
        print("warning: adjustText が見つかりません。ラベル衝突回避は無効化されます。")

    df = pd.read_parquet(MATRIX_PATH)
    keys = [k for k in MEMBERS_JP if k not in EXCLUDED_KEYS and k in df.columns]
    df = df[keys]
    arr = df.values.astype(bool)

    fig, axes = plt.subplots(2, 2, figsize=(18, 14))
    axes_flat = axes.flatten()

    for ax, (tkey, pat_label, pat_desc) in zip(axes_flat, TARGETS):
        if tkey not in keys:
            print(f"スキップ: {tkey} はキーに存在しません")
            continue
        rows = compute_scatter_data(tkey, df, arr, keys)
        target_name = MEMBERS_JP[tkey]["name"]

        max_inter = max(r["intersection"] for r in rows)
        min_inter = min(r["intersection"] for r in rows)
        texts, xs, ys = [], [], []
        for r in rows:
            color = UNIT_COLOR.get(r["unit"], "#888")
            size = 80 + (r["intersection"] - min_inter) / (max_inter - min_inter + 1e-9) * 1000
            ax.scatter(r["share"], r["jaccard"], s=size, c=color,
                       alpha=0.7, edgecolor="black", linewidth=0.5, zorder=3)
            t = ax.annotate(r["name"], (r["share"], r["jaccard"]),
                            fontsize=11, fontweight="bold", alpha=0.95, zorder=4)
            texts.append(t)
            xs.append(r["share"])
            ys.append(r["jaccard"])

        # Pearson r を計算してパターン判定に説得力を加える
        x_arr = np.array(xs); y_arr = np.array(ys)
        r = float(np.corrcoef(x_arr, y_arr)[0, 1])

        ax.set_xlim(0, max(xs) * 1.15)
        ax.set_ylim(0, max(ys) * 1.20)
        ax.set_xlabel(f"{target_name} 視点 視聴者共有率（%）", fontsize=13)
        ax.set_ylabel("Jaccard 係数（%）", fontsize=13)
        ax.set_title(f"{target_name}: {pat_label}\n{pat_desc}（Pearson r = {r:+.2f}）",
                     fontsize=14, fontweight="bold")
        ax.tick_params(axis="both", labelsize=11)
        ax.grid(alpha=0.3, zorder=0)

        if HAS_ADJUST:
            adjust_text(texts, xs, ys, ax=ax,
                        expand_points=(1.3, 1.3), expand_text=(1.1, 1.2),
                        arrowprops=dict(arrowstyle="-", color="#888", lw=0.4, alpha=0.5))

    # 共通凡例
    legend_patches = [mpatches.Patch(color=col, label=u) for u, col in UNIT_COLOR.items()]
    fig.legend(handles=legend_patches, loc="lower center", ncol=10, fontsize=11,
               bbox_to_anchor=(0.5, 0.00))

    fig.suptitle(
        "視聴者共有率 × Jaccard 散布図の規模効果による連続変形（マーカーサイズ = 共視聴者数）",
        fontsize=16, fontweight="bold", y=0.99,
    )
    fig.tight_layout(rect=[0, 0.04, 1, 0.96])
    out = PLOTS_DIR / "scatter_3patterns.png"
    fig.savefig(out, dpi=140, bbox_inches="tight")
    plt.close(fig)
    print(f"保存: {out}")


if __name__ == "__main__":
    main()
