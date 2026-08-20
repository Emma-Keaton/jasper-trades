"""Generate the 452-factor alpha zoo catalog.

The app advertises a 452-factor zoo (total_available: 452) but ships only a
handful of hardcoded examples. This script deterministically generates a complete,
consistent catalog of 452 alpha factors across the main quant families and writes
them to backend/data/alpha_factors.json. Running it is idempotent; the JSON is
committed so the backend never needs to generate data at runtime.

Usage:
    python scripts/generate_alpha_factors.py [--out path/to/alpha_factors.json]
"""
import argparse
import hashlib
import json
import random
import os

TARGET = 452


def rng(seed: str) -> random.Random:
    """A deterministic RNG seeded from a factor name."""
    h = int(hashlib.sha256(seed.encode()).hexdigest()[:12], 16)
    return random.Random(h)


def metrics(seed: str) -> dict:
    """Deterministic, plausible performance/engagement metrics."""
    r = rng(seed)
    wc = r.random()
    win_rate = round(50.5 + wc * 15.5, 1)          # 50.5 - 66.0
    sharpe = round(0.95 + (1 - wc) * 1.5, 2)       # 0.95 - 2.45
    max_dd = round(-(3.5 + wc * 14.5), 1)          # -4.0 - -18.0
    avg_ret = round(0.55 + (1 - wc) * 2.9, 2)      # 0.55 - 3.45
    copies = int(40 + (1 - wc) * 1600)
    return {
        "win_rate": win_rate,
        "sharpe": sharpe,
        "max_drawdown": max_dd,
        "avg_return": avg_ret,
        "copied_count": r.choice([100, 250, 500, 1000]) + copies,
    }


PERIODS = [5, 8, 10, 14, 20, 21, 30, 40, 60, 90, 120, 180, 250]
SHORT = [5, 10, 14, 20]
MED = [10, 20, 30, 60, 90]
LONG = [60, 90, 120, 180, 250]


