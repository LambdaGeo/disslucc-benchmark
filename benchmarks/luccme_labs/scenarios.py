"""disslucc scenarios that mirror LuccME labs.

Each scenario builds the lab's model with disslucc (inputs from the pinned luccme-goldens
layers) and returns, for every year, `<lu>_out` and `<lu>_pot` of every cell, plus the
convergence-loop iterations and maximum error per year. Parameters are transcribed from the
lab's Lua script; `declared` lists every number transcribed so that `run.py` can check
each one against the Lua text (a typo fails before any simulation is compared).
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Callable

import geopandas as gpd
import numpy as np
import pandas as pd
from dissmodel.core import Environment, Model
from dissmodel.geo.raster.backend import RasterBackend

from disslucc import (
    AllocationClueLike,
    AllocationClueLikeSaturation,
    AllocationDClueSLike,
    AllocationSpec,
    DemandPreComputedValues,
    LogisticRegressionSpec,
    PotentialDLogisticRegression,
    PotentialLinearRegression,
    PotentialSpatialLagRegression,
    RegressionSpec,
    SaturationAllocationSpec,
    SpatialLagRegressionSpec,
)

import references as ref


@dataclass
class Run:
    table: pd.DataFrame            # index (year, row, col); columns <lu>_out, <lu>_pot
    iterations: list[int]          # per year
    max_error: list[float] | None  # per year (continuous allocations)


@dataclass
class Scenario:
    lab: str                       # lab whose Lua script the parameters come from
    run: Callable[[], Run]
    declared: list[float] = field(default_factory=list)  # numbers transcribed from the Lua
    golden: str | None = None      # golden directory; defaults to `lab` (a variant: lab01_md1643)
    max_difference: float | None = None  # `MD=` override the golden was generated with, if any

    @property
    def golden_name(self) -> str:
        return self.golden or self.lab


class _Recorder(Model):
    """Snapshots `<lu>` and `<lu>_pot` at the end of every step (create it after the allocation)."""

    def setup(self, backend, rows, cols, land_use_types):
        self.backend, self.rows, self.cols, self.lus = backend, rows, cols, land_use_types
        self.snaps: list[dict[str, np.ndarray]] = []

    def execute(self):
        snap = {}
        for lu in self.lus:
            snap[f"{lu}_out"] = np.asarray(self.backend.get(lu), dtype=np.float64)[self.rows, self.cols].copy()
            snap[f"{lu}_pot"] = np.asarray(self.backend.get(f"{lu}_pot"), dtype=np.float64)[self.rows, self.cols].copy()
        self.snaps.append(snap)


def _table(rec: _Recorder, years: list[int]) -> pd.DataFrame:
    frames = []
    for year, snap in zip(years, rec.snaps, strict=True):
        f = pd.DataFrame(snap)
        f["year"], f["row"], f["col"] = year, rec.rows, rec.cols
        frames.append(f)
    return pd.concat(frames).set_index(["year", "row", "col"]).sort_index()


def _grid(cells: gpd.GeoDataFrame, columns: list[str], dtype=np.float32) -> tuple[RasterBackend, np.ndarray, np.ndarray]:
    """Raster by the cells' own (row, col): no resampling, so no alignment error."""
    rows, cols = cells["row"].astype(int).values, cells["col"].astype(int).values
    shape = (int(rows.max()) + 1, int(cols.max()) + 1)
    backend = RasterBackend(shape=shape)
    mask = np.zeros(shape, dtype=np.float32)
    mask[rows, cols] = 1.0
    backend.set("mask", mask)
    for c in columns:
        arr = np.zeros(shape, dtype=dtype)
        arr[rows, cols] = cells[c].astype(float).values
        backend.set(c, arr)
    return backend, rows, cols


def _finish(allocation, rec, years) -> Run:
    return Run(
        table=_table(rec, years),
        iterations=list(allocation.iterations_per_step),
        max_error=list(getattr(allocation, "max_error_per_step", []) or []) or None,
    )


# ── csAC labs (continuous, 2008-2014): lab01, lab03, lab06 ───────────────────────────────────

