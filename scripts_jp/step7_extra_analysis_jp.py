"""
追加分析（JP 35名版）

matrix_jp.parquet から以下の3分析を実行:
1. 複推し数分布ヒストグラム (各ユーザーが何人のタレントに参加しているかの分布)
2. 高重複2人組ランキング（Jaccard上位N組）
3. 期生跨ぎ高重複2人組（運営定義期生と異なる高重複ペア）

実行方法:
    python scripts_jp/step7_extra_analysis_jp.py

出力:
    data/plots/jp/multitalent_hist.png
    data/plots/jp/top_pairs.md
"""

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

matplotlib.use("Agg")
matplotlib.rcParams["axes.unicode_minus"] = False

# Python 3.14 deepcopy 無限再帰回避
import copy as _copy
import matplotlib.path as _mpath
def _path_deepcopy_fix(self, memo):
    result = object.__new__(type(self))
    memo[id(self)] = result
    result.__dict__.update(_copy.deepcopy(self.__dict__, memo))
    return result
_mpath.Path.__deepcopy__ = _path_deepcopy_fix
_JP_FONTS = ["Yu Gothic", "Meiryo", "MS Gothic", "IPAexGothic"]
_available = {f.name for f in fm.fontManager.ttflist}
for _f in _JP_FONTS:
    if _f in _available:
        matplotlib.rcParams["font.family"] = _f
        break

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

MATRIX_PATH = Path(DATA_DIR) / "matrix_jp.parquet"
PLOTS_DIR   = Path(DATA_DIR_JP)

EXCLUDED_KEYS = {"choco", "laplus", "niko"}


