"""
The ports against the original LuccME Lua code, run as it is (lupa), on
synthetic cases built to reach what the lab03/lab06 goldens never do:

- ``correctCellChange`` — in those labs no cell ever needs correcting;
- the saturation branch of ``computeChange`` and ``updateAllocationParameters``
  — those labs set ``changeLimiarValue = 1``;
- ``computePotential`` with log-transformed classes, isolated cells and cells
  whose neighbours are all no-data — csAC has none.

The two Lua files are the unchanged LuccME components of the reference image (terrame-docker v0.4.2,
luccme/lua/), downloaded and SHA-256-checked from references.toml; none is stored here. The TerraME
functions they call are stubbed below: ``forEachCell``, ``forEachNeighbor`` (the
neighbourhoods are built here, as TerraME's ``createNeighborhood`` would: Moore
without the cell for the potential, 3 × 3 with the cell for "11x11"), ``belong``.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "benchmarks" / "luccme_labs"))
import references as ref  # noqa: E402

from disslucc.components.allocation.saturation import (
    compute_change,
    correct_cell_change,
    saturation_indicator,
)
from disslucc.components.potential.spatial_lag import spatial_lag_regression
from disslucc.schemas import SaturationAllocationSpec, SpatialLagRegressionSpec

lupa = pytest.importorskip("lupa")

TOL = 1e-12
STUBS = """
print = function() end
function forEachCell(cs, f) for _, c in ipairs(cs.cells) do f(c) end end
function forEachNeighbor(cell, name, f)
    if type(name) == "function" then f = name; name = "1" end
    for _, n in ipairs(cell.neighborhoods[name]) do f(n, 1, cell) end
end
function belong(v, t) for _, x in ipairs(t) do if x == v then return true end end return false end
function makeDemand(dirs)
    local d = {dirs = dirs}
    function d:getCurrentLuDirection(i) return self.dirs[i] end
    return d
end
function makeEvent(t) local e = {t = t}; function e:getTime() return self.t end; return e end
"""


@pytest.fixture(scope="module")
def lua():
    rt = lupa.LuaRuntime(unpack_returned_tuples=True)
    rt.execute(STUBS)
    for name in ("AllocationCClueLikeSaturation.lua", "PotentialCSpatialLagRegression.lua"):
        rt.execute(ref.lua_component(name).read_text())
    return rt


def table(lua, obj):
    return lua.table_from(obj, recursive=True)


def lua_allocation(lua, specs: list[SaturationAllocationSpec], **extra):
    data = [
        {
            "static": s.static,
            "minValue": s.min_value,
            "maxValue": s.max_value,
            "minChange": s.min_change,
            "maxChange": s.max_change,
            "changeLimiarValue": s.change_limiar_value,
            "maxChangeAboveLimiar": s.max_change_above_limiar,
        }
        for s in specs
    ]
    return lua.globals().AllocationCClueLikeSaturation(table(lua, {"allocationData": [data], **extra}))


class Grid:
    """A small raster with holes; the cells in row-major order are LuccME's cells."""

    def __init__(self, rng, shape=(24, 30), holes=0.15, isolated=4):
        self.shape = shape
        self.valid = rng.random(shape) > holes
        # a few isolated cells: a valid cell with every neighbour removed
        for _ in range(isolated):
            r, c = rng.integers(2, shape[0] - 2), rng.integers(2, shape[1] - 2)
            self.valid[r - 1 : r + 2, c - 1 : c + 2] = False
            self.valid[r, c] = True
        self.rows, self.cols = np.nonzero(self.valid)

    def neighbourhoods(self, lua, cells):
        index = {(r, c): k for k, (r, c) in enumerate(zip(self.rows, self.cols, strict=True))}
        for k, (r, c) in enumerate(zip(self.rows, self.cols, strict=True)):
            moore, window = [], []
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    j = index.get((r + dr, c + dc))
                    if j is None:
                        continue
                    window.append(cells[j])
                    if (dr, dc) != (0, 0):
                        moore.append(cells[j])
            cells[k].neighborhoods = table(lua, {"1": moore, "11x11": window})


def random_specs(rng, n) -> list[SaturationAllocationSpec]:
    specs = []
    for i in range(n):
        lo = float(rng.choice([0.0, 0.0, 0.05, 0.2]))
        hi = float(rng.choice([1.0, 1.0, 0.8, 0.6]))
        specs.append(
            SaturationAllocationSpec(
                static=int(rng.choice([-1, -1, 0, 1])) if i else -1,
                min_value=lo,
                max_value=hi,
                min_change=float(rng.choice([0.0, 0.01])),
                max_change=float(rng.choice([1.0, 0.3, 0.1])),
                change_limiar_value=float(rng.uniform(0.2, 0.8)),
                max_change_above_limiar=float(rng.uniform(0.0, 0.1)),
            )
        )
    return specs


