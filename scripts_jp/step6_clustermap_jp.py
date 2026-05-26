"""
Jaccard係数による階層クラスタリング順ヒートマップ（JP 35名版）

タレント間のJaccard距離 (1 - Jaccard) に対して階層クラスタリング (average linkage) を適用し、
デンドログラム順に並べ替えたヒートマップを生成する。

実行方法:
    python scripts_jp/step6_clustermap_jp.py

出力:
    data/plots/jp/overlap_clustermap.png  - クラスタマップ + デンドログラム

依存ライブラリ: pandas, pyarrow, matplotlib, numpy, scipy
Python: 3.8+
"""

import copy
import sys
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.font_manager as fm
import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import linkage, dendrogram
from scipy.spatial.distance import squareform

sys.path.insert(0, str(Path(__file__).parent))
from config_jp import DATA_DIR, DATA_DIR_JP, MEMBERS_JP, UNIT_COLOR

matplotlib.use("Agg")
matplotlib.rcParams["axes.unicode_minus"] = False

# Python 3.14 deepcopy 無限再帰回避
import matplotlib.path as _mpath
def _path_deepcopy_fix(self, memo):
    result = object.__new__(type(self))
    memo[id(self)] = result
    result.__dict__.update(copy.deepcopy(self.__dict__, memo))
    return result
_mpath.Path.__deepcopy__ = _path_deepcopy_fix

# Windows 日本語フォント
_JP_FONTS = ["Yu Gothic", "Meiryo", "MS Gothic", "IPAexGothic"]
_available = {f.name for f in fm.fontManager.ttflist}
for _f in _JP_FONTS:
    if _f in _available:
        matplotlib.rcParams["font.family"] = _f
        break

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

MATRIX_PATH = Path(DATA_DIR) / "matrix_jp.parquet"
PLOTS_DIR   = Path(DATA_DIR_JP)

# 分析対象外（step1 件数不足）
EXCLUDED_KEYS = {"choco", "laplus", "niko"}

# 表示用短名（35名）
SHORT_NAMES = {
    "sora":     "そら",
    "roboco":   "ロボ子",
    "azki":     "AZKi",
    "suisei":   "すいせい",
    "miko":     "みこ",
    "fubuki":   "フブキ",
    "matsuri":  "まつり",
    "aki":      "アキ",
    "ayame":    "あやめ",
    "subaru":   "スバル",
    "mio":      "ミオ",
    "okayu":    "おかゆ",
    "korone":   "ころね",
    "pekora":   "ぺこら",
    "flare":    "フレア",
    "noel":     "ノエル",
    "marine":   "マリン",
    "watame":   "わため",
    "towa":     "トワ",
    "luna":     "ルーナ",
    "lamy":     "ラミィ",
    "nene":     "ねね",
    "botan":    "ぼたん",
    "polka":    "ポルカ",
    "lui":      "ルイ",
    "koyori":   "こより",
    "iroha":    "いろは",
    "kanade":   "奏",
    "ririka":   "莉々華",
    "raden":    "らでん",
    "hajime":   "はじめ",
    "riona":    "リオナ",
    "su":       "枢",
    "chihaya":  "千速",
    "vivi":     "ヴィヴィ",
}

LINKAGE_METHOD = "average"


def load_matrix() -> pd.DataFrame:
    df = pd.read_parquet(MATRIX_PATH)
    keys = [k for k in MEMBERS_JP if k not in EXCLUDED_KEYS and k in df.columns]
    return df[keys]


def co_matrix(df: pd.DataFrame) -> np.ndarray:
    arr = df.values.astype(np.int32)
    return arr.T @ arr


def jaccard_matrix(C: np.ndarray) -> np.ndarray:
    n = C.shape[0]
    diag = np.diag(C).astype(float)
    J = np.zeros((n, n), dtype=float)
    for i in range(n):
        for j in range(n):
            if i == j:
                J[i, j] = np.nan
            else:
                denom = diag[i] + diag[j] - C[i, j]
                J[i, j] = C[i, j] / denom if denom > 0 else 0.0
    return J


def compute_linkage(J: np.ndarray) -> np.ndarray:
    D = 1.0 - np.nan_to_num(J, nan=1.0)
    np.fill_diagonal(D, 0.0)
    condensed = squareform(D, checks=False)
    Z = linkage(condensed, method=LINKAGE_METHOD)
    return Z


