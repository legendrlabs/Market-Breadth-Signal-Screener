"""Causal indicators. Inputs must already be reindexed to the trading calendar."""
import numpy as np
import pandas as pd


def breadth_ratio(advances, declines):
    a, d = advances.astype(float), declines.astype(float)
    valid = a.ge(0) & d.ge(0) & (a+d).gt(0) & np.isfinite(a) & np.isfinite(d)
    return (a/(a+d)).where(valid)


def ema(values, span=10, warmup=100, seed='sma'):
    """SMA(span) seed or first observation; reset on every invalid session."""
    if span < 1 or warmup < span or seed not in ('sma','first'):
        raise ValueError('invalid EMA configuration')
    alpha = 2/(span+1)
    out = pd.Series(np.nan, index=values.index, dtype=float)
    buffer, previous, count = [], None, 0
    for i, value in enumerate(values):
        if not np.isfinite(value):
            buffer, previous, count = [], None, 0
            continue
        count += 1
        if previous is None:
            buffer.append(float(value))
            if seed == 'first': previous = float(value)
            elif len(buffer) == span: previous = float(np.mean(buffer))
        else:
            previous = alpha*value + (1-alpha)*previous
        if count >= warmup and previous is not None: out.iloc[i] = previous
    return out


def strong_streak(close, threshold=.015):
    returns = close.pct_change(fill_method=None)
    count, out = 0, []
    for value in returns:
        # Relative tolerance only covers IEEE roundoff around exactly 1.5%.
        count = count+1 if np.isfinite(value) and (value > threshold or np.isclose(value,threshold,rtol=0,atol=1e-12)) else 0
        out.append(count)
    return pd.Series(out,index=close.index,dtype=int)


def expansion_count(ratio):
    eligible = ratio.gt(.70).astype(float).where(ratio.notna())
    return eligible.rolling(10,min_periods=10).sum()