def main():
    PLOTS_DIR.mkdir(parents=True, exist_ok=True)

    df = pd.read_parquet(MATRIX_PATH)
    target_keys = [k for k in MEMBERS_JP if k not in EXCLUDED_KEYS and k in df.columns]
    df = df[target_keys]
    print(f"分析対象: {len(target_keys)} 名 × {df.shape[0]:,} ユーザー\n")

    # =================================================================
    # B-1: 複推し数分布ヒストグラム
    # =================================================================
    print("=== B-1: 複推し数分布 ===")
    multitalent_count = df.sum(axis=1).values  # 各ユーザーの参加タレント数
    dist = pd.Series(multitalent_count).value_counts().sort_index()
    print("参加タレント数 → 人数 (%):")
    total = len(multitalent_count)
    cumulative = 0
    for n_t, n_users in dist.items():
        pct = n_users / total * 100
        cumulative += pct
        marker = "  累計100%" if int(n_t) >= 8 else ""
        print(f"  {int(n_t):2d}人: {n_users:6,} ({pct:5.2f}%)  [累計{cumulative:5.1f}%]")

    # 散布バー（1〜35タレント参加）
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

    # 通常スケール
    x = dist.index.values.astype(int)
    y = dist.values
    ax1.bar(x, y, color="#4C72B0", width=0.7)
    ax1.set_xlabel("参加タレント数")
    ax1.set_ylabel("人数")
    ax1.set_title(f"ホロライブJP 35名 複推し数分布（通常スケール、N={total:,}）")
    ax1.set_xticks(np.arange(1, x.max() + 1, max(1, x.max() // 18)))
    ax1.grid(axis="y", alpha=0.3)

    # 対数スケール（少数派の挙動を見やすく）
    ax2.bar(x, y, color="#C44E52", width=0.7)
    ax2.set_xlabel("参加タレント数")
    ax2.set_ylabel("人数（対数）")
    ax2.set_yscale("log")
    ax2.set_title("対数スケール")
    ax2.set_xticks(np.arange(1, x.max() + 1, max(1, x.max() // 18)))
    ax2.grid(axis="y", alpha=0.3, which="both")

    fig.tight_layout()
    out = PLOTS_DIR / "multitalent_hist.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"保存: {out}\n")

    # =================================================================
    # B-2: 高重複2人組ランキング
    # =================================================================
    print("=== B-2: 高重複2人組ランキング（Jaccard上位30）===")

    # 共起行列
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
        k_i, k_j = target_keys[i], target_keys[j]
        u_i = MEMBERS_JP[k_i]["units"][0]
        u_j = MEMBERS_JP[k_j]["units"][0]
        # ホロライブJP本体（0〜6期生+ゲーマーズ）かDEV_IS（ReGLOSS/FLOW GLOW）か
        is_devis_i = u_i in ("ReGLOSS", "FLOW GLOW")
        is_devis_j = u_j in ("ReGLOSS", "FLOW GLOW")
        # 同所属判定: フブキの両所属を考慮
        units_i = set(MEMBERS_JP[k_i]["units"])
        units_j = set(MEMBERS_JP[k_j]["units"])
        same_unit = bool(units_i & units_j)
        cross_jp_devis = is_devis_i != is_devis_j
        pairs.append({
            "name_i":     MEMBERS_JP[k_i]["name"],
            "name_j":     MEMBERS_JP[k_j]["name"],
            "unit_i":     u_i,
            "unit_j":     u_j,
            "jaccard":    jac,
            "cooccur":    c,
            "u_i":        diag[i],
            "u_j":        diag[j],
            "same_unit":  same_unit,
            "cross_jp_devis": cross_jp_devis,
        })

    pair_df = pd.DataFrame(pairs).sort_values("jaccard", ascending=False)
    print(f"\n総ペア数: {len(pair_df):,}")
    print(f"\n上位30ペア:")
    print(f"{'#':>3} {'タレントA':10s} {'タレントB':10s} {'A所属':10s} {'B所属':10s} {'Jacc':>6s} {'共視':>7s} {'同ユニ':>4s}")
    for i, r in pair_df.head(30).reset_index(drop=True).iterrows():
        same_mark = "Y" if r["same_unit"] else " "
        print(f"{i+1:>3} {r['name_i']:10s} {r['name_j']:10s} {r['unit_i']:10s} {r['unit_j']:10s} "
              f"{r['jaccard']*100:>5.2f}% {int(r['cooccur']):>7,} {same_mark:>4s}")

    # =================================================================
    # B-3: 期生跨ぎ高重複2人組（同ユニットでないペアの中で高いもの）
    # =================================================================
    print("\n=== B-3: 期生跨ぎ高重複ペア（同ユニットでない上位30）===")
    cross_df = pair_df[~pair_df["same_unit"]].head(30).reset_index(drop=True)
    print(f"{'#':>3} {'タレントA':10s} {'タレントB':10s} {'A所属':10s} {'B所属':10s} {'Jacc':>6s} {'共視':>7s}")
    for i, r in cross_df.iterrows():
        print(f"{i+1:>3} {r['name_i']:10s} {r['name_j']:10s} {r['unit_i']:10s} {r['unit_j']:10s} "
              f"{r['jaccard']*100:>5.2f}% {int(r['cooccur']):>7,}")

    # =================================================================
    # Markdown 出力
    # =================================================================
    out_md = PLOTS_DIR / "top_pairs.md"
    with open(out_md, "w", encoding="utf-8") as f:
        f.write("# 追加分析: 複推し数分布 & 高重複ペア（JP 35名）\n\n")

        f.write("## 複推し数分布\n\n")
        f.write("各ユーザーが何人のタレントの配信にチャット参加したかの分布。\n\n")
        f.write("| 参加タレント数 | 人数 | 全体比 | 累計 |\n")
        f.write("|---:|---:|---:|---:|\n")
        cum = 0.0
        for n_t, n_users in dist.items():
            pct = n_users / total * 100
            cum += pct
            f.write(f"| {int(n_t)} | {n_users:,} | {pct:.2f}% | {cum:.1f}% |\n")
        f.write(f"\n総ユーザー数: **{total:,}**\n\n")

        f.write("## 高重複2人組ランキング（Jaccard上位30）\n\n")
        f.write("| # | タレントA | タレントB | A所属 | B所属 | Jaccard | 共視聴者数 | 同ユニット |\n")
        f.write("|---:|---|---|---|---|---:|---:|:---:|\n")
        for i, r in pair_df.head(30).reset_index(drop=True).iterrows():
            same_mark = "✓" if r["same_unit"] else ""
            f.write(f"| {i+1} | {r['name_i']} | {r['name_j']} | {r['unit_i']} | {r['unit_j']} "
                    f"| {r['jaccard']*100:.2f}% | {int(r['cooccur']):,} | {same_mark} |\n")

        f.write("\n## 期生跨ぎ高重複ペア（同ユニットでない上位30）\n\n")
        f.write("運営定義の所属ユニットを跨いで高い視聴者重複を示すペア。\n\n")
        f.write("| # | タレントA | タレントB | A所属 | B所属 | Jaccard | 共視聴者数 |\n")
        f.write("|---:|---|---|---|---|---:|---:|\n")
        for i, r in cross_df.iterrows():
            f.write(f"| {i+1} | {r['name_i']} | {r['name_j']} | {r['unit_i']} | {r['unit_j']} "
                    f"| {r['jaccard']*100:.2f}% | {int(r['cooccur']):,} |\n")

    print(f"\n保存: {out_md}")


if __name__ == "__main__":
    main()