# ── correctCellChange ──────────────────────────────────────────────────────


@pytest.mark.parametrize("seed", range(12))
def test_correct_cell_change_matches_lua(lua, seed):
    rng = np.random.default_rng(seed)
    n_cells, n_lu = 300, int(rng.integers(3, 5))
    lus = [f"c{i}" for i in range(n_lu)]
    specs = random_specs(rng, n_lu)
    directions = [int(d) for d in rng.choice([-1, 0, 1], size=n_lu)]

    past = rng.dirichlet(np.ones(n_lu), size=n_cells)
    step = rng.normal(0, 0.08, size=(n_cells, n_lu))
    same_way = rng.random(n_cells) < 0.3  # every class moving the same way: the "shift" branch
    step[same_way] = np.abs(step[same_way]) * rng.choice([-1, 1], size=(same_way.sum(), 1))
    values = np.clip(past + step, 0, 1)

    cells = []
    for k in range(n_cells):
        cell = {lu: float(values[k, i]) for i, lu in enumerate(lus)}
        cell["past"] = {lu: float(past[k, i]) for i, lu in enumerate(lus)}
        cell["regionAloc"] = 1
        cells.append(table(lua, cell))
    model = table(lua, {"cs": {"cells": cells}, "landUseTypes": lus})
    model.demand = lua.globals().makeDemand(table(lua, directions))
    comp = lua_allocation(lua, specs)
    comp.correctCellChange(comp, model, 1)
    theirs = np.array([[cells[k][lu] for lu in lus] for k in range(n_cells)])

    stats: dict = {}
    ours = correct_cell_change(values, past, specs, directions, stats)
    assert np.abs(ours - theirs).max() < TOL, stats
    assert stats["need"] > 0


def test_correct_cell_change_cases_reach_every_branch(lua):
    """The random cases above are only worth something if they reach the branches."""
    total: dict = {}
    for seed in range(12):
        rng = np.random.default_rng(seed)
        n_lu = int(rng.integers(3, 5))
        specs = random_specs(rng, n_lu)
        past = rng.dirichlet(np.ones(n_lu), size=300)
        step = rng.normal(0, 0.08, size=(300, n_lu))
        same_way = rng.random(300) < 0.3
        step[same_way] = np.abs(step[same_way]) * rng.choice([-1, 1], size=(same_way.sum(), 1))
        values = np.clip(past + step, 0, 1)
        correct_cell_change(values, past, specs, [int(d) for d in rng.choice([-1, 0, 1], size=n_lu)], total)
    assert total["need"] > 1000
    assert total["shift"] > 100
    assert total["backp_lowered"] > 100
    assert total["several_rounds"] > 10


# ── computeChange with saturation ──────────────────────────────────────────


@pytest.mark.parametrize("seed", range(8))
def test_compute_change_matches_lua(lua, seed):
    rng = np.random.default_rng(100 + seed)
    n_cells, n_lu = 400, 3
    lus = ["f", "d", "o"]
    specs = random_specs(rng, n_lu)
    directions = [int(d) for d in rng.choice([-1, 1], size=n_lu)]
    elasticity = [float(e) for e in rng.uniform(0.05, 1.5, size=n_lu)]
    past = rng.dirichlet(np.ones(n_lu), size=n_cells)
    pot = rng.normal(0, 0.3, size=(n_cells, n_lu))
    pot[rng.random((n_cells, n_lu)) < 0.05] = 0.0
    saturation = rng.random(n_cells)

    cells = []
    for k in range(n_cells):
        cell = {f"{lu}_pot": float(pot[k, i]) for i, lu in enumerate(lus)}
        cell.update({lu: float(past[k, i]) for i, lu in enumerate(lus)})
        cell["past"] = {lu: float(past[k, i]) for i, lu in enumerate(lus)}
        cell["regionAloc"] = 1
        cell["sat"] = float(saturation[k])
        cells.append(table(lua, cell))
    model = table(lua, {"cs": {"cells": cells}, "landUseTypes": lus})
    model.demand = lua.globals().makeDemand(table(lua, directions))
    comp = lua_allocation(lua, specs, saturationIndicator="sat")
    comp.elasticity = table(lua, elasticity)
    comp.computeChange(comp, model, 1)

    saturated = 0
    for i, lu in enumerate(lus):
        theirs = np.array([cells[k][lu] for k in range(n_cells)])
        ours = compute_change(past[:, i], pot[:, i], elasticity[i], specs[i], directions[i], saturation)
        assert np.abs(ours - theirs).max() < TOL, (lu, specs[i])
        saturated += int((saturation > specs[i].change_limiar_value).sum())
    assert saturated > 0