CSAC_LUS = ["f", "d", "outros"]
CSAC_YEARS = list(range(2008, 2015))
CSAC_DEMAND = [
    [137878.1691, 19982.62882, 6489.202049], [137622.2199, 20238.57805, 6489.202049],
    [137366.2707, 20494.52729, 6489.202049], [137110.3214, 20750.47652, 6489.202049],
    [136824.6853, 21036.11265, 6489.202049], [136539.0492, 21321.74879, 6489.202049],
    [136253.4130, 21607.38493, 6489.202049],
]
LAB01_DRIVERS = ["assentamen", "uc_us", "uc_pi", "ti", "dist_riobr", "fertilidad", "rodovias"]
_ALLOC_FLAGS = [(-1, 0, 1, 0, 1), (-1, 0, 1, 0, 1), (1, 0, 1, 0, 1)]  # static, minValue, maxValue, minChange, maxChange


def lab01(cell_correction: bool, max_difference: float = 5000.0) -> Run:
    """PreComputedValues + CLinearRegression + CClueLike (maxDifference 5000 in the lab script)."""
    cells = gpd.read_file(ref.layer("csAC"))
    backend, rows, cols = _grid(cells, CSAC_LUS + LAB01_DRIVERS)
    env = Environment(end_time=len(CSAC_YEARS) - 1)
    demand = DemandPreComputedValues(annual_demand=CSAC_DEMAND, land_use_types=CSAC_LUS)
    potential = PotentialLinearRegression(
        backend=backend, demand=demand, land_use_types=CSAC_LUS, land_use_no_data="outros",
        potential_data=[[
            RegressionSpec(const=0.7392, betas={
                "assentamen": -0.2193, "uc_us": 0.1754, "uc_pi": 0.09708, "ti": 0.1207,
                "dist_riobr": 0.0000002388, "fertilidad": -0.1313}),
            RegressionSpec(const=0.267, betas={
                "rodovias": -0.0000009922, "assentamen": 0.2294, "uc_us": -0.09867,
                "dist_riobr": -0.0000003216, "fertilidad": 0.1281}),
            RegressionSpec(const=0.0),
        ]],
    )
    allocation = AllocationClueLike(
        backend=backend, demand=demand, potential=potential, land_use_types=CSAC_LUS,
        static={"f": -1, "d": -1, "outros": 1}, complementar_lu="f", cell_area=25.0,
        allocation_data=[AllocationSpec(static=s, min_value=a, max_value=b, min_change=c, max_change=d)
                         for s, a, b, c, d in _ALLOC_FLAGS],
        max_difference=max_difference, cell_correction=cell_correction,
    )
    rec = _Recorder(backend=backend, rows=rows, cols=cols, land_use_types=CSAC_LUS)
    env.run()
    return _finish(allocation, rec, CSAC_YEARS)


LAB01_DECLARED = [
    *[v for row in CSAC_DEMAND for v in row],
    0.7392, -0.2193, 0.1754, 0.09708, 0.1207, 0.0000002388, -0.1313,
    0.267, -0.0000009922, 0.2294, -0.09867, -0.0000003216, 0.1281, 25.0,
]
LAB01_MAX_DIFFERENCE = 5000.0   # in lab01.lua; a variant overrides it (MD=) and says so in its manifest

LAB03_SPECS = [
    SpatialLagRegressionSpec(const=0.05266679, ro=0.9124615,
                             betas={"uc_us": 0.03789872, "uc_pi": 0.04141921, "ti": 0.04455667}),
    SpatialLagRegressionSpec(const=0.01431553, ro=0.9019253,
                             betas={"assentamen": 0.0443537, "uc_us": -0.01454847,
                                    "fertilidad": 0.01701601, "dist_riobr": -0.00000002262071}),
    SpatialLagRegressionSpec(const=0, ro=0, betas={}),
]
LAB03_DECLARED = [
    *[v for row in CSAC_DEMAND for v in row],
    0.05266679, 0.9124615, 0.03789872, 0.04141921, 0.04455667,
    0.01431553, 0.9019253, 0.0443537, -0.01454847, 0.01701601, -0.00000002262071,
    1643.0, 1000.0, 0.1, 0.001, 1.5, 25.0,
]