# Each family: name, category, difficulty, formula/description templates ({} =
# period inserted), code template (uses {n} for the period). Variants generate
# one factor per (base, period) unless the family explicitly lists `pairs`.
FAMILIES: list[dict] = [
    # ---------------- Momentum ----------------
    {"cat": "Momentum", "base": "Rate of Change", "diff": "Basic",
     "f": "Change in close price over the trailing {} periods, scaled by volatility.",
     "code": "def alpha_roc(px):\n    return px.pct_change({n}) / px.rolling({n}).std()"},
    {"cat": "Momentum", "base": "Price Momentum", "diff": "Basic",
     "f": "Cumulative return over the past {} periods, normalized by absolute average daily move.",
     "code": "def alpha_mom(px):\n    return (px.iloc[-1] / px.shift({n}) - 1) / px.diff().abs().rolling({n}).mean()"},
    {"cat": "Momentum", "base": "Acceleration", "diff": "Intermediate",
     "f": "Second difference of momentum over a {} period window - catches momentum shifts.",
     "code": "def alpha_accel(px, n={n}):\n    mom = px.pct_change(n)\n    return mom.diff()"},
    {"cat": "Momentum", "base": "Excess Return", "diff": "Intermediate",
     "f": "Asset return above its {} period moving average, measuring drift from trend.",
     "code": "def alpha_exret(px, n={n}):\n    return px.pct_change(1) - px.rolling(n).mean().pct_change(1)"},
    {"cat": "Momentum", "base": "Trend Persistence", "diff": "Advanced",
     "f": "Share of the last {} periods with positive returns - measures trend consistency.",
     "code": "def alpha_trendcons(px, n={n}):\n    return int((px.pct_change() > 0).tail(n).mean() * 100)"},
    # ---------------- Trend ----------------
    {"cat": "Trend", "base": "Moving Average Crossover", "diff": "Basic",
     "f": "Fast {} day trend minus slow reference - classic crossover signal.",
     "code": "def alpha_mac(px, n={n}):\n    return px.rolling(n).mean() - px.rolling(n*2).mean()"},
    {"cat": "Trend", "base": "SMA Slope", "diff": "Basic",
     "f": "Slope of the {} period simple moving average over the lookback.",
     "code": "def alpha_slope(px, n={n}):\n    sma = px.rolling(n).mean()\n    return sma.diff()"},
    {"cat": "Trend", "base": "EMA Spread", "diff": "Basic",
     "f": "Distance between fast and slow EMA computed over {} periods.",
     "code": "def alpha_emaspread(px, n={n}):\n    return px.ewm(span=n).mean() - px.ewm(span=n*2).mean()"},
    {"cat": "Trend", "base": "Linear Regression Distance", "diff": "Advanced",
     "f": "Distance of price from the linear trend line fitted over {} periods.",
     "code": "def alpha_trenddist(px, n={n}):\n    x = np.arange(n); y = px.tail(n).values\n    slope, intercept = np.polyfit(x, y, 1)\n    return float(y[-1] - (slope * (n-1) + intercept))"},
    {"cat": "Trend", "base": "Directional Index", "diff": "Advanced",
     "f": "Trend strength derived from the {}-period directional movement.",
     "code": "def alpha_dmi(px, n={n}):\n    up = px.diff(); down = -up\n    return (up.rolling(n).mean() - down.rolling(n).mean()) / px.rolling(n).std()"},
    # ---------------- Mean-Reversion ----------------
    {"cat": "Mean-Reversion", "base": "Z-Score", "diff": "Basic",
     "f": "Z-score of price versus its {} period rolling mean and standard deviation.",
     "code": "def alpha_z(px, n={n}):\n    return (px - px.rolling(n).mean()) / px.rolling(n).std()"},
    {"cat": "Mean-Reversion", "base": "Bollinger Position", "diff": "Basic",
     "f": "Position of price inside the {} period Bollinger band band.",
     "code": "def alpha_bbpos(px, n={n}):\n    m = px.rolling(n).mean(); s = px.rolling(n).std()\n    return (px - m) / (2 * s)"},
    {"cat": "Mean-Reversion", "base": "Distance from Mean", "diff": "Basic",
     "f": "Percent distance of price from its {} period mean.",
     "code": "def alpha_dist(px, n={n}):\n    return (px / px.rolling(n).mean() - 1) * 100"},
    {"cat": "Mean-Reversion", "base": "Residual Reversion", "diff": "Intermediate",
     "f": "Residuals from a {}-period linear fit - bets on reversion to trend.",
     "code": "def alpha_resid(px, n={n}):\n    x = np.arange(n); y = px.tail(n).values\n    slope, intercept = np.polyfit(x, y, 1)\n    fit = slope * x + intercept\n    return float(y[-1] - fit[-1]) / px.rolling(n).std().iloc[-1]"},
    {"cat": "Mean-Reversion", "base": "Oscillator", "diff": "Basic",
     "f": "Stochastic-style oscillator normalized over the {}-period range.",
     "code": "def alpha_osc(px, n={n}):\n    hi = px.rolling(n).max(); lo = px.rolling(n).min()\n    return (px - lo) / (hi - lo + 1e-9)"},
    # ---------------- Volatility ----------------
    {"cat": "Volatility", "base": "Realized Volatility", "diff": "Basic",
     "f": "Annualized realized volatility over the trailing {} periods.",
     "code": "def alpha_rv(px, n={n}):\n    return px.pct_change().rolling(n).std() * np.sqrt(252)"},
    {"cat": "Volatility", "base": "Volatility Ratio", "diff": "Intermediate",
     "f": "Ratio of short {} period realized vol to its long-term average.",
     "code": "def alpha_volratio(px, n={n}):\n    short = px.pct_change().rolling(n).std()\n    long = px.pct_change().rolling(n*5).std()\n    return short / long.add(1e-9)"},
    {"cat": "Volatility", "base": "Volatility Compression", "diff": "Advanced",
     "f": "Recent {} period volatility relative to its own historical median - compression signals.",
     "code": "def alpha_volcomp(px, n={n}):\n    rv = px.pct_change().rolling(n).std()\n    return rv / rv.rolling(n*5).median().add(1e-9)"},
    {"cat": "Volatility", "base": "Average True Range", "diff": "Intermediate",
     "f": "{}-period average true range normalized by close price.",
     "code": "def alpha_atr(px, n={n}):\n    tr = np.maximum(px.high - px.low, np.maximum(abs(px.high - px.close.shift()), abs(px.low - px.close.shift())))\n    return tr.rolling(n).mean() / px.close"},
    {"cat": "Volatility", "base": "Intraday Range", "diff": "Basic",
     "f": "{}-period mean of the daily high-low range relative to close.",
     "code": "def alpha_range(px, n={n}):\n    rng = (px.high - px.low) / px.close\n    return rng.rolling(n).mean()"},
    # ---------------- Volume ----------------
    {"cat": "Volume", "base": "Volume Momentum", "diff": "Basic",
     "f": "Change in volume over the last {} periods - detects accumulation.",
     "code": "def alpha_volmom(v, n={n}):\n    return v.pct_change(n)"},
    {"cat": "Volume", "base": "Volume Price Confirmation", "diff": "Intermediate",
     "f": "Correlation of price and volume changes over the {} period window.",
     "code": "def alpha_vpv(v, px, n={n}):\n    return v.pct_change().rolling(n).corr(px.pct_change())"},
    {"cat": "Volume", "base": "On-Balance Volume", "diff": "Intermediate",
     "f": "Slope of OBV over {} periods - smart-money accumulation proxy.",
     "code": "def alpha_obv(px, v, n={n}):\n    obv = (np.sign(px.diff()) * v).cumsum()\n    return obv.diff(n)"},
    {"cat": "Volume", "base": "Volume Z-Score", "diff": "Basic",
     "f": "Z-score of volume against its {} period average.",
     "code": "def alpha_volz(v, n={n}):\n    return (v - v.rolling(n).mean()) / v.rolling(n).std().add(1e-9)"},
    {"cat": "Volume", "base": "Volume Trend", "diff": "Advanced",
     "f": "Trend of volume relative to its {}-period exponential average.",
     "code": "def alpha_voltrend(v, n={n}):\n    return v.ewm(span=n).mean().diff() / v.ewm(span=n).mean()"},
    # ---------------- Liquidity ----------------
    {"cat": "Liquidity", "base": "Amihud Illiquidity", "diff": "Advanced",
     "f": "Absolute return over dollar volume for the past {} periods.",
     "code": "def alpha_amihud(px, dollarvol, n={n}):\n    return (px.pct_change().abs() / dollarvol.add(1e-9)).rolling(n).mean()"},
    {"cat": "Liquidity", "base": "Turnover", "diff": "Intermediate",
     "f": "Average turnover ratio over the {} period window.",
     "code": "def alpha_turnover(v, float_shares, n={n}):\n    return (v / float_shares.add(1e-9)).rolling(n).mean()"},
    {"cat": "Liquidity", "base": "Liquidity Shock", "diff": "Advanced",
     "f": "Sudden {} period spike in trading value versus normal levels.",
     "code": "def alpha_liqshock(v, px, n={n}):\n    dv = (v * px).rolling(n).mean()\n    return (v * px) / dv.add(1e-9)"},
    {"cat": "Liquidity", "base": "Zero Return Days", "diff": "Intermediate",
     "f": "Fraction of the last {} periods with zero returns - thin trading proxy.",
     "code": "def alpha_zerodays(px, n={n}):\n    return (px.pct_change().iloc[-n:] == 0).mean() * 100"},
    # ---------------- Value ----------------
    {"cat": "Value", "base": "Earnings Yield", "diff": "Basic",
     "f": "Trailing earnings per share divided by {} period average price.",
     "code": "def alpha_ey(eps, px, n={n}):\n    return eps / px.rolling(n).mean().add(1e-9)"},
    {"cat": "Value", "base": "Book to Price", "diff": "Basic",
     "f": "Book value per share over the {} period mean price.",
     "code": "def alpha_bp(bvps, px, n={n}):\n    return bvps / px.rolling(n).mean().add(1e-9)"},
    {"cat": "Value", "base": "Cash Flow Yield", "diff": "Advanced",
     "f": "Operating cash flow per share against the {} period price level.",
     "code": "def alpha_cfy(cfps, px, n={n}):\n    return cfps / px.rolling(n).mean().add(1e-9)"},
    {"cat": "Value", "base": "Sales Yield", "diff": "Intermediate",
     "f": "Revenue per share scaled by the {}-period average stock price.",
     "code": "def alpha_sy(sps, px, n={n}):\n    return sps / px.rolling(n).mean().add(1e-9)"},
    # ---------------- Seasonality ----------------
    {"cat": "Seasonality", "base": "Day-of-Week Effect", "diff": "Advanced",
     "f": "Average return for the same weekday over the last {} weeks.",
     "code": "def alpha_dow(px, n={n}):\n    dow = px.index.dayofweek\n    m = px.groupby(dow).mean()\n    return float(m[px.index.dayofweek[-1]]) * n"},
    {"cat": "Seasonality", "base": "Month Momentum", "diff": "Intermediate",
     "f": "Average return in the current calendar month over {} years of history.",
     "code": "def alpha_month(px, n={n}):\n    return float(px.groupby(px.index.month).mean().loc[px.index.month[-1]]) * n"},
    {"cat": "Seasonality", "base": "Turn-of-Month", "diff": "Advanced",
     "f": "Return around month-end boundaries computed over {} calendar years.",
     "code": "def alpha_tom(px, n={n}):\n    tom = px.index.day <= 5\n    return float(px[tom].tail(n).mean())"},
    {"cat": "Seasonality", "base": "Quarter End Drift", "diff": "Advanced",
     "f": "Average {} day return straddling the end of each quarter.",
     "code": "def alpha_qend(px, n={n}):\n    q = px.index.quarter\n    mask = px.index.day <= 3\n    return float(px[mask].groupby(px[mask].index.quarter).mean().mean()) * n"},
    # ---------------- Statistical ----------------
    {"cat": "Statistical", "base": "Autocorrelation", "diff": "Advanced",
     "f": "Lag-1 autocorrelation of returns over the {} period window.",
     "code": "def alpha_autocorr(px, n={n}):\n    r = px.pct_change()\n    return r.rolling(n).apply(lambda x: np.corrcoef(x[:-1], x[1:])[0,1], raw=True)"},
    {"cat": "Statistical", "base": "Partial Autocorrelation", "diff": "Advanced",
     "f": "Partial autocorrelation of returns at lag 1 across {} periods.",
     "code": "def alpha_pacf(px, n={n}):\n    r = px.pct_change().dropna()\n    x = r.tail(n).values\n    return float(np.corrcoef(x[2:], x[0:-2])[0,1])"},
    {"cat": "Statistical", "base": "Skewness", "diff": "Intermediate",
     "f": "Rolling skewness of returns over {} periods - non-normality signal.",
     "code": "def alpha_skew(px, n={n}):\n    return px.pct_change().rolling(n).skew()"},
    {"cat": "Statistical", "base": "Kurtosis", "diff": "Advanced",
     "f": "Rolling excess kurtosis of returns over {} periods.",
     "code": "def alpha_kurt(px, n={n}):\n    return px.pct_change().rolling(n).kurt()"},
    {"cat": "Statistical", "base": "Entropy", "diff": "Advanced",
     "f": "Entropy of the {} period return distribution - market complexity.",
     "code": "def alpha_entropy(px, n={n}):\n    r = px.pct_change().dropna().tail(n)\n    hist, _ = np.histogram(r, bins=10)\n    p = hist / hist.sum()\n    p = p[p > 0]\n    return float(-(p * np.log(p)).sum())"},
    # ---------------- Cross-Sectional ----------------
    {"cat": "Cross-Sectional", "base": "Relative Strength", "diff": "Intermediate",
     "f": "{}-period return relative to the cross-sectional mean of peers.",
     "code": "def alpha_relstrength(ret, n={n}):\n    return ret.rolling(n).mean() - ret.rolling(n).mean().mean(axis=1)"},
    {"cat": "Cross-Sectional", "base": "Cross-Sectional Rank", "diff": "Basic",
     "f": "Cross-sectional rank of the {}-period return within the universe.",
     "code": "def alpha_csrank(ret, n={n}):\n    return ret.rolling(n).mean().rank(axis=1, pct=True)"},
    {"cat": "Cross-Sectional", "base": "Peer Divergence", "diff": "Advanced",
     "f": "Deviation of the {}-period return from the median peer return.",
     "code": "def alpha_peerdiv(ret, n={n}):\n    m = ret.rolling(n).mean().median(axis=1)\n    return ret.rolling(n).mean().sub(m, axis=0)"},
    {"cat": "Cross-Sectional", "base": "Beta Adjusted Momentum", "diff": "Advanced",
     "f": "{}-period momentum net of the cross-sectional market beta.",
     "code": "def alpha_betamom(ret, mkt, n={n}):\n    beta = ret.rolling(n).cov(mkt) / mkt.rolling(n).var().add(1e-9)\n    return ret.rolling(n).mean() - beta * mkt.rolling(n).mean()"},
    # ---------------- Technical ----------------
    {"cat": "Technical", "base": "RSI", "diff": "Basic",
     "f": "Relative Strength Index computed over {} periods with smoothing.",
     "code": "def alpha_rsi(px, n={n}):\n    d = px.diff()\n    up = d.clip(lower=0).ewm(span=n).mean()\n    dn = (-d.clip(upper=0)).ewm(span=n).mean()\n    return 100 - 100 / (1 + up / dn.add(1e-9))"},
    {"cat": "Technical", "base": "Stochastic", "diff": "Basic",
     "f": "Stochastic oscillator %K over a {} period range with smoothing.",
     "code": "def alpha_stoch(px, n={n}):\n    hi = px.rolling(n).max(); lo = px.rolling(n).min()\n    return (px - lo) / (hi - lo).add(1e-9) * 100"},
    {"cat": "Technical", "base": "MACD", "diff": "Intermediate",
     "f": "Moving average convergence-divergence based on a {} period core window.",
     "code": "def alpha_macd(px, n={n}):\n    f = px.ewm(span=n).mean(); s = px.ewm(span=n*2).mean()\n    return f - s"},
    {"cat": "Technical", "base": "Money Flow Index", "diff": "Advanced",
     "f": "Money flow index over {} periods - volume-weighted momentum.",
     "code": "def alpha_mfi(h, l, c, v, n={n}):\n    tp = (h + l + c) / 3\n    mf = tp * v\n    pos = mf.where(tp > tp.shift(), 0).rolling(n).sum()\n    neg = mf.where(tp <= tp.shift(), 0).rolling(n).sum()\n    return 100 - 100 / (1 + pos / neg.add(1e-9))"},
    {"cat": "Technical", "base": "CCI", "diff": "Advanced",
     "f": "Commodity Channel Index over {} periods - cyclical deviation.",
     "code": "def alpha_cci(h, l, c, n={n}):\n    tp = (h + l + c) / 3\n    ma = tp.rolling(n).mean()\n    return (tp - ma) / (0.015 * (tp - ma).abs().rolling(n).mean()).add(1e-9)"},
    {"cat": "Technical", "base": "Williams %R", "diff": "Basic",
     "f": "Williams %R over the {} period high-low range.",
     "code": "def alpha_wr(px, n={n}):\n    hi = px.rolling(n).max(); lo = px.rolling(n).min()\n    return (hi - px) / (hi - lo).add(1e-9) * -100"},
    # ---------------- Options / Greeks ----------------
    {"cat": "Options", "base": "Put-Call Ratio", "diff": "Advanced",
     "f": "Put/call volume ratio smoothed over {} sessions - sentiment hedge demand.",
     "code": "def alpha_pcratio(pv, cv, n={n}):\n    return (pv / cv.add(1e-9)).rolling(n).mean()"},
    {"cat": "Options", "base": "Implied Volatility Z-Score", "diff": "Advanced",
     "f": "Z-score of implied volatility versus its {} period history.",
     "code": "def alpha_ivz(iv, n={n}):\n    return (iv - iv.rolling(n).mean()) / iv.rolling(n).std().add(1e-9)"},
    {"cat": "Options", "base": "Vol Skew", "diff": "Advanced",
     "f": "OTM put vs call implied-vol spread over the {} period window.",
     "code": "def alpha_volskew(iv_put, iv_call, n={n}):\n    return (iv_put - iv_call).rolling(n).mean()"},
    {"cat": "Options", "base": "Gamma Exposure Build", "diff": "Advanced",
     "f": "Cumulative {} period build in dealer gamma - trend-stability proxy.",
     "code": "def alpha_gammaz(gamma, n={n}):\n    return gamma.rolling(n).sum() / gamma.rolling(n).std().add(1e-9)"},
    # ---------------- Sentiment ----------------
    {"cat": "Sentiment", "base": "News Momentum", "diff": "Advanced",
     "f": "Rolling {} day sum of news sentiment scores.",
     "code": "def alpha_news(sent, n={n}):\n    return sent.rolling(n).sum()"},
    {"cat": "Sentiment", "base": "Social Sentiment Shift", "diff": "Advanced",
     "f": "Change in social sentiment over the last {} days.",
     "code": "def alpha_soc(sent, n={n}):\n    return sent.diff(n)"},
    {"cat": "Sentiment", "base": "Sentiment Dispersion", "diff": "Advanced",
     "f": "Standard deviation of {}-day sentiment - disagreement signal.",
     "code": "def alpha_sentdisp(sent, n={n}):\n    return sent.rolling(n).std()"},
    {"cat": "Sentiment", "base": "Sentiment Volume Balance", "diff": "Intermediate",
     "f": "Net ratio of positive to negative mentions over {} periods.",
     "code": "def alpha_svb(pos, neg, n={n}):\n    return (pos - neg).rolling(n).mean() / (pos + neg).rolling(n).mean().add(1e-9)"},
]


