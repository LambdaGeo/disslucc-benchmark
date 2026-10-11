"""Figure: a continuous and a discrete LuccME model, disslucc against the TerraME golden.

    python benchmarks/luccme_labs/figure_models.py --out docs/fig_models.png   # or: make figure

Top row: disslucc 0.5.0. Bottom row: the TerraME 2.0.1 golden of luccme-goldens (the file the benchmark
compares with, verified by SHA-256). Same cells and same colour limits in both rows. Two columns per model:
the last year, and the change since the first year.

    lab01  continuous (PreComputed + CLinearRegression + CClueLike): each cell holds fractions of
           forest, deforested and other. Shown: the deforested fraction `d`, 2014, and its change since 2008.
    lab15_md10  discrete (PreComputed + DLogisticRegression + DClueSLike, maxDifference 10): each cell has
           one class. Shown: the class in 2004 and the cells whose class changed since 1999, coloured by the
           new class. lab15 itself is not used: with maxDifference 300 no cell changes class (README, section 5).

Under each column: the largest absolute difference between the two rows over every cell, year and column of
the lab (the number of the benchmark table), and whether the iterations of the allocation are identical.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import BoundaryNorm, ListedColormap
from matplotlib.patches import Patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import references as ref  # noqa: E402
from run import LABS, compare  # noqa: E402

CLASS_NAMES = ("forest", "deforested", "other")
CLASS_COLOURS = ("#3a7d44", "#d95f02", "#c8c8c8")
UNCHANGED = "#efefef"


def _plane(table: pd.DataFrame, col: str, year: int, shape, origin) -> np.ndarray:
    t = table[col].xs(year, level="year")
    a = np.full(shape, np.nan)
    a[t.index.get_level_values("row") - origin[0], t.index.get_level_values("col") - origin[1]] = t.to_numpy()
    return a


def _classes(table: pd.DataFrame, cols, year, shape, origin) -> np.ndarray:
    planes = np.stack([_plane(table, c, year, shape, origin) for c in cols])
    out = np.argmax(np.nan_to_num(planes, nan=-1), axis=0).astype(float)
    out[np.isnan(planes).all(axis=0)] = np.nan
    return out


def _load(name: str):
    from scenarios import SCENARIOS

    scenario = SCENARIOS[name]
    result = scenario.run()
    files = ref.lab_files(scenario.golden_name, scenario.lab)
    golden = pd.read_csv(files["golden"]).set_index(["year", "row", "col"]).sort_index()
    stats = compare(name, LABS[name], scenario, result)
    return result.table.sort_index(), golden, stats


def _extent(table: pd.DataFrame):
    r, c = table.index.get_level_values("row"), table.index.get_level_values("col")
    return (int(r.min()), int(c.min())), (int(r.max() - r.min() + 1), int(c.max() - c.min() + 1))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--dpi", type=int, default=300)
    args = p.parse_args()

    fig, axes = plt.subplots(2, 4, figsize=(7.2, 3.9), dpi=args.dpi, gridspec_kw={"width_ratios": [1.85, 1.85, 1, 1]})
    fig.subplots_adjust(left=0.06, right=0.995, top=0.86, bottom=0.2, wspace=0.05, hspace=0.02)

    # ---- continuous: lab01 -------------------------------------------------------------------------------
    table, golden, stats = _load("lab01")
    origin, shape = _extent(golden)
    y0, y1 = int(golden.index.get_level_values("year").min()), int(golden.index.get_level_values("year").max())
    final = [_plane(t, "d_out", y1, shape, origin) for t in (table, golden)]
    change = [_plane(t, "d_out", y1, shape, origin) - _plane(t, "d_out", y0, shape, origin) for t in (table, golden)]
    lim = float(np.nanmax(np.abs(change)))
    for i in range(2):
        im1 = axes[i, 0].imshow(final[i], cmap="Blues", vmin=0, vmax=1, interpolation="nearest")
        im2 = axes[i, 1].imshow(change[i], cmap="Blues", vmin=0, vmax=max(lim, 1e-9), interpolation="nearest") if np.nanmin(change) >= -1e-9 \
            else axes[i, 1].imshow(change[i], cmap="RdBu_r", vmin=-lim, vmax=lim, interpolation="nearest")
    axes[0, 0].set_title(f"{y1}", fontsize=7, pad=2)
    axes[0, 1].set_title(f"change since {y0}", fontsize=7, pad=2)
    for j, (im, label) in enumerate(((im1, f"d, deforested fraction ({y1})"), (im2, f"d({y1}) − d({y0})"))):
        cax = fig.add_axes([0.06 + j * 0.2515 + 0.02, 0.125, 0.2515 - 0.06, 0.017])
        cb = fig.colorbar(im, cax=cax, orientation="horizontal")
        cb.ax.tick_params(labelsize=6, length=2)
        cb.outline.set_linewidth(0.3)
        cb.set_label(label, fontsize=6.5, labelpad=1)
    note = f"max |diff| = {stats['worst_max']:.1g}; iterations {'identical' if stats['iterations']['match'] else 'differ'}"
    fig.text(0.06 + 0.2515, 0.19, note, ha="center", va="top", fontsize=6.5, color="#444444")

    # ---- discrete: lab15 ---------------------------------------------------------------------------------
    table, golden, stats = _load("lab15_md10")
    origin, shape = _extent(golden)
    y0, y1 = int(golden.index.get_level_values("year").min()), int(golden.index.get_level_values("year").max())
    cols = ("f_out", "d_out", "o_out")
    cmap = ListedColormap(CLASS_COLOURS)
    norm = BoundaryNorm(np.arange(4) - 0.5, 3)
    cmap_change = ListedColormap([UNCHANGED, *CLASS_COLOURS])
    norm_change = BoundaryNorm(np.arange(5) - 0.5, 4)
    agree = []
    for i, t in enumerate((table, golden)):
        last = _classes(t, cols, y1, shape, origin)
        first = _classes(t, cols, y0, shape, origin)
        changed = np.where(last != first, last + 1, 0.0)
        changed[np.isnan(last)] = np.nan
        axes[i, 2].imshow(last, cmap=cmap, norm=norm, interpolation="nearest")
        axes[i, 3].imshow(changed, cmap=cmap_change, norm=norm_change, interpolation="nearest")
        agree.append((last, changed))
    same = float(np.mean(agree[0][0][~np.isnan(agree[0][0])] == agree[1][0][~np.isnan(agree[1][0])])) * 100
    axes[0, 2].set_title(f"{y1}", fontsize=7, pad=2)
    axes[0, 3].set_title(f"changed since {y0}", fontsize=7, pad=2)
    note = f"{same:.1f}% of cells agree; iterations {'identical' if stats['iterations']['match'] else 'differ'}"
    fig.text(0.06 + 0.2515 * 2 + 0.2515 * 0.0 + 0.145, 0.19, note, ha="center", va="top", fontsize=6.5, color="#444444")
    fig.legend(handles=[Patch(facecolor=c, edgecolor="#666666", linewidth=0.4, label=n) for c, n in zip(CLASS_COLOURS, CLASS_NAMES)]
               + [Patch(facecolor=UNCHANGED, edgecolor="#666666", linewidth=0.4, label="unchanged")],
               loc="lower center", bbox_to_anchor=(0.80, 0.0), ncol=4, fontsize=6.5, frameon=False,
               title="class (right: new class of the cells that changed)", title_fontsize=6.5, handlelength=1.1, columnspacing=0.8)

    fig.text(0.06 + 0.2515, 0.935, "lab01 · continuous (CClueLike)", ha="center", fontsize=8.5, fontweight="bold")
    fig.text(0.06 + 0.2515 * 2 + 0.145, 0.935, "lab15_md10 · discrete (DClueSLike)", ha="center", fontsize=8.5, fontweight="bold")
    for ax in axes.ravel():
        ax.set_xticks([])
        ax.set_yticks([])
        for s in ax.spines.values():
            s.set_visible(False)
    for i, name in enumerate(("disslucc", "TerraME")):
        axes[i, 0].set_ylabel(name, fontsize=8.5, fontweight="bold", labelpad=3)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.out, dpi=args.dpi)
    print(f"{args.out}")


if __name__ == "__main__":
    main()
