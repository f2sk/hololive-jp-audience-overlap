"""
活動年数 × チャット参加率のゾーン分割散布図（JP 35名版）

3つのゾーンに分けて可視化：
  1. 左上: FLOW GLOW（4名、デビュー間もない高参加率群）
  2. 右上: 高密度ハブ層（古参なのにフィット線から正方向に外れる群）
  3. その他: 線形フィット線が引かれる中心群

実行方法:
    python scripts_jp/step11_zones_jp.py

依存:
    pandas, numpy, matplotlib, scipy
    Python 3.10+

出力:
    data/plots/jp/zones_chart.png
"""

import sys
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from matplotlib.lines import Line2D
from matplotlib.patches import Polygon
import numpy as np
import pandas as pd
from scipy.spatial import ConvexHull
from scipy.stats import pearsonr

sys.path.insert(0, str(Path(__file__).parent))
from config_jp import DATA_DIR, DATA_DIR_JP, MEMBERS_JP, UNIT_COLOR
from step8_age_analysis_jp import years_since_debut, load_subscribers

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
PLOTS_DIR   = Path(DATA_DIR_JP)
EXCLUDED_KEYS = {"choco", "laplus", "niko"}

# 右上「高密度ハブ層」ゾーン: 活動年数 7年以上 かつ 全データ線形フィットからの残差が大きい群
# 視覚的に明瞭なクラスタを構成する 6名を選定
HUB_KEYS = ["azki", "suisei", "miko", "ayame", "subaru", "mio"]

# 左上「FLOW GLOW」ゾーン: ユニット所属で自動判定
FLOWGLOW_UNIT = "FLOW GLOW"

ZONE_COLOR = {
    "flowglow": "#1a6fa8",  # ネイビーブルー
    "hub":      "#c0392b",  # レッド
    "other":    "#7f8c8d",  # グレー
}