def _saturation(updates: dict[int, str]) -> Run:
    """PreComputedValues + CSpatialLagRegression + CClueLikeSaturation (maxDifference 1643).
    `updates` maps a year to the layer whose columns replace the drivers from that year
    (LuccME's updateYears)."""
    cells = gpd.read_file(ref.layer("csAC"))
    rows, cols = cells["row"].astype(int).values, cells["col"].astype(int).values
    drivers_used = sorted({d for s in LAB03_SPECS for d in s.betas})
    # float64: the saturation/spatial-lag labs are compared at 1e-9 (the goldens keep 12 decimals)
    backend, rows, cols = _grid(cells, CSAC_LUS + drivers_used, dtype=np.float64)
    new_layers = {y: gpd.read_file(ref.layer(name)) for y, name in updates.items()}

    class Updates(Model):
        """LuccME's updateYears: this year's drivers, before demand and potential. LuccME copies
        the columns of the <layer>_<year> file into the cells *by position* (forEachCellPair)."""

        def execute(self):
            year = CSAC_YEARS[0] + int(self.env.now())
            current = cells.copy()
            for upd_year in sorted(new_layers):
                if year >= upd_year:
                    for col in new_layers[upd_year].columns:
                        if col in current.columns and col not in ("geometry", "object_id0"):
                            current[col] = new_layers[upd_year][col].values
            for name in drivers_used:
                arr = np.zeros(backend.shape, dtype=np.float64)
                arr[rows, cols] = current[name].astype(float).values
                backend.set(name, arr)

    # cells are visited in the layer's (file) order, as TerraME does
    order = np.zeros(backend.shape)
    order[rows, cols] = np.arange(len(cells), dtype=np.float64)
    backend.set("order", order)

    env = Environment(end_time=len(CSAC_YEARS) - 1)
    Updates()
    demand = DemandPreComputedValues(annual_demand=CSAC_DEMAND, land_use_types=CSAC_LUS)
    potential = PotentialSpatialLagRegression(
        backend=backend, potential_data=[copy.deepcopy(LAB03_SPECS)], demand=demand,  # deepcopy: the component writes the adapted const back
        land_use_types=CSAC_LUS, land_use_no_data="outros",
    )
    allocation = AllocationClueLikeSaturation(
        backend=backend, demand=demand, potential=potential, land_use_types=CSAC_LUS,
        allocation_data=[[SaturationAllocationSpec(static=s, min_value=a, max_value=b, min_change=c, max_change=d)
                          for s, a, b, c, d in _ALLOC_FLAGS]],
        complementar_lu="f", cell_area=25, land_use_no_data="outros", attr_protection="uc_pi",
        max_difference=1643, max_iteration=1000, initial_elasticity=0.1, min_elasticity=0.001,
        max_elasticity=1.5, order_attr="order",
    )
    rec = _Recorder(backend=backend, rows=rows, cols=cols, land_use_types=CSAC_LUS)
    env.run()
    return _finish(allocation, rec, CSAC_YEARS)


# ── cs_moju lab (discrete, 1999-2004): lab15 ─────────────────────────────────────────────────