# ── updateAllocationParameters (saturation indicator) ──────────────────────


@pytest.mark.parametrize("seed", range(6))
def test_saturation_indicator_matches_lua(lua, seed):
    rng = np.random.default_rng(200 + seed)
    grid = Grid(rng)
    shape = grid.shape
    comp_share = rng.random(shape)
    no_data = np.where(rng.random(shape) < 0.1, 1.0, rng.random(shape) * 0.3)
    protection = np.where(rng.random(shape) < 0.2, rng.random(shape) * 0.8, 0.0)

    cells = []
    for r, c in zip(grid.rows, grid.cols, strict=True):
        cells.append(
            table(
                lua,
                {"f": float(comp_share[r, c]), "nd": float(no_data[r, c]), "prot": float(protection[r, c])},
            )
        )
    grid.neighbourhoods(lua, cells)
    model = table(lua, {"cs": {"cells": cells}, "landUseNoData": "nd"})
    comp = lua_allocation(
        lua,
        [SaturationAllocationSpec()],
        saturationIndicator="sat",
        attrProtection="prot",
        complementarLU="f",
    )
    comp.updateAllocationParameters(comp, lua.globals().makeEvent(2000), model)

    theirs = np.array([cell["sat"] for cell in cells])
    ours = saturation_indicator(comp_share, grid.valid, no_data, protection)[grid.rows, grid.cols]
    assert np.abs(ours - theirs).max() < TOL


# ── computePotential ───────────────────────────────────────────────────────


@pytest.mark.parametrize("is_log", [False, True])
@pytest.mark.parametrize("seed", range(4))
def test_spatial_lag_potential_matches_lua(lua, seed, is_log):
    rng = np.random.default_rng(300 + seed)
    grid = Grid(rng)
    shape = grid.shape
    share = rng.random(shape)
    no_data = np.where(rng.random(shape) < 0.25, 1.0, rng.random(shape) * 0.4)  # many all-no-data cells
    drivers = {"x1": rng.random(shape), "x2": rng.normal(0, 1, shape)}
    spec = SpatialLagRegressionSpec(
        const=float(rng.normal(0, 0.2)),
        ro=float(rng.uniform(0.5, 1.0)),
        betas={"x1": float(rng.normal(0, 0.5)), "x2": float(rng.normal(0, 0.1))},
        is_log=is_log,
        min_reg=float(rng.choice([0.0, 0.1])),
        max_reg=float(rng.choice([1.0, 0.9])),
    )
    newconst = spec.const + 0.1 * int(rng.integers(-2, 3))  # as after the allocation's modify

    cells = []
    for r, c in zip(grid.rows, grid.cols, strict=True):
        cell = {"region": 1, "nd": float(no_data[r, c]), "past": {"u": float(share[r, c])}}
        cell.update({k: float(v[r, c]) for k, v in drivers.items()})
        cells.append(table(lua, cell))
    grid.neighbourhoods(lua, cells)
    model = table(lua, {"cs": {"cells": cells}, "landUseTypes": ["u"], "landUseNoData": "nd"})
    data = {
        "isLog": is_log,
        "const": spec.const,
        "minReg": spec.min_reg,
        "maxReg": spec.max_reg,
        "ro": spec.ro,
        "betas": spec.betas,
    }
    comp = lua.globals().PotentialCSpatialLagRegression(table(lua, {"potentialData": [[data]]}))
    comp.potentialData[1][1].newconst = newconst
    comp.computePotential(comp, model, 1, 1)

    theirs = np.array([cell["u_pot"] for cell in cells])
    _, pot = spatial_lag_regression(spec, share, drivers, grid.valid, no_data, newconst)
    ours = pot[grid.rows, grid.cols]
    assert np.abs(ours - theirs).max() < 1e-10

    # the cases do contain what csAC lacks
    moore_count = sum(
        np.roll(np.roll(grid.valid, dr, 0), dc, 1)
        for dr in (-1, 0, 1)
        for dc in (-1, 0, 1)
        if (dr, dc) != (0, 0)
    )
    assert ((moore_count == 0) & grid.valid).any()
