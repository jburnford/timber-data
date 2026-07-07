#!/usr/bin/env python3
"""Structural-break dating for Canada's UK timber exports (JHG Fig 3 data).

Method: piecewise-linear segmented regression (each segment has its own
intercept + slope). Optimal break placement by dynamic programming over SSR
(Bai-Perron style, pure least squares); number of breaks chosen by BIC.
Break-date uncertainty: the set of alternative break years whose constrained
SSR is within 1% of the optimum (a crude but honest confidence set).

Series: Canada square timber, sawn lumber, and total, annually 1809-1900
(1813 missing — war year — interpolated for the DP grid, flagged).
"""
import numpy as np
import pandas as pd

XLSX = "/mnt/c/Users/jic823/Dropbox/2026/JHG-data2022.xlsx"
MIN_SEG = 8          # minimum segment length in years
MAX_BREAKS = 4


def seg_ssr_matrix(y):
    """ssr[i][j] = SSR of a linear fit on y[i..j] inclusive."""
    n = len(y)
    t = np.arange(n, dtype=float)
    ssr = np.full((n, n), np.inf)
    for i in range(n):
        for j in range(i + MIN_SEG - 1, n):
            tt, yy = t[i:j + 1], y[i:j + 1]
            X = np.column_stack([np.ones(len(tt)), tt])
            beta, res, *_ = np.linalg.lstsq(X, yy, rcond=None)
            ssr[i, j] = res[0] if len(res) else float(((yy - X @ beta) ** 2).sum())
    return ssr


def best_partition(ssr, m):
    """DP: minimal total SSR with m breaks; returns (ssr, break_indices)."""
    n = ssr.shape[0]
    # cost[k][j] = min SSR of fitting y[0..j] with k segments
    cost = np.full((m + 2, n), np.inf)
    prev = np.full((m + 2, n), -1, dtype=int)
    cost[1] = ssr[0]
    for k in range(2, m + 2):
        for j in range((k * MIN_SEG) - 1, n):
            # last segment starts at i+1
            cands = [(cost[k - 1, i] + ssr[i + 1, j], i)
                     for i in range((k - 1) * MIN_SEG - 1, j - MIN_SEG + 1)]
            if cands:
                c, i = min(cands)
                cost[k, j], prev[k, j] = c, i
    # backtrack
    breaks = []
    j = n - 1
    for k in range(m + 1, 1, -1):
        i = prev[k, j]
        breaks.append(i)
        j = i
    return cost[m + 1, n - 1], sorted(breaks)


def bic(ssr_val, n, m):
    k = 2 * (m + 1) + m          # slopes+intercepts per segment + break dates
    return n * np.log(ssr_val / n) + k * np.log(n)


def confidence_set(ssr, breaks, which, best_ssr, years):
    """Years for break `which` keeping others fixed, within 1% of best SSR."""
    n = ssr.shape[0]
    fixed = list(breaks)
    lo = fixed[which - 1] + MIN_SEG if which > 0 else MIN_SEG - 1
    hi = (fixed[which + 1] - MIN_SEG) if which < len(fixed) - 1 else n - MIN_SEG - 1
    ok = []
    for b in range(lo, hi + 1):
        trial = fixed[:which] + [b] + fixed[which + 1:]
        bounds = [-1] + trial + [n - 1]
        tot = sum(ssr[bounds[i] + 1, bounds[i + 1]] for i in range(len(bounds) - 1))
        if tot <= best_ssr * 1.01:
            ok.append(years[b])
    return min(ok), max(ok)


def analyze(name, years, y):
    print(f'\n== {name} ==')
    ssr = seg_ssr_matrix(y)
    n = len(y)
    results = []
    for m in range(0, MAX_BREAKS + 1):
        if (m + 1) * MIN_SEG > n:
            break
        s, br = best_partition(ssr, m)
        results.append((bic(s, n, m), m, s, br))
        print(f'  m={m}: SSR={s:12.4g}  BIC={results[-1][0]:8.1f}  '
              f'breaks={[years[b] for b in br]}')
    best = min(results)
    _, m, s, br = best
    print(f'  BIC-selected: {m} breaks at {[years[b] for b in br]}')
    bounds = [-1] + br + [n - 1]
    for i in range(len(bounds) - 1):
        a, b = bounds[i] + 1, bounds[i + 1]
        tt = np.arange(a, b + 1, dtype=float)
        X = np.column_stack([np.ones(len(tt)), tt])
        beta, *_ = np.linalg.lstsq(X, y[a:b + 1], rcond=None)
        print(f'    {years[a]}-{years[b]}: slope {beta[1] / 1e6:+.2f} M cu ft/yr '
              f'(mean level {y[a:b + 1].mean() / 1e6:.1f}M)')
    for wi, b in enumerate(br):
        lo, hi = confidence_set(ssr, br, wi, s, years)
        print(f'    break at {years[b]}: ~1%-SSR set [{lo}, {hi}]')


def main():
    f3 = pd.ExcelFile(XLSX).parse('Figure 3', index_col=0)
    years = [c for c in f3.columns if isinstance(c, (int, float)) and 1809 <= c <= 1900]
    years = [int(c) for c in years]
    sq = f3.loc['Square timber', years].astype(float)
    sw = f3.loc['Sawn lumber', years].astype(float)
    # 1813 is NaN (war year): interpolate for the grid, note in output
    sq = sq.interpolate()
    sw = sw.interpolate()
    print('note: 1813 missing in source, linearly interpolated')
    analyze('Canada SQUARE timber (cu ft)', years, sq.to_numpy())
    analyze('Canada SAWN lumber (cu ft)', years, sw.to_numpy())
    analyze('Canada TOTAL (cu ft)', years, (sq + sw).to_numpy())


if __name__ == '__main__':
    main()