MOJU_LUS = ["f", "d", "o"]
MOJU_YEARS = list(range(1999, 2005))
MOJU_DEMAND = [[5706, 205, 3], [5658, 253, 3], [5611, 300, 3], [5563, 348, 3], [5516, 395, 3], [5468, 443, 3]]
MOJU_DRIVERS = ["media_decl", "dist_area_", "dist_br", "dist_curua", "dist_rios_", "dist_estra"]
MOJU_SPECS = [
    LogisticRegressionSpec(const=-2.34187976925989, elasticity=0.0, betas={
        "media_decl": -0.0272710076327129, "dist_area_": 4.30977432375496, "dist_br": 3.10319957497883,
        "dist_curua": 0.445414024051873, "dist_rios_": 47.3556329553235, "dist_estra": 38.4966894254506}),
    LogisticRegressionSpec(const=-0.100351497277102, elasticity=0.6, betas={
        "media_decl": 0.0581358851690861, "dist_area_": -0.974998890251365, "dist_br": -2.51650696123426,
        "dist_curua": -1.26742746441679, "dist_rios_": -40.3646901047482, "dist_estra": -23.0841140199094}),
    LogisticRegressionSpec(const=0.01, elasticity=0.5, betas={}),
]
LAB15_DECLARED = [
    *[float(v) for row in MOJU_DEMAND for v in row],
    -2.34187976925989, -0.0272710076327129, 4.30977432375496, 3.10319957497883, 0.445414024051873,
    47.3556329553235, 38.4966894254506, -0.100351497277102, 0.0581358851690861, -0.974998890251365,
    -2.51650696123426, -1.26742746441679, -40.3646901047482, -23.0841140199094, 0.6, 0.5, 0.01,
    1000.0, 0.0001, 1.0,
]
LAB15_MAX_DIFFERENCE = 300.0


def lab15(max_difference: float = 300.0) -> Run:
    """PreComputedValues + DLogisticRegression + DClueSLike (maxDifference 300 in the lab script)."""
    cells = gpd.read_file(ref.layer("cs_moju"))
    backend, rows, cols = _grid(cells, MOJU_LUS + MOJU_DRIVERS)
    env = Environment(end_time=len(MOJU_YEARS) - 1)
    demand = DemandPreComputedValues(annual_demand=MOJU_DEMAND, land_use_types=MOJU_LUS)
    PotentialDLogisticRegression(backend=backend, potential_data=[copy.deepcopy(MOJU_SPECS)], land_use_types=MOJU_LUS)
    allocation = AllocationDClueSLike(
        backend=backend, demand=demand, land_use_types=MOJU_LUS,
        transition_matrix=[[[1, 1, 0], [0, 1, 0], [0, 0, 1]]],  # irreversible deforestation
        cell_area=1.0, max_difference=max_difference, max_iteration=1000, factor_iteration=0.0001,
    )
    rec = _Recorder(backend=backend, rows=rows, cols=cols, land_use_types=MOJU_LUS)
    env.run()
    return _finish(allocation, rec, MOJU_YEARS)


SCENARIOS: dict[str, Scenario] = {
    # `cell_correction=False` is TerraME's behaviour (its correctCellChange never runs, a typo)
    "lab01": Scenario("lab01", lambda: lab01(cell_correction=False), LAB01_DECLARED + [LAB01_MAX_DIFFERENCE]),
    "lab01/cell_correction": Scenario("lab01", lambda: lab01(cell_correction=True), LAB01_DECLARED + [LAB01_MAX_DIFFERENCE]),
    # variants: same lab script, `maxDifference` overridden (make run-labs-per-year LAB=01 MD=1643)
    "lab01_md1643": Scenario("lab01", lambda: lab01(cell_correction=False, max_difference=1643.0), LAB01_DECLARED,
                             golden="lab01_md1643", max_difference=1643.0),
    "lab03": Scenario("lab03", lambda: _saturation({}), LAB03_DECLARED),
    "lab06": Scenario("lab06", lambda: _saturation({2009: "csAC_2009"}), LAB03_DECLARED),
    # disslucc's default (cell_correction=True) against the same golden: where the 0.0036 MAE of
    # docs/validation.md comes from. Reported only: TerraME never runs correctCellChange.
    "lab01_md1643/cell_correction": Scenario("lab01", lambda: lab01(cell_correction=True, max_difference=1643.0), LAB01_DECLARED,
                                             golden="lab01_md1643", max_difference=1643.0),
    "lab15": Scenario("lab15", lab15, LAB15_DECLARED + [LAB15_MAX_DIFFERENCE]),
    "lab15_md10": Scenario("lab15", lambda: lab15(max_difference=10.0), LAB15_DECLARED,
                           golden="lab15_md10", max_difference=10.0),
}
