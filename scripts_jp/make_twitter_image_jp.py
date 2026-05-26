"""
Twitter誘引用クラスタマップ画像生成

step6_clustermap_jp.py と完全に同じレイアウト・構成で、文字サイズのみ拡大した
バージョンを出力する。論文用と差し替えるのではなく、別ファイル
data/plots/jp/twitter_clustermap.png として並置する。

実行方法:
    python scripts_jp/make_twitter_image_jp.py

出力:
    data/plots/jp/twitter_clustermap.png
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

import matplotlib.path as _mpath
def _path_deepcopy_fix(self, memo):
    result = object.__new__(type(self))
    memo[id(self)] = result
    result.__dict__.update(copy.deepcopy(self.__dict__, memo))
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

SHORT_NAMES = {
    "sora":"そら","roboco":"ロボ子","azki":"AZKi","suisei":"すいせい","miko":"みこ",
    "fubuki":"フブキ","matsuri":"まつり","aki":"アキ",
    "ayame":"あやめ","subaru":"スバル",
    "mio":"ミオ","okayu":"おかゆ","korone":"ころね",
    "pekora":"ぺこら","flare":"フレア","noel":"ノエル","marine":"マリン",
    "watame":"わため","towa":"トワ","luna":"ルーナ",
    "lamy":"ラミィ","nene":"ねね","botan":"ぼたん","polka":"ポルカ",
    "lui":"ルイ","koyori":"こより","iroha":"いろは",
    "kanade":"奏","ririka":"莉々華","raden":"らでん","hajime":"はじめ",
    "riona":"リオナ","su":"枢","chihaya":"千速","vivi":"ヴィヴィ",
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

    # step6 と同じレイアウト（デンドログラム高さのみ縮小）
    fig = plt.figure(figsize=(15, 15.5))
    gs = fig.add_gridspec(
        nrows=2, ncols=2,
        width_ratios=[20, 1],
        height_ratios=[0.6, 6],
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
    # 葉までの余白を縮めて上部の木構造に縦幅を回す
    # （最短枝＝おかスバの d_min から leaf までの距離 = leaf_margin）
    leaf_margin = (d_max - d_min) * 0.1
    leaf_y = d_min - leaf_margin
    dcoord = np.where(dcoord == 0, leaf_y, dcoord)

    for xs, ys in zip(icoord_norm, dcoord):
        ax_dendro.plot(xs, ys, color="#333333", linewidth=1.4)

    ax_dendro.set_xlim(-0.5, n - 0.5)
    top_margin = (d_max - d_min) * 0.1
    ax_dendro.set_ylim(leaf_y - leaf_margin * 0.2, d_max + top_margin)
    ax_dendro.set_xticks([])
    ax_dendro.set_yticks([])
    for side in ("top", "right", "bottom"):
        ax_dendro.spines[side].set_visible(False)
    ax_dendro.spines["left"].set_color("#cccccc")
    # フォントサイズのみ拡大: step6 は 7 → Twitter版は 18
    ax_dendro.set_ylabel("距離 (1−J)", fontsize=18, color="#888888")

    im = ax_heat.imshow(J_ord, cmap="YlOrRd", aspect="equal")
    ax_heat.set_xlim(-0.5, n - 0.5)
    ax_heat.set_ylim(n - 0.5, -0.5)

    cbar = fig.colorbar(im, cax=ax_cbar)
    # step6: 18 → 26
    cbar.set_label("Jaccard係数（%）", fontsize=26)
    # step6: 14 → 20
    cbar.ax.tick_params(labelsize=20)

    ax_heat.set_xticks(range(n))
    ax_heat.set_yticks(range(n))
    # step6: 16 → 20（24だと隣ラベルと被るため縮小）
    ax_heat.set_xticklabels(labels_ord, fontsize=20, rotation=90)
    ax_heat.set_yticklabels(labels_ord, fontsize=20)
    ax_heat.xaxis.set_ticks_position("top")
    ax_heat.xaxis.set_label_position("top")
    ax_heat.yaxis.set_ticks_position("left")
    ax_heat.tick_params(axis="x", bottom=False, labelbottom=False)
    ax_heat.tick_params(axis="y", right=False, labelright=False)

    # 対角線セル: step6: 11 → 16
    vmax = np.nanmax(J_ord)
    for i in range(n):
        ax_heat.text(i, i, f"{diag_ord[i]/1000:.1f}k", ha="center", va="center",
                     fontsize=16, color="#aaaaaa", fontweight="bold")

    for i, (lbl, unit) in enumerate(zip(labels_ord, units_ord)):
        color = UNIT_COLOR.get(unit, "#666")
        xt = ax_heat.get_xticklabels()[i]
        yt = ax_heat.get_yticklabels()[i]
        for t in (xt, yt):
            t.set_color(color)
            t.set_fontweight("bold")

    # 凡例: step6: 16 → 22
    legend_patches = [
        mpatches.Patch(color=col, label=u) for u, col in UNIT_COLOR.items()
    ]
    ax_heat.legend(
        handles=legend_patches, loc="upper right",
        bbox_to_anchor=(1.0, -0.02), ncol=5, fontsize=22,
    )

    # タイトル: step6: 22 → 30
    fig.suptitle(
        f"ホロライブJP 35名 Jaccard係数 クラスタマップ（階層クラスタリング順, {LINKAGE_METHOD} linkage）",
        fontsize=30, fontweight="bold", y=0.97,
    )

    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    heat_pos = ax_heat.get_position()
    heat_bbox = ax_heat.get_tightbbox(renderer).transformed(fig.transFigure.inverted())
    # デンドログラム下端を X 軸ラベル上端のちょうど真上に配置（重なり防止）
    dendro_y0 = heat_bbox.y1
    dendro_pos = ax_dendro.get_position()
    ax_dendro.set_position([heat_pos.x0, dendro_y0,
                            heat_pos.width, dendro_pos.height])

    fig.savefig(out_path, dpi=160, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"Twitter版クラスタマップ保存: {out_path}")


def main():
    df   = load_matrix()
    keys = list(df.columns)
    C    = co_matrix(df)
    J    = jaccard_matrix(C)
    plot_clustermap(J, C, keys, PLOTS_DIR / "twitter_clustermap.png")


if __name__ == "__main__":
    main()