def hull_polygon(points: np.ndarray, padding_x: float = 0.3, padding_y: float = 0.05) -> np.ndarray:
    """点群の凸包に余白を加えたポリゴン座標を返す。
    点が縮退（同一x、または2点以下）の場合は外接矩形にフォールバック。"""
    xs, ys = points[:, 0], points[:, 1]
    degenerate = len(points) < 3 or np.ptp(xs) < 1e-6 or np.ptp(ys) < 1e-6
    if not degenerate:
        try:
            hull = ConvexHull(points)
            verts = points[hull.vertices]
            centroid = verts.mean(axis=0)
            offset = verts - centroid
            scale = np.column_stack([
                (np.abs(offset[:, 0]) + padding_x) / np.maximum(np.abs(offset[:, 0]), 1e-6),
                (np.abs(offset[:, 1]) + padding_y) / np.maximum(np.abs(offset[:, 1]), 1e-6),
            ])
            verts = centroid + offset * scale
            return verts
        except Exception:
            pass
    # 縮退時は外接矩形
    x0, x1 = xs.min() - padding_x, xs.max() + padding_x
    y0, y1 = ys.min() - padding_y, ys.max() + padding_y
    return np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y1]])


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
        unit = MEMBERS_JP[key]["units"][0]
        if unit == FLOWGLOW_UNIT:
            zone = "flowglow"
        elif key in HUB_KEYS:
            zone = "hub"
        else:
            zone = "other"
        rows.append({
            "key":   key,
            "name":  MEMBERS_JP[key]["name"],
            "unit":  unit,
            "zone":  zone,
            "years": years_since_debut(key),
            "subs":  s,
            "rate":  (unique / s if s > 0 else 0) * 100,
        })
    d = pd.DataFrame(rows)

    # ===== ゾーン別集計 =====
    print("=== ゾーン別構成 ===")
    for zone in ["flowglow", "hub", "other"]:
        sub = d[d["zone"] == zone]
        names = ", ".join(sub["name"].tolist())
        print(f"  {zone:9s} ({len(sub):2d}名): {names}")
    print()

    # ===== その他ゾーンのみで線形フィット =====
    other = d[d["zone"] == "other"]
    x_o, y_o = other["years"].values, other["rate"].values
    coef = np.polyfit(x_o, y_o, 1)
    a, b = coef
    y_pred = np.polyval(coef, x_o)
    r2 = 1 - np.sum((y_o - y_pred) ** 2) / np.sum((y_o - y_o.mean()) ** 2)
    r_p, p_p = pearsonr(x_o, y_o)
    rmse = np.sqrt(np.mean((y_o - y_pred) ** 2))

    print(f"=== 「その他」ゾーン（{len(other)}名）の線形フィット ===")
    print(f"  y = {a:+.4f} × 年数 + {b:+.4f}")
    print(f"  Pearson r = {r_p:+.4f}, p = {p_p:.4f}")
    print(f"  R² = {r2:.4f}, RMSE = {rmse:.4f} %")
    print()

    # 全データの線形フィット（比較用、プロット非表示）
    coef_all = np.polyfit(d["years"], d["rate"], 1)
    y_pred_all = np.polyval(coef_all, d["years"])
    r2_all = 1 - np.sum((d["rate"] - y_pred_all) ** 2) / np.sum((d["rate"] - d["rate"].mean()) ** 2)
    print(f"=== 全35名の線形フィット（参考） ===")
    print(f"  y = {coef_all[0]:+.4f} × 年数 + {coef_all[1]:+.4f}")
    print(f"  R² = {r2_all:.4f}")
    print()

    # ===== プロット =====
    fig, ax = plt.subplots(figsize=(15, 10))

    # ゾーン凸包をプロット（背景）
    for zone in ["flowglow", "hub", "other"]:
        sub = d[d["zone"] == zone]
        pts = sub[["years", "rate"]].values
        verts = hull_polygon(pts, padding_x=0.35, padding_y=0.06)
        poly = Polygon(verts, closed=True, facecolor=ZONE_COLOR[zone],
                       edgecolor=ZONE_COLOR[zone], alpha=0.10, linewidth=2,
                       linestyle="--", zorder=1)
        ax.add_patch(poly)

    # 「その他」線形フィット線
    xs = np.linspace(other["years"].min() - 0.3, other["years"].max() + 0.3, 100)
    ys = np.polyval(coef, xs)
    ax.plot(xs, ys, "-", color=ZONE_COLOR["other"], linewidth=2.2, alpha=0.85, zorder=2,
            label=f"「その他」線形フィット y={a:.3f}x+{b:.3f}  (R²={r2:.3f}, N={len(other)})")

    # マーカー（ユニット色を保持）
    s_min, s_max = d["subs"].min(), d["subs"].max()
    for unit, color in UNIT_COLOR.items():
        sub = d[d["unit"] == unit]
        if len(sub) == 0:
            continue
        sizes = 200 + (sub["subs"] - s_min) / (s_max - s_min) * 1800
        ax.scatter(sub["years"], sub["rate"], s=sizes, c=color,
                   alpha=0.75, edgecolor="black", linewidth=0.7, zorder=4)

    # タレント名
    for _, r in d.iterrows():
        ax.annotate(r["name"], (r["years"], r["rate"]),
                    fontsize=11, alpha=1.0, fontweight="bold",
                    xytext=(7, 5), textcoords="offset points", zorder=5)

    # ゾーンラベル（凸包の重心近辺に大きく）
    zone_labels = {
        "flowglow": ("FLOW GLOW", "左上"),
        "hub":      ("高密度ハブ層", "右上"),
        "other":    ("線形ゾーン", "中央"),
    }
    for zone, (zlabel, _) in zone_labels.items():
        sub = d[d["zone"] == zone]
        cx = sub["years"].mean()
        cy = sub["rate"].max() + 0.08
        ax.text(cx, cy, zlabel, fontsize=18, fontweight="bold",
                color=ZONE_COLOR[zone], ha="center", va="bottom",
                bbox=dict(boxstyle="round,pad=0.4", facecolor="white",
                          edgecolor=ZONE_COLOR[zone], alpha=0.9),
                zorder=6)

    ax.set_xlabel("活動年数（年、デビューから 2026-05-25 時点）", fontsize=15)
    ax.set_ylabel("チャット参加率（%）", fontsize=15)
    ax.tick_params(axis="both", labelsize=12)
    ax.set_title(
        "活動年数 × チャット参加率（3ゾーン分割、その他のみ線形回帰）\n"
        "バブル径=登録者数、色=ユニット",
        fontsize=16, fontweight="bold",
    )
    ax.grid(alpha=0.3)

    # 凡例: ユニット + フィット線
    legend_handles = [
        Line2D([0], [0], marker="o", color="w", markerfacecolor=color,
               markeredgecolor="black", markeredgewidth=0.5,
               markersize=12, alpha=0.85, label=unit)
        for unit, color in UNIT_COLOR.items()
    ]
    legend_handles.append(
        Line2D([0], [0], color=ZONE_COLOR["other"], linewidth=2.2,
               label=f"「その他」線形フィット (R²={r2:.3f}, N={len(other)})")
    )
    ax.legend(handles=legend_handles, fontsize=11, loc="lower left", ncol=2)

    # Y軸下限を 0 にして見やすく
    ax.set_ylim(bottom=0.15)

    fig.tight_layout()
    out = PLOTS_DIR / "zones_chart.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"保存: {out}")


if __name__ == "__main__":
    main()