def plot_clustermap(J: np.ndarray, C: np.ndarray, keys: list[str], out_path: Path):
    n = len(keys)
    labels = [SHORT_NAMES.get(k, k) for k in keys]
    units  = [MEMBERS_JP[k]["units"][0] for k in keys]

    Z = compute_linkage(J)
    dendro = dendrogram(Z, no_plot=True)
    order = dendro["leaves"]

    J_pct  = J * 100.0
    J_ord  = J_pct[np.ix_(order, order)]
    diag_ord = np.diag(C)[order]
    labels_ord = [labels[i] for i in order]
    units_ord  = [units[i]  for i in order]
    keys_ord   = [keys[i]   for i in order]

    # 35x35 サイズ調整
    fig = plt.figure(figsize=(15, 15.5))
    gs = fig.add_gridspec(
        nrows=2, ncols=2,
        width_ratios=[20, 1],
        height_ratios=[1, 6],
        hspace=0.05, wspace=0.05,
    )
    ax_dendro = fig.add_subplot(gs[0, 0])
    ax_heat   = fig.add_subplot(gs[1, 0])
    ax_cbar   = fig.add_subplot(gs[1, 1])

    icoord = np.array(dendro["icoord"])
    dcoord = np.array(dendro["dcoord"]).copy()
    icoord_norm = (icoord - 5.0) / 10.0

    d_positive = dcoord[dcoord > 0]
    d_min, d_max = d_positive.min(), dcoord.max()
    leaf_margin = (d_max - d_min) * 0.4
    leaf_y = d_min - leaf_margin
    dcoord = np.where(dcoord == 0, leaf_y, dcoord)

    for xs, ys in zip(icoord_norm, dcoord):
        ax_dendro.plot(xs, ys, color="#333333", linewidth=1.2)

    ax_dendro.set_xlim(-0.5, n - 0.5)
    top_margin = (d_max - d_min) * 0.1
    ax_dendro.set_ylim(leaf_y - leaf_margin * 0.2, d_max + top_margin)
    ax_dendro.set_xticks([])
    ax_dendro.set_yticks([])
    for side in ("top", "right", "bottom"):
        ax_dendro.spines[side].set_visible(False)
    ax_dendro.spines["left"].set_color("#cccccc")
    ax_dendro.set_ylabel("距離 (1−J)", fontsize=14, color="#888888")

    im = ax_heat.imshow(J_ord, cmap="YlOrRd", aspect="equal")
    ax_heat.set_xlim(-0.5, n - 0.5)
    ax_heat.set_ylim(n - 0.5, -0.5)

    cbar = fig.colorbar(im, cax=ax_cbar)
    cbar.set_label("Jaccard係数（%）", fontsize=18)
    cbar.ax.tick_params(labelsize=14)

    ax_heat.set_xticks(range(n))
    ax_heat.set_yticks(range(n))
    ax_heat.set_xticklabels(labels_ord, fontsize=16, rotation=90)
    ax_heat.set_yticklabels(labels_ord, fontsize=16)
    ax_heat.xaxis.set_ticks_position("top")
    ax_heat.xaxis.set_label_position("top")
    ax_heat.yaxis.set_ticks_position("left")
    ax_heat.tick_params(axis="x", bottom=False, labelbottom=False)
    ax_heat.tick_params(axis="y", right=False, labelright=False)

    # 35x35はテキスト省略（セルが小さすぎる）。対角線のみ参加者数表示
    vmax = np.nanmax(J_ord)
    for i in range(n):
        ax_heat.text(i, i, f"{diag_ord[i]/1000:.1f}k", ha="center", va="center",
                     fontsize=11, color="#aaaaaa", fontweight="bold")

    # ラベル色分け
    for i, (lbl, unit) in enumerate(zip(labels_ord, units_ord)):
        color = UNIT_COLOR.get(unit, "#666")
        xt = ax_heat.get_xticklabels()[i]
        yt = ax_heat.get_yticklabels()[i]
        for t in (xt, yt):
            t.set_color(color)
            t.set_fontweight("bold")

    # 凡例（10ユニット）
    legend_patches = [
        mpatches.Patch(color=col, label=u) for u, col in UNIT_COLOR.items()
    ]
    ax_heat.legend(
        handles=legend_patches, loc="upper right",
        bbox_to_anchor=(1.0, -0.02), ncol=5, fontsize=16,
    )

    fig.suptitle(
        f"ホロライブJP 35名 Jaccard係数 クラスタマップ（階層クラスタリング順, {LINKAGE_METHOD} linkage）",
        fontsize=22, fontweight="bold", y=0.97,
    )

    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    heat_pos = ax_heat.get_position()
    heat_bbox = ax_heat.get_tightbbox(renderer).transformed(fig.transFigure.inverted())
    dendro_y0 = heat_bbox.y1 + 0.005
    dendro_pos = ax_dendro.get_position()
    ax_dendro.set_position([heat_pos.x0, dendro_y0,
                            heat_pos.width, dendro_pos.height])

    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"クラスタマップ保存: {out_path}")

    # クラスタ順序ログ
    print("\nクラスタリング順序（左→右 / 上→下）:")
    for i, idx in enumerate(order):
        unit = MEMBERS_JP[keys[idx]]["units"][0]
        print(f"  {i+1:2d}. {labels[idx]:8s} ({unit})")


def main():
    PLOTS_DIR.mkdir(parents=True, exist_ok=True)
    df   = load_matrix()
    keys = list(df.columns)
    print(f"分析対象: {len(keys)} 名")
    C    = co_matrix(df)
    J    = jaccard_matrix(C)
    plot_clustermap(J, C, keys, PLOTS_DIR / "overlap_clustermap.png")


if __name__ == "__main__":
    main()