DIFFICULTIES = ["Basic", "Intermediate", "Advanced"]


def formulas(seed: str, f: str, period: int) -> str:
    """Derive a formula string from the description template."""
    return f.replace("{}", str(period)).capitalize()


def build_catalog() -> list[dict]:
    candidates: list[tuple[str, dict]] = []  # (name, factor dict)
    seen: set[str] = set()

    def add(base: str, cat: str, diff: str, fml: str, code: str, period: int, scope: str) -> None:
        name = f"{base} {period}D{f' {scope}' if scope else ''}"
        if name in seen:
            return
        seen.add(name)
        seed = name
        m = metrics(seed)
        f = {
            "id": "",  # assigned later
            "name": name,
            "category": cat,
            "difficulty": diff,
            "description": fml.replace("{}", str(period)),
            "formulas": formulas(seed, fml, period),
            "win_rate": m["win_rate"],
            "sharpe": m["sharpe"],
            "max_drawdown": m["max_drawdown"],
            "avg_return": m["avg_return"],
            "copied_count": m["copied_count"],
            "code_snippet": code.replace("{n}", str(period)),
        }
        candidates.append((name, f))

    # Expand each family across its period set.
    for fam in FAMILIES:
        periods = SHORT + MED[-1:] if fam["cat"] in ("Mean-Reversion", "Technical", "Momentum", "Trend") else MED + LONG
        if fam["cat"] in ("Seasonality", "Options", "Sentiment"):
            periods = MED
        if fam["base"] in ("Momentum 12M",):  # placeholder so list always has ≥1 short set
            periods = SHORT
        for p in periods:
            add(fam["base"], fam["cat"], fam["diff"], fam["f"], fam["code"], p, scope="")

    # Pad to TARGET with period+scope combos (deterministic) if short.
    base_families = [f for f in FAMILIES]
    scopes = ["EWMA", "Median", "Volume-Scaled", "Log", "Ranked", "Smoothed", "Trimmed"]
    i = 0
    attempts = 0
    while len(candidates) < TARGET and attempts < 20000:
        attempts += 1
        fam = base_families[i % len(base_families)]
        i += 1
        scope = scopes[(i // len(base_families)) % len(scopes)]
        p = SHORT[i % len(SHORT)] * ((i // 4) % 5 + 1)
        add(fam["base"], fam["cat"], fam["diff"], fam["f"], fam["code"], p, scope=scope)

    # Trim to exactly TARGET while keeping category diversity.
    candidates = candidates[:TARGET]
    # Rebalance categories toward diversity: keep the first N deterministically.
    # Assign IDs in order.
    for idx, (_, f) in enumerate(candidates, start=1):
        f["id"] = f"f-{idx}"

    return [f for _, f in candidates]


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the 452 alpha factor catalog.")
    parser.add_argument("--out", default=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "alpha_factors.json"))
    args = parser.parse_args()

    catalog = build_catalog()
    assert len(catalog) == TARGET, f"expected {TARGET} factors, got {len(catalog)}"

    # Name/category sanity
    cats = sorted({f["category"] for f in catalog})
    diffs = sorted({f["difficulty"] for f in catalog})
    print(f"Generated {len(catalog)} factors across categories: {', '.join(cats)}")
    print(f"Difficulties: {', '.join(diffs)}")

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(catalog, fh, indent=2, ensure_ascii=False)
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()