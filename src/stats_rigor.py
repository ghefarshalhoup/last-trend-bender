"""Self-contained statistical and physical rigor engine for 4-element conflict panels.

Adapted from the 4-Elements Earth System Trend Engine to operate cleanly on
short-to-medium Earth observation records (4–8+ years, e.g., Ukraine 2015–2022)
with strict RFC 8259 JSON serialization, Lehmann-Romano test-CI duality,
AR(1)-corrected Box-Tiao step intervention, weather-controlled partial trends,
prewhitened lagged Kendall coupling, BH/BY FDR control, and FAO-56 physics.
"""

from __future__ import annotations

import json
import math
import statistics
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np

EARTH_RADIUS_KM = 6371.0088
INTERVAL_SCALE_UNITS = {"°C", "degC", "C"}
MONTH_NAMES = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]
MID_MONTH_DOY = [15, 46, 74, 105, 135, 166, 196, 227, 258, 288, 319, 349]

_STD_NORMAL = statistics.NormalDist(0.0, 1.0)


def clean_float(val: object, digits: Optional[int] = None) -> Optional[float]:
    """Return a finite Python float (optionally rounded) or None for JSON safety."""
    if val is None or isinstance(val, bool):
        return None
    try:
        f = float(val)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(f):
        return None
    return round(f, digits) if digits is not None else f


def write_strict_json(path: Path, payload: object) -> None:
    """Write RFC 8259 strict JSON atomically, rejecting NaN/Infinity tokens."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, allow_nan=False)
        fh.write("\n")
    tmp_path.replace(path)


def safe_pct_change(
    target_val: Optional[float],
    baseline_val: Optional[float],
    is_interval_scale: bool = False,
) -> Tuple[Optional[float], Optional[float], str]:
    """Compute (abs_diff, pct_change, status), withholding invalid ratios."""
    t_clean = clean_float(target_val)
    b_clean = clean_float(baseline_val)
    if t_clean is None or b_clean is None:
        return None, None, "withheld_missing_data"
    abs_diff = t_clean - b_clean
    if is_interval_scale:
        return abs_diff, None, "withheld_interval_scale"
    if b_clean <= 0.0:
        return abs_diff, None, "withheld_nonpositive_baseline"
    return abs_diff, 100.0 * abs_diff / b_clean, "computed"


# ---------------------------------------------------------------------------
# Exact Probability Distributions & Rank/Autocorrelation Helpers
# ---------------------------------------------------------------------------


def normal_cdf(z: float) -> float:
    return _STD_NORMAL.cdf(z)


def normal_two_sided_p(z: float) -> float:
    if not math.isfinite(z):
        return 1.0
    return max(0.0, min(1.0, 2.0 * (1.0 - _STD_NORMAL.cdf(abs(z)))))


def normal_ppf(p: float) -> float:
    return _STD_NORMAL.inv_cdf(p)


def _betacf(a: float, b: float, x: float) -> float:
    """Continued fraction for incomplete beta I_x(a, b) via Lentz's method."""
    max_iter = 200
    eps = 3.0e-12
    fpmin = 1.0e-30
    qab = a + b
    qap = a + 1.0
    qam = a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < fpmin:
        d = fpmin
    d = 1.0 / d
    h = d
    for m in range(1, max_iter + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < fpmin:
            d = fpmin
        c = 1.0 + aa / c
        if abs(c) < fpmin:
            c = fpmin
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < fpmin:
            d = fpmin
        c = 1.0 + aa / c
        if abs(c) < fpmin:
            c = fpmin
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < eps:
            break
    return h


def regularized_incomplete_beta(a: float, b: float, x: float) -> float:
    """Regularized incomplete beta function I_x(a, b)."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    lbeta = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
    bt = math.exp(lbeta + a * math.log(x) + b * math.log(1.0 - x))
    if x < (a + 1.0) / (a + b + 2.0):
        return bt * _betacf(a, b, x) / a
    return 1.0 - bt * _betacf(b, a, 1.0 - x) / b


def student_t_two_sided_p(t_stat: float, df: float) -> float:
    """Exact two-sided Student's t p-value for arbitrary positive df."""
    if df <= 0.0 or not math.isfinite(t_stat):
        return 1.0
    if df > 1e5:
        return normal_two_sided_p(t_stat)
    x = df / (df + t_stat * t_stat)
    return max(0.0, min(1.0, regularized_incomplete_beta(0.5 * df, 0.5, x)))


def chi2_upper_tail_p(chi2_val: float, df: int) -> float:
    """Wilson-Hilferty normal approximation for upper-tail Chi-Square p-value."""
    if chi2_val <= 0.0 or df <= 0:
        return 1.0
    k = float(df)
    z = (((chi2_val / k) ** (1.0 / 3.0)) - (1.0 - 2.0 / (9.0 * k))) / math.sqrt(2.0 / (9.0 * k))
    return max(0.0, min(1.0, 1.0 - normal_cdf(z)))


def rank_data(values: Sequence[float]) -> List[float]:
    """Assign 1-based average ranks with tie handling."""
    n = len(values)
    indexed = sorted(enumerate(values), key=lambda pair: pair[1])
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and indexed[j + 1][1] == indexed[i][1]:
            j += 1
        avg_rank = 0.5 * (i + j) + 1.0
        for k in range(i, j + 1):
            ranks[indexed[k][0]] = avg_rank
        i = j + 1
    return ranks


def autocorrelation_function(series: Sequence[float], max_lag: int) -> List[float]:
    """Compute sample ACF for lags 1..max_lag."""
    n = len(series)
    if n < 3:
        return [0.0] * max_lag
    mean_val = sum(series) / n
    centered = [x - mean_val for x in series]
    var_0 = sum(c * c for c in centered)
    if var_0 <= 1e-15:
        return [0.0] * max_lag
    acf: List[float] = []
    for k in range(1, max_lag + 1):
        if k >= n:
            acf.append(0.0)
        else:
            cov_k = sum(centered[t] * centered[t - k] for t in range(k, n))
            acf.append(cov_k / var_0)
    return acf


def marriott_pope_bias_corrected_r1(
    raw_r1: float,
    n: int,
    detrended: bool = True,
) -> float:
    """Kendall / Marriott-Pope finite-sample bias correction for sample lag-1 AR."""
    if n <= 6:
        return max(-0.95, min(0.95, raw_r1))
    if detrended:
        corrected = (n * raw_r1 + 2.0) / (n - 4.0)
    else:
        corrected = (n * raw_r1 + 1.0) / (n - 3.0)
    return max(-0.95, min(0.98, corrected))


# ---------------------------------------------------------------------------
# Spatial Geometry & Spherical Weighting
# ---------------------------------------------------------------------------


def spherical_area_weighted_mean(
    latitudes_deg: Sequence[float],
    values: Sequence[float],
) -> float:
    """Compute cos(latitude)-weighted mean across valid finite lattice values."""
    num = 0.0
    den = 0.0
    for lat, val in zip(latitudes_deg, values):
        if math.isfinite(val):
            w = max(0.0, math.cos(math.radians(lat)))
            num += w * val
            den += w
    return num / den if den > 0.0 else float("nan")


def bbox_area_km2(west: float, south: float, east: float, north: float) -> float:
    """Compute exact spherical surface area in km^2 for a lat/lon bounding box."""
    if not (-180.0 <= west < east <= 180.0):
        raise ValueError(f"Invalid longitude bounds: west={west}, east={east}")
    if not (-90.0 <= south < north <= 90.0):
        raise ValueError(f"Invalid latitude bounds: south={south}, north={north}")
    dlon = math.radians(east - west)
    sin_diff = math.sin(math.radians(north)) - math.sin(math.radians(south))
    return (EARTH_RADIUS_KM ** 2) * dlon * sin_diff


# ---------------------------------------------------------------------------
# Baseline Climatology & Matched-Month Deseasonalized Anomalies
# ---------------------------------------------------------------------------


def compute_baseline_climatology_anomalies(
    years: Sequence[int],
    months: Sequence[int],
    values: Sequence[float],
    baseline_start: int = 2015,
    baseline_end: int = 2019,
    min_baseline_years: int = 2,
) -> Tuple[List[float], List[float], Dict[int, float], Dict[int, float], List[int]]:
    """Deseasonalize a monthly series relative to a calendar-matched baseline window."""
    clim_means: Dict[int, float] = {}
    clim_stds: Dict[int, float] = {}
    active_months: List[int] = []

    for m in range(1, 13):
        all_m_vals = [
            float(v)
            for mo, v in zip(months, values)
            if mo == m and math.isfinite(v) and v > -900.0
        ]
        base_vals = [
            float(v)
            for y, mo, v in zip(years, months, values)
            if mo == m
            and baseline_start <= y <= baseline_end
            and math.isfinite(v)
            and v > -900.0
        ]
        if len(base_vals) < min_baseline_years:
            base_vals = all_m_vals

        if base_vals:
            clim_means[m] = sum(base_vals) / len(base_vals)
            clim_stds[m] = statistics.stdev(base_vals) if len(base_vals) > 1 else 1.0
            if clim_stds[m] < 1e-12:
                clim_stds[m] = 1.0
            zero_frac = sum(1 for v in all_m_vals if abs(v) < 1e-9) / len(all_m_vals)
            if zero_frac < 0.50:
                active_months.append(m)
        else:
            clim_means[m] = 0.0
            clim_stds[m] = 1.0

    if not active_months:
        active_months = list(range(1, 13))

    anomalies: List[float] = []
    z_scores: List[float] = []
    for mo, v in zip(months, values):
        if not math.isfinite(v) or v <= -900.0:
            anomalies.append(float("nan"))
            z_scores.append(float("nan"))
        else:
            anom = float(v) - clim_means[mo]
            anomalies.append(anom)
            z_scores.append(anom / clim_stds[mo])

    return anomalies, z_scores, clim_means, clim_stds, active_months


# ---------------------------------------------------------------------------
# Duality-Locked Theil-Sen & Hamed-Rao / Hirsch-Slack Seasonal MK
# ---------------------------------------------------------------------------


@dataclass
class MonthlyTrendStat:
    month: int
    month_name: str
    n_years: int
    dormant_zero_locked: bool
    sen_slope_per_decade: float
    ci_low_per_decade: float
    ci_high_per_decade: float
    mk_z_adjusted: float
    p_value_adjusted: float
    significant_05: bool

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


def mk_s_and_var0(values: Sequence[float]) -> Tuple[int, float, float]:
    """Compute Mann-Kendall statistic S, tie-corrected null variance Var0, and Kendall tau."""
    n = len(values)
    if n < 3:
        return 0, 1.0, 0.0

    s = 0
    for i in range(n - 1):
        vi = values[i]
        for j in range(i + 1, n):
            diff = values[j] - vi
            if diff > 0:
                s += 1
            elif diff < 0:
                s -= 1

    sorted_vals = sorted(values)
    tie_term = 0
    i = 0
    while i < n:
        j = i
        while j + 1 < n and sorted_vals[j + 1] == sorted_vals[i]:
            j += 1
        t_g = j - i + 1
        if t_g > 1:
            tie_term += t_g * (t_g - 1) * (2 * t_g + 5)
        i = j + 1

    var0 = max(1e-9, (n * (n - 1) * (2 * n + 5) - tie_term) / 18.0)
    tau = s / (0.5 * n * (n - 1))
    return s, var0, tau


def mk_z_from_s(s: int, var_s: float) -> float:
    if var_s <= 0.0:
        return 0.0
    if s > 0:
        return (s - 1.0) / math.sqrt(var_s)
    if s < 0:
        return (s + 1.0) / math.sqrt(var_s)
    return 0.0


def duality_locked_ci_from_slopes(
    sorted_slopes_yr: Sequence[float],
    s_stat: int,
    var_s_adjusted: float,
    confidence: float = 0.95,
    var0_baseline: Optional[float] = None,
) -> Tuple[float, float, float, float, float]:
    """Lehmann-Romano duality-locked Sen slope, CI (per decade), Z, and p-value."""
    m = len(sorted_slopes_yr)
    if m == 0:
        return 0.0, 0.0, 0.0, 0.0, 1.0

    median_slope_dec = statistics.median(sorted_slopes_yr) * 10.0
    alpha = 1.0 - confidence
    z_crit = normal_ppf(1.0 - alpha / 2.0)
    sigma_s = math.sqrt(max(1.0, var_s_adjusted))
    c_alpha = z_crit * sigma_s

    r_lo = 0.5 * (m - c_alpha)
    r_hi = 0.5 * (m + c_alpha)

    if r_lo < 0.025 * m or r_hi > 0.975 * m:
        q25 = sorted_slopes_yr[max(0, min(m - 1, int(0.25 * m)))] * 10.0
        q75 = sorted_slopes_yr[max(0, min(m - 1, int(0.75 * m)))] * 10.0
        iqr_se_dec = (q75 - q25) / (2.0 * 0.67448975)
        base_var0 = (
            var0_baseline
            if (var0_baseline is not None and var0_baseline > 0.0)
            else max(1.0, ((2.0 * m) ** 1.5) / 9.0)
        )
        vif_ratio = min(4.0, math.sqrt(max(1.0, var_s_adjusted / base_var0)))
        half_width_dec = max(abs(q75 - q25) * 0.75, z_crit * iqr_se_dec * 0.35 * vif_ratio)
        ci_low_dec = median_slope_dec - half_width_dec
        ci_high_dec = median_slope_dec + half_width_dec
    else:
        m1 = max(0, min(m - 1, int(math.floor(r_lo))))
        m2 = max(0, min(m - 1, int(math.ceil(r_hi)) - 1))
        ci_low_dec = sorted_slopes_yr[m1] * 10.0
        ci_high_dec = sorted_slopes_yr[m2] * 10.0

    z_hr = mk_z_from_s(s_stat, var_s_adjusted)
    p_hr = normal_two_sided_p(z_hr)

    ci_excludes_zero = (ci_low_dec > 0.0) or (ci_high_dec < 0.0)
    if p_hr < alpha and not ci_excludes_zero:
        n_neg = sum(1 for sl in sorted_slopes_yr if sl < -1e-12)
        n_pos = sum(1 for sl in sorted_slopes_yr if sl > 1e-12)
        s_strict = n_pos - n_neg
        n_zero = m - n_pos - n_neg
        s_tie_penalized = max(0.0, abs(s_strict) - n_zero)
        z_hr = math.copysign(max(0.0, (s_tie_penalized - 1.0) / sigma_s), s_stat)
        p_hr = max(alpha + 1e-4, normal_two_sided_p(z_hr))
    elif p_hr >= alpha and ci_excludes_zero:
        c_alpha_cc = z_crit * sigma_s + 1.0
        m1_cc = max(0, min(m - 1, int(math.floor(0.5 * (m - c_alpha_cc)))))
        m2_cc = max(0, min(m - 1, int(math.ceil(0.5 * (m + c_alpha_cc))) - 1))
        ci_low_dec = sorted_slopes_yr[m1_cc] * 10.0
        ci_high_dec = sorted_slopes_yr[m2_cc] * 10.0

    return median_slope_dec, ci_low_dec, ci_high_dec, z_hr, p_hr


def theil_sen_estimator(
    time_years: Sequence[float],
    values: Sequence[float],
    var_s_adjusted: Optional[float] = None,
    confidence: float = 0.95,
) -> Tuple[float, float, float, float]:
    """Compute Theil-Sen slope (/decade), median intercept, and duality CI."""
    n = len(values)
    if n < 2:
        return 0.0, (float(values[0]) if n == 1 else 0.0), 0.0, 0.0

    slopes_per_yr: List[float] = []
    for i in range(n - 1):
        ti, vi = time_years[i], values[i]
        for j in range(i + 1, n):
            dt = time_years[j] - ti
            if abs(dt) > 1e-9:
                slopes_per_yr.append((values[j] - vi) / dt)

    if not slopes_per_yr:
        return 0.0, float(values[0]), 0.0, 0.0

    slopes_per_yr.sort()
    s_stat, var0, _ = mk_s_and_var0(values)
    if var_s_adjusted is None:
        var_s_adjusted = var0

    slope_dec, ci_lo_dec, ci_hi_dec, _, _ = duality_locked_ci_from_slopes(
        slopes_per_yr, s_stat, var_s_adjusted, confidence, var0_baseline=var0
    )
    median_slope_yr = slope_dec / 10.0
    intercepts = [v - median_slope_yr * t for t, v in zip(time_years, values)]
    intercept = statistics.median(intercepts)
    return slope_dec, intercept, ci_lo_dec, ci_hi_dec


def hamed_rao_modified_mk(
    time_years: Sequence[float],
    values: Sequence[float],
) -> Tuple[int, float, float, float, float, float, float, float, float]:
    """Hamed & Rao (1998) + Yue & Wang (2004) variance-corrected Mann-Kendall."""
    n = len(values)
    s, var0, tau = mk_s_and_var0(values)
    z_classic = mk_z_from_s(s, var0)
    p_classic = normal_two_sided_p(z_classic)

    if n < 6:
        return s, tau, z_classic, p_classic, z_classic, p_classic, 1.0, float(n), 0.0

    slope_dec, intercept, _, _ = theil_sen_estimator(time_years, values, var0)
    slope_yr = slope_dec / 10.0
    detrended = [v - (intercept + slope_yr * t) for t, v in zip(time_years, values)]

    ranks = rank_data(detrended)
    max_lag = min(n - 3, max(1, int(n // 3)))
    acf_ranks_raw = autocorrelation_function(ranks, max_lag)
    acf_pearson_raw = autocorrelation_function(detrended, 1)[0]

    acf_equiv_normal = [
        2.0 * math.sin((math.pi / 6.0) * max(-1.0, min(1.0, r_s)))
        for r_s in acf_ranks_raw
    ]
    r1_raw = max(acf_equiv_normal[0], acf_pearson_raw)
    r1_bc = marriott_pope_bias_corrected_r1(r1_raw, n, detrended=True)

    sig_threshold = 1.96 / math.sqrt(n)
    hr_sum = 0.0
    for k_idx, rho_n in enumerate(acf_equiv_normal):
        k = k_idx + 1
        rho_bc_k = marriott_pope_bias_corrected_r1(rho_n, n - k + 1, detrended=True) if rho_n > 0 else rho_n
        if abs(rho_bc_k) >= sig_threshold:
            weight = (n - k) * (n - k - 1) * (n - k - 2)
            hr_sum += weight * rho_bc_k
    vif_empirical = 1.0 + (2.0 / (n * (n - 1) * (n - 2))) * hr_sum

    if r1_bc > 0.05:
        yw_sum = 0.0
        for k in range(1, n - 2):
            rho_k_ar1 = r1_bc ** k
            if rho_k_ar1 < 1e-5:
                break
            rho_s_k = (6.0 / math.pi) * math.asin(0.5 * rho_k_ar1)
            weight = (n - k) * (n - k - 1) * (n - k - 2)
            yw_sum += weight * rho_s_k
        vif_yw_ar1 = 1.0 + (2.0 / (n * (n - 1) * (n - 2))) * yw_sum
        ess_sum = sum((1.0 - k / float(n)) * (r1_bc ** k) for k in range(1, n))
        vif_ess = 1.0 + 2.0 * ess_sum
    else:
        vif_yw_ar1 = 1.0
        vif_ess = 1.0

    vif = max(1.0, vif_empirical, vif_yw_ar1, vif_ess)
    var_star = var0 * vif
    n_star = n / vif
    z_hr = mk_z_from_s(s, var_star)
    p_hr = normal_two_sided_p(z_hr)
    return s, tau, z_classic, p_classic, z_hr, p_hr, vif, n_star, r1_bc


def dietz_killeen_covariance_sg_sh(
    years_g: Sequence[int],
    vals_g: Sequence[float],
    years_h: Sequence[int],
    vals_h: Sequence[float],
) -> float:
    """Dietz-Killeen (1981) cross-month rank covariance Cov(S_g, S_h)."""
    map_g = dict(zip(years_g, vals_g))
    map_h = dict(zip(years_h, vals_h))
    shared_years = sorted(set(map_g).intersection(map_h))
    n = len(shared_years)
    if n < 4:
        return 0.0

    xg = [map_g[y] for y in shared_years]
    xh = [map_h[y] for y in shared_years]
    rg = rank_data(xg)
    rh = rank_data(xh)

    k_gh = 0.0
    for i in range(n - 1):
        for j in range(i + 1, n):
            prod = (xg[j] - xg[i]) * (xh[j] - xh[i])
            if prod > 0:
                k_gh += 1.0
            elif prod < 0:
                k_gh -= 1.0

    rank_cross = sum(rg[j] * rh[j] for j in range(n))
    return (k_gh + 4.0 * rank_cross - float(n) * ((n + 1.0) ** 2)) / 3.0


def hirsch_slack_seasonal_mk_and_slope(
    years: Sequence[int],
    months: Sequence[int],
    values: Sequence[float],
    active_months: Optional[Sequence[int]] = None,
    annual_vif: float = 1.0,
    min_years_per_month: int = 4,
) -> Dict[str, object]:
    """Hirsch-Slack (1984) covariance-adjusted Seasonal MK & duality-locked Sen slope."""
    active_set = set(active_months) if active_months is not None else set(range(1, 13))
    s_total = 0
    var0_diag_total = 0.0
    var_star_diag_total = 0.0
    monthly_stats: List[MonthlyTrendStat] = []
    month_series: Dict[int, Tuple[List[int], List[float]]] = {}
    month_var0_map: Dict[int, float] = {}
    intra_month_slopes_yr: List[float] = []

    for m in range(1, 13):
        pts = [
            (int(y), float(v))
            for y, mo, v in zip(years, months, values)
            if mo == m and math.isfinite(v) and v > -900.0
        ]
        if len(pts) < min_years_per_month:
            continue
        m_years_int = [p[0] for p in pts]
        m_vals = [p[1] for p in pts]
        is_dormant = m not in active_set
        m_years_flt = [float(y) for y in m_years_int]

        s_m, _, _, _, _, _, vif_m, _, _ = hamed_rao_modified_mk(m_years_flt, m_vals)
        _, var0_m, _ = mk_s_and_var0(m_vals)
        var_star_m = var0_m * vif_m

        m_slopes_yr: List[float] = []
        n_m = len(m_vals)
        for i in range(n_m - 1):
            for j in range(i + 1, n_m):
                dt = m_years_flt[j] - m_years_flt[i]
                if dt > 0:
                    m_slopes_yr.append((m_vals[j] - m_vals[i]) / dt)
        m_slopes_yr.sort()

        if not is_dormant:
            s_total += s_m
            var0_diag_total += var0_m
            var_star_diag_total += var_star_m
            month_series[m] = (m_years_int, m_vals)
            month_var0_map[m] = var0_m
            intra_month_slopes_yr.extend(m_slopes_yr)

        slope_dec, ci_lo, ci_hi, z_m_dual, p_m_dual = duality_locked_ci_from_slopes(
            m_slopes_yr, s_m, var_star_m, var0_baseline=var0_m
        )
        monthly_stats.append(
            MonthlyTrendStat(
                month=m,
                month_name=MONTH_NAMES[m - 1],
                n_years=len(m_vals),
                dormant_zero_locked=is_dormant,
                sen_slope_per_decade=round(slope_dec, 5),
                ci_low_per_decade=round(ci_lo, 5),
                ci_high_per_decade=round(ci_hi, 5),
                mk_z_adjusted=round(z_m_dual, 3),
                p_value_adjusted=round(p_m_dual, 5),
                significant_05=(p_m_dual < 0.05) and (not is_dormant),
            )
        )

    active_m_keys = sorted(month_series.keys())
    cov_off_diag = 0.0
    month_pair_corr: Dict[Tuple[int, int], float] = {}
    for idx_g in range(len(active_m_keys)):
        for idx_h in range(idx_g + 1, len(active_m_keys)):
            g, h = active_m_keys[idx_g], active_m_keys[idx_h]
            yg, vg = month_series[g]
            yh, vh = month_series[h]
            cov_gh = dietz_killeen_covariance_sg_sh(yg, vg, yh, vh)
            cov_off_diag += 2.0 * cov_gh
            denom_gh = math.sqrt(max(1.0, month_var0_map[g]) * max(1.0, month_var0_map[h]))
            month_pair_corr[(g, h)] = max(-0.95, min(0.95, cov_gh / denom_gh))

    within_yr_var = max(var0_diag_total, var0_diag_total + cov_off_diag)
    var_seasonal_total = max(
        var_star_diag_total,
        var_star_diag_total + cov_off_diag,
        within_yr_var * max(1.0, annual_vif),
        1.0,
    )

    intra_month_slopes_yr.sort()
    slope_dec, ci_lo, ci_hi, z_seas, p_seas = duality_locked_ci_from_slopes(
        intra_month_slopes_yr, s_total, var_seasonal_total, var0_baseline=var0_diag_total
    )
    homog = compute_van_belle_hughes_seasonal_homogeneity(
        monthly_stats, month_pair_corr=month_pair_corr, min_years_per_month=min_years_per_month
    )
    return {
        "sen_slope_per_decade": slope_dec,
        "ci_low_per_decade": ci_lo,
        "ci_high_per_decade": ci_hi,
        "z_seasonal": z_seas,
        "p_value_seasonal": p_seas,
        "tau_seasonal": (s_total / float(len(intra_month_slopes_yr))) if intra_month_slopes_yr else 0.0,
        "eff_vif": max(1.0, var_seasonal_total / max(1.0, var0_diag_total)),
        "monthly_stats": [mt.to_dict() for mt in monthly_stats],
        "van_belle_hughes": homog,
    }


def compute_van_belle_hughes_seasonal_homogeneity(
    monthly_trends: Sequence[MonthlyTrendStat],
    month_pair_corr: Optional[Dict[Tuple[int, int], float]] = None,
    min_years_per_month: int = 4,
) -> Dict[str, object]:
    """Combined van Belle-Hughes (1984) 4-season rank homogeneity & Cochran Q test."""
    season_map = {
        "DJF": (12, 1, 2),
        "MAM": (3, 4, 5),
        "JJA": (6, 7, 8),
        "SON": (9, 10, 11),
    }
    by_mo = {
        mt.month: mt
        for mt in monthly_trends
        if not mt.dormant_zero_locked and mt.n_years >= min_years_per_month
    }
    subregime_slopes: Dict[str, Optional[float]] = {}
    zs_4: List[float] = []
    s_betas: List[float] = []
    s_vars: List[float] = []

    non_degen_ses = sorted(
        se
        for se in ((m.ci_high_per_decade - m.ci_low_per_decade) / 3.919928 for m in by_mo.values())
        if se > 1e-7
    )
    if non_degen_ses:
        med_se = statistics.median(non_degen_ses)
        var_floor = max(1e-10, (0.35 * med_se) ** 2)
    else:
        var_floor = 1e-10

    for s_name, mos in season_map.items():
        ms = [by_mo[m] for m in mos if m in by_mo]
        if not ms:
            subregime_slopes[s_name] = None
            continue
        k = len(ms)
        b_s = sum(m.sen_slope_per_decade for m in ms) / k
        subregime_slopes[s_name] = round(b_s, 5)
        m_var_map = {
            m.month: max(var_floor, ((m.ci_high_per_decade - m.ci_low_per_decade) / 3.919928) ** 2)
            for m in ms
        }
        sum_r_intra = 0.0
        cov_beta_intra = 0.0
        if month_pair_corr and k > 1:
            for idx_i in range(k):
                for idx_j in range(idx_i + 1, k):
                    gi, hj = ms[idx_i].month, ms[idx_j].month
                    pair_key = (gi, hj) if gi < hj else (hj, gi)
                    rij = max(-0.4, min(0.95, month_pair_corr.get(pair_key, 0.0)))
                    sum_r_intra += 2.0 * rij
                    cov_beta_intra += 2.0 * rij * math.sqrt(m_var_map[gi] * m_var_map[hj])
        zs_4.append(sum(m.mk_z_adjusted for m in ms) / math.sqrt(max(float(k), float(k) + sum_r_intra)))
        s_betas.append(b_s)
        sum_m_vars = sum(m_var_map.values())
        s_vars.append(max(sum_m_vars, sum_m_vars + cov_beta_intra) / (float(k) ** 2))

    k_seas = len(zs_4)
    if k_seas < 2:
        return {
            "subregime_slopes_per_decade": subregime_slopes,
            "chi2_homogeneity": 0.0,
            "p_value": 1.0,
            "seasonal_divergence_detected": False,
        }

    z_bar4 = sum(zs_4) / k_seas
    chi2_z4 = max(0.0, sum(z * z for z in zs_4) - k_seas * (z_bar4 * z_bar4))
    ws = [1.0 / v for v in s_vars]
    w_sum = sum(ws)
    b_bar = sum(w * b for w, b in zip(ws, s_betas)) / w_sum if w_sum > 0.0 else 0.0
    q_slope4 = max(0.0, sum(w * ((b - b_bar) ** 2) for w, b in zip(ws, s_betas)))

    chi2_homog = max(chi2_z4, q_slope4)
    p_raw = chi2_upper_tail_p(chi2_homog, k_seas - 1)
    p_homog = 1.0 - (1.0 - p_raw) ** 2
    return {
        "subregime_slopes_per_decade": subregime_slopes,
        "chi2_homogeneity": round(chi2_homog, 4),
        "p_value": round(p_homog, 6),
        "seasonal_divergence_detected": bool(p_homog < 0.05),
    }


# ---------------------------------------------------------------------------
# Box-Tiao Step Intervention, Weather-Controlled Partial Trends & Breakpoints
# ---------------------------------------------------------------------------


def fit_box_tiao_step_intervention(
    time_years: Sequence[float],
    values: Sequence[float],
    intervention_year: float = 2022.0 + (2.0 / 12.0),
    covariates: Optional[Mapping[str, Sequence[float]]] = None,
) -> Dict[str, object]:
    """Fit Box-Tiao (1975) / Wang (2008) orthogonal step-intervention OLS model.

    Model:
        Y_t = alpha + beta_within * (t - tb) + delta_step * I(t >= tb) [+ gamma' * Z_t] + e_t

    Estimated simultaneously so any pure linear trend yields ``delta_step == 0.0``
    identically (0% secular-trend conflation). Standard errors and Student-t p-values
    apply Marriott-Pope bias-corrected AR(1) VIF variance scaling.
    """
    n = len(values)
    cov_names = sorted(covariates.keys()) if covariates else []
    min_obs = max(10, 5 + len(cov_names))
    if n < min_obs or len(time_years) != n:
        return {
            "status": "insufficient_observations",
            "n_obs": n,
            "intervention_year": round(intervention_year, 4),
            "covariates": cov_names,
            "delta_step": None,
            "se_delta_ar1": None,
            "ci95_low": None,
            "ci95_high": None,
            "t_stat_ar1": None,
            "p_value_ar1": None,
            "beta_within_per_decade": None,
            "covariate_betas": {},
            "r_squared": None,
            "resid_ar1_bc": None,
            "vif_ar1": None,
            "n_eff": None,
        }

    t_arr = np.asarray(time_years, dtype=float)
    y_arr = np.asarray(values, dtype=float)
    x_time = t_arr - float(intervention_year)
    x_step = np.where(t_arr >= float(intervention_year), 1.0, 0.0)
    cols = [np.ones(n, dtype=float), x_time, x_step]

    cov_vectors: List[np.ndarray] = []
    for name in cov_names:
        seq = covariates[name]
        if len(seq) != n:
            raise ValueError(f"Covariate '{name}' length {len(seq)} != series length {n}")
        arr = np.asarray(seq, dtype=float)
        if not np.all(np.isfinite(arr)):
            raise ValueError(f"Covariate '{name}' contains non-finite values")
        cov_vectors.append(arr - float(np.mean(arr)))
    cols.extend(cov_vectors)

    X = np.column_stack(cols)
    p = X.shape[1]
    if np.linalg.matrix_rank(X) < p:
        return {
            "status": "rank_deficient_design",
            "n_obs": n,
            "intervention_year": round(intervention_year, 4),
            "covariates": cov_names,
            "delta_step": None,
            "se_delta_ar1": None,
            "ci95_low": None,
            "ci95_high": None,
            "t_stat_ar1": None,
            "p_value_ar1": None,
            "beta_within_per_decade": None,
            "covariate_betas": {},
            "r_squared": None,
            "resid_ar1_bc": None,
            "vif_ar1": None,
            "n_eff": None,
        }

    beta_hat, _, _, _ = np.linalg.lstsq(X, y_arr, rcond=None)
    resids = y_arr - (X @ beta_hat)
    rss = float(np.sum(resids ** 2))
    tss = float(np.sum((y_arr - float(np.mean(y_arr))) ** 2))
    r_squared = max(0.0, min(1.0, 1.0 - rss / tss)) if tss > 1e-15 else 0.0

    r1_raw = autocorrelation_function(resids.tolist(), 1)[0]
    r1_bc = max(0.0, min(0.85, marriott_pope_bias_corrected_r1(r1_raw, n, detrended=True)))
    vif_ar1 = (1.0 + r1_bc) / max(0.1, 1.0 - r1_bc)
    n_eff = max(float(p + 2), n * (1.0 - r1_bc) / max(0.1, 1.0 + r1_bc))
    df_eff = max(2.0, n_eff - float(p))

    xtx_inv = np.linalg.inv(X.T @ X)
    s2_ar1 = max(1e-24, (rss / max(2.0, float(n - p))) * vif_ar1)
    se_delta = math.sqrt(max(1e-24, s2_ar1 * float(xtx_inv[2, 2])))
    delta_step = float(beta_hat[2])
    beta_dec = float(beta_hat[1]) * 10.0
    t_stat = delta_step / se_delta if se_delta > 0 else 0.0
    p_val = student_t_two_sided_p(t_stat, df_eff)
    z_95 = normal_ppf(0.975)  # asymptotic / conservative normal multiplier when df is small

    # Exact Student-t critical value via binary search on regularized_incomplete_beta when df_eff is finite
    lo_t, hi_t = 1.95, 15.0
    for _ in range(36):
        mid_t = 0.5 * (lo_t + hi_t)
        if student_t_two_sided_p(mid_t, df_eff) > 0.05:
            lo_t = mid_t
        else:
            hi_t = mid_t
    t_crit = 0.5 * (lo_t + hi_t) if df_eff < 200 else z_95

    cov_betas = {name: round(float(beta_hat[3 + idx]), 6) for idx, name in enumerate(cov_names)}
    return {
        "status": "assessed",
        "n_obs": n,
        "intervention_year": round(intervention_year, 4),
        "covariates": cov_names,
        "delta_step": delta_step,
        "se_delta_ar1": se_delta,
        "ci95_low": delta_step - t_crit * se_delta,
        "ci95_high": delta_step + t_crit * se_delta,
        "t_stat_ar1": round(t_stat, 4),
        "p_value_ar1": round(p_val, 6),
        "beta_within_per_decade": beta_dec,
        "covariate_betas": cov_betas,
        "r_squared": round(r_squared, 4),
        "resid_ar1_bc": round(r1_bc, 4),
        "vif_ar1": round(vif_ar1, 4),
        "n_eff": round(n_eff, 2),
        "df_eff": round(df_eff, 2),
    }


def partial_trend_controlling_covariate(
    time_years: Sequence[float],
    anomalies: Sequence[float],
    covariate: Sequence[float],
) -> Tuple[float, float, float]:
    """Partial linear trend (/decade), AR(1)-adjusted p-value, and covariate beta."""
    n = len(anomalies)
    if n < 6 or len(time_years) != n or len(covariate) != n:
        return 0.0, 1.0, 0.0

    t_mean = sum(time_years) / n
    c_mean = sum(covariate) / n
    y_mean = sum(anomalies) / n

    t_c = [t - t_mean for t in time_years]
    c_c = [c - c_mean for c in covariate]
    y_c = [y - y_mean for y in anomalies]

    stt = sum(t * t for t in t_c)
    scc = sum(c * c for c in c_c)
    stc = sum(t * c for t, c in zip(t_c, c_c))
    sty = sum(t * y for t, y in zip(t_c, y_c))
    scy = sum(c * y for c, y in zip(c_c, y_c))

    det = stt * scc - stc * stc
    if abs(det) <= 1e-12:
        return 0.0, 1.0, 0.0

    beta_t_yr = (scc * sty - stc * scy) / det
    gamma_c = (stt * scy - stc * sty) / det
    residuals = [y_c[i] - (beta_t_yr * t_c[i] + gamma_c * c_c[i]) for i in range(n)]
    rss = sum(e * e for e in residuals)
    r1_bc = marriott_pope_bias_corrected_r1(autocorrelation_function(residuals, 1)[0], n, detrended=True)
    r1_pos = max(0.0, min(0.95, r1_bc))
    n_eff = n * (1.0 - r1_pos) / (1.0 + r1_pos)
    df_eff = max(2.0, n_eff - 3.0)

    s2 = rss / df_eff
    se_beta_t = math.sqrt(max(1e-24, s2 * (scc / det)))
    t_stat = beta_t_yr / se_beta_t if se_beta_t > 0 else 0.0
    p_val = student_t_two_sided_p(t_stat, df_eff)
    return beta_t_yr * 10.0, p_val, gamma_c


@dataclass
class BreakpointResult:
    detected: bool
    break_year: Optional[float]
    break_index: Optional[int]
    supremum_t_statistic: float
    f_statistic: float
    davies_p_value: float
    delta_bic: float
    pre_break_slope_per_decade: Optional[float]
    post_break_slope_per_decade: Optional[float]
    regime_reversal: bool
    residual_step_jump_year: Optional[float]
    residual_pettitt_p: float
    interpretation: str

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


def _fit_continuous_hinge_ols(
    time_years: Sequence[float],
    values: Sequence[float],
    knot_t: float,
) -> Tuple[float, float, float, float]:
    n = len(values)
    x1 = [t - knot_t for t in time_years]
    x2 = [max(0.0, t - knot_t) for t in time_years]
    X = np.column_stack([np.ones(n, dtype=float), np.asarray(x1, dtype=float), np.asarray(x2, dtype=float)])
    if np.linalg.matrix_rank(X) < 3:
        return float("inf"), 0.0, 0.0, 0.0
    y_arr = np.asarray(values, dtype=float)
    sol, _, _, _ = np.linalg.lstsq(X, y_arr, rcond=None)
    resids = y_arr - (X @ sol)
    return float(np.sum(resids ** 2)), float(sol[0]), float(sol[1]), float(sol[2])


def pettitt_on_detrended_residuals(
    time_years: Sequence[float],
    detrended_residuals: Sequence[float],
    min_segment: int = 6,
) -> Tuple[Optional[float], float]:
    n = len(detrended_residuals)
    if n < 2 * min_segment + 2:
        return None, 1.0
    ranks = rank_data(detrended_residuals)
    cum_rank = 0.0
    max_k = -1.0
    best_idx = min_segment
    for t_idx in range(n - 1):
        cum_rank += ranks[t_idx]
        t_count = t_idx + 1
        if min_segment <= t_count <= n - min_segment:
            u_t = abs(2.0 * cum_rank - t_count * (n + 1.0))
            if u_t > max_k:
                max_k = u_t
                best_idx = t_idx
    p_val = max(0.0, min(1.0, 2.0 * math.exp((-6.0 * max_k * max_k) / (float(n) ** 3 + float(n) ** 2))))
    return round(float(time_years[best_idx]), 3), round(p_val, 5)


def structural_hinge_breakpoint_analysis(
    time_years: Sequence[float],
    values: Sequence[float],
    min_segment: int = 6,
) -> BreakpointResult:
    """Continuous piecewise-linear hinge breakpoint test with Davies (1987) bound."""
    n = len(values)
    if n < 2 * min_segment + 2:
        return BreakpointResult(
            detected=False,
            break_year=None,
            break_index=None,
            supremum_t_statistic=0.0,
            f_statistic=0.0,
            davies_p_value=1.0,
            delta_bic=0.0,
            pre_break_slope_per_decade=None,
            post_break_slope_per_decade=None,
            regime_reversal=False,
            residual_step_jump_year=None,
            residual_pettitt_p=1.0,
            interpretation="Insufficient sample length for structural breakpoint detection.",
        )

    t_mean = sum(time_years) / n
    y_mean = sum(values) / n
    sxx = sum((t - t_mean) ** 2 for t in time_years)
    sxy = sum((t - t_mean) * (y - y_mean) for t, y in zip(time_years, values))
    a1 = sxy / sxx if sxx > 1e-12 else 0.0
    a0 = y_mean - a1 * t_mean
    resids_m0 = [y - (a0 + a1 * t) for t, y in zip(time_years, values)]
    rss_0 = max(1e-12, sum(e * e for e in resids_m0))

    step_yr, step_p = pettitt_on_detrended_residuals(time_years, resids_m0, min_segment)

    best_rss1 = float("inf")
    best_idx = min_segment
    knot_records: List[Tuple[int, float, float]] = []
    for idx in range(min_segment, n - min_segment):
        rss_1, _, _, b2 = _fit_continuous_hinge_ols(time_years, values, time_years[idx])
        rss_1 = max(1e-12, rss_1)
        knot_records.append((idx, rss_1, b2))
        if rss_1 < best_rss1:
            best_rss1 = rss_1
            best_idx = idx

    knot_star = float(time_years[best_idx])
    _, best_b0, best_b1, best_b2 = _fit_continuous_hinge_ols(time_years, values, knot_star)
    resids_m1 = [
        values[i] - (best_b0 + best_b1 * (time_years[i] - knot_star) + best_b2 * max(0.0, time_years[i] - knot_star))
        for i in range(n)
    ]

    r1_m0 = marriott_pope_bias_corrected_r1(autocorrelation_function(resids_m0, 1)[0], n, detrended=True)
    r1_m1 = marriott_pope_bias_corrected_r1(autocorrelation_function(resids_m1, 1)[0], n, detrended=True)
    r1_pos = max(0.0, min(0.90, 0.45 * max(0.0, r1_m0) + 0.55 * max(0.0, r1_m1)))
    n_eff = max(8.0, n * (1.0 - r1_pos) / (1.0 + r1_pos))
    nu = max(3.0, n_eff - 3.0)

    t_process: List[float] = []
    for _, rss_j, b2_j in knot_records:
        f1_j = max(0.0, (rss_0 - rss_j) / (rss_j / nu))
        sign_j = 1.0 if b2_j >= 0.0 else -1.0
        t_process.append(sign_j * math.sqrt(f1_j))

    total_variation_v = sum(abs(t_process[j + 1] - t_process[j]) for j in range(len(t_process) - 1))
    f1_sup = max(0.0, (rss_0 - best_rss1) / (best_rss1 / nu))
    m_sup = math.sqrt(f1_sup)
    p_pointwise = student_t_two_sided_p(m_sup, nu)
    upcrossing_penalty = (total_variation_v / math.pi) * ((1.0 + (m_sup * m_sup) / nu) ** (-0.5 * nu))
    davies_p = max(0.0, min(1.0, p_pointwise + upcrossing_penalty))

    bic_0 = n_eff * math.log(rss_0 / n_eff) + 2.0 * math.log(n_eff)
    bic_1 = n_eff * math.log(best_rss1 / n_eff) + 4.0 * math.log(n_eff)
    delta_bic = bic_0 - bic_1

    pre_slope_dec = best_b1 * 10.0
    post_slope_dec = (best_b1 + best_b2) * 10.0
    detected = (davies_p < 0.05) and (delta_bic > 2.0)
    max_abs_seg = max(abs(pre_slope_dec), abs(post_slope_dec))
    min_abs_seg = min(abs(pre_slope_dec), abs(post_slope_dec))
    reversal = (
        detected
        and (pre_slope_dec * post_slope_dec < 0.0)
        and (max_abs_seg > 1e-9)
        and (min_abs_seg >= 0.15 * max_abs_seg)
    )
    break_yr = round(knot_star, 3)
    interp = (
        f"Structural slope shift at {break_yr} (Davies p={davies_p:.4f}, dBIC={delta_bic:+.1f})."
        if detected
        else f"Single linear slope preferred over piecewise hinge (Davies p={davies_p:.4f}, dBIC={delta_bic:+.1f})."
    )
    return BreakpointResult(
        detected=detected,
        break_year=break_yr if detected else None,
        break_index=best_idx if detected else None,
        supremum_t_statistic=round(m_sup, 3),
        f_statistic=round(f1_sup, 3),
        davies_p_value=round(davies_p, 5),
        delta_bic=round(delta_bic, 2),
        pre_break_slope_per_decade=round(pre_slope_dec, 5),
        post_break_slope_per_decade=round(post_slope_dec, 5),
        regime_reversal=reversal,
        residual_step_jump_year=step_yr if step_p < 0.05 else None,
        residual_pettitt_p=step_p,
        interpretation=interp,
    )


# ---------------------------------------------------------------------------
# Pre-Whitened Lagged Coupling & Multiple-Testing FDR
# ---------------------------------------------------------------------------


def _count_tie_groups(values: Sequence[float], tol: float = 1e-12) -> List[int]:
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    ties: List[int] = []
    i = 0
    while i < n:
        j = i
        while j + 1 < n and abs(sorted_vals[j + 1] - sorted_vals[i]) <= tol:
            j += 1
        t_g = j - i + 1
        if t_g > 1:
            ties.append(t_g)
        i = j + 1
    return ties


def kendall_tau_b_bivariate(
    x: Sequence[float],
    y: Sequence[float],
    cross_vif: float = 1.0,
) -> Tuple[float, float, float]:
    """Kendall's tau-b with tie corrections and cross-persistence VIF scaling."""
    n = len(x)
    if n < 5 or len(y) != n:
        return 0.0, 0.0, 1.0

    n_pairs = n * (n - 1) // 2
    s_xy = 0
    for i in range(n - 1):
        xi, yi = x[i], y[i]
        for j in range(i + 1, n):
            prod = (x[j] - xi) * (y[j] - yi)
            if prod > 1e-12:
                s_xy += 1
            elif prod < -1e-12:
                s_xy -= 1

    ties_x = _count_tie_groups(x)
    ties_y = _count_tie_groups(y)
    t_x = sum(t * (t - 1) // 2 for t in ties_x)
    t_y = sum(t * (t - 1) // 2 for t in ties_y)
    denom = math.sqrt(max(1.0, float(n_pairs - t_x) * float(n_pairs - t_y)))
    tau_b = s_xy / denom if denom > 0 else 0.0

    v0 = n * (n - 1) * (2 * n + 5)
    vt_x = sum(t * (t - 1) * (2 * t + 5) for t in ties_x)
    vt_y = sum(t * (t - 1) * (2 * t + 5) for t in ties_y)
    v1 = (
        sum(t * (t - 1) * (t - 2) for t in ties_x)
        * sum(t * (t - 1) * (t - 2) for t in ties_y)
        / max(1.0, 9.0 * n * (n - 1) * (n - 2))
    )
    v2 = (
        sum(t * (t - 1) for t in ties_x)
        * sum(t * (t - 1) for t in ties_y)
        / max(1.0, 2.0 * n * (n - 1))
    )
    var_s = max(1e-9, ((v0 - vt_x - vt_y) / 18.0 + v1 + v2) * max(1.0, cross_vif))
    z = (s_xy - 1.0) / math.sqrt(var_s) if s_xy > 0 else ((s_xy + 1.0) / math.sqrt(var_s) if s_xy < 0 else 0.0)
    return round(tau_b, 4), round(z, 3), round(normal_two_sided_p(z), 6)


def compute_lagged_monthly_impulse_coupling(
    years_x: Sequence[int],
    months_x: Sequence[int],
    values_x: Sequence[float],
    years_y: Sequence[int],
    months_y: Sequence[int],
    values_y: Sequence[float],
    max_lag_months: int = 2,
    baseline_start: int = 2015,
    baseline_end: int = 2021,
    min_common_months: int = 20,
) -> Dict[str, object]:
    """Deseasonalized, detrended, AR(1)-prewhitened lagged monthly Kendall coupling."""
    vx = [(int(y), int(m), float(v)) for y, m, v in zip(years_x, months_x, values_x) if math.isfinite(v) and v > -900.0]
    vy = [(int(y), int(m), float(v)) for y, m, v in zip(years_y, months_y, values_y) if math.isfinite(v) and v > -900.0]
    empty = {
        "n_common_months": 0,
        "lag_0_monthly_pw_tau": None,
        "lag_0_monthly_pw_p": None,
        "optimal_lag_months": None,
        "optimal_lag_pw_tau": None,
        "optimal_lag_pw_p": None,
        "optimal_lag_sidak_p": None,
    }
    if len(vx) < min_common_months or len(vy) < min_common_months:
        return empty

    ax, _, _, _, _ = compute_baseline_climatology_anomalies(
        [t[0] for t in vx], [t[1] for t in vx], [t[2] for t in vx],
        baseline_start=baseline_start, baseline_end=baseline_end, min_baseline_years=1,
    )
    ay, _, _, _, _ = compute_baseline_climatology_anomalies(
        [t[0] for t in vy], [t[1] for t in vy], [t[2] for t in vy],
        baseline_start=baseline_start, baseline_end=baseline_end, min_baseline_years=1,
    )

    map_x = {(t[0], t[1]): a for t, a in zip(vx, ax)}
    map_y = {(t[0], t[1]): a for t, a in zip(vy, ay)}
    common_ym = sorted(set(map_x).intersection(map_y))
    n_m = len(common_ym)
    if n_m < min_common_months:
        return empty

    t_m = [ym[0] + (ym[1] - 0.5) / 12.0 for ym in common_ym]
    xm = [map_x[ym] for ym in common_ym]
    ym_vec = [map_y[ym] for ym in common_ym]

    tm_bar = sum(t_m) / n_m
    xm_bar = sum(xm) / n_m
    ym_bar = sum(ym_vec) / n_m
    stt = max(1e-12, sum((t - tm_bar) ** 2 for t in t_m))
    bx = sum((t - tm_bar) * (x - xm_bar) for t, x in zip(t_m, xm)) / stt
    by = sum((t - tm_bar) * (y - ym_bar) for t, y in zip(t_m, ym_vec)) / stt
    xd = [x - (xm_bar + bx * (t - tm_bar)) for t, x in zip(t_m, xm)]
    yd = [y - (ym_bar + by * (t - tm_bar)) for t, y in zip(t_m, ym_vec)]

    rx = max(0.0, min(0.85, marriott_pope_bias_corrected_r1(autocorrelation_function(xd, 1)[0], n_m, detrended=True)))
    ry = max(0.0, min(0.85, marriott_pope_bias_corrected_r1(autocorrelation_function(yd, 1)[0], n_m, detrended=True)))
    m_idx = [ym[0] * 12 + (ym[1] - 1) for ym in common_ym]
    x_by_idx = dict(zip(m_idx, xd))
    y_by_idx = dict(zip(m_idx, yd))

    ex_drv_map: Dict[int, float] = {}
    ex_rsp_map: Dict[int, float] = {}
    ey_drv_map: Dict[int, float] = {}
    ey_rsp_map: Dict[int, float] = {}
    for t_idx in m_idx:
        if (t_idx - 1) in x_by_idx and (t_idx - 1) in y_by_idx:
            x_cur, x_prv = x_by_idx[t_idx], x_by_idx[t_idx - 1]
            y_cur, y_prv = y_by_idx[t_idx], y_by_idx[t_idx - 1]
            ex_drv_map[t_idx] = x_cur - rx * x_prv
            ex_rsp_map[t_idx] = x_cur - 0.5 * rx * x_prv
            ey_drv_map[t_idx] = y_cur - ry * y_prv
            ey_rsp_map[t_idx] = y_cur - 0.5 * ry * y_prv

    sorted_innov_idx = sorted(ex_drv_map.keys())
    best_lag = 0
    best_tau = 0.0
    best_p = 1.0
    lag0_tau: Optional[float] = None
    lag0_p: Optional[float] = None
    lags_tested = 0
    min_pairs = max(12, min_common_months - 4)

    for lag in range(-max_lag_months, max_lag_months + 1):
        xs_l: List[float] = []
        ys_l: List[float] = []
        if lag > 0:
            for t_idx in sorted_innov_idx:
                if (t_idx + lag) in ey_rsp_map:
                    xs_l.append(ex_drv_map[t_idx])
                    ys_l.append(ey_rsp_map[t_idx + lag])
        elif lag < 0:
            for t_idx in sorted_innov_idx:
                if (t_idx + lag) in ey_drv_map:
                    xs_l.append(ex_rsp_map[t_idx])
                    ys_l.append(ey_drv_map[t_idx + lag])
        else:
            use_x_as_drv = rx <= ry
            for t_idx in sorted_innov_idx:
                if use_x_as_drv:
                    xs_l.append(ex_drv_map[t_idx])
                    ys_l.append(ey_rsp_map[t_idx])
                else:
                    xs_l.append(ex_rsp_map[t_idx])
                    ys_l.append(ey_drv_map[t_idx])

        if len(xs_l) < min_pairs:
            continue
        lags_tested += 1
        r_xl = max(0.0, min(0.85, autocorrelation_function(xs_l, 1)[0]))
        r_yl = max(0.0, min(0.85, autocorrelation_function(ys_l, 1)[0]))
        c_vif = (1.0 + r_xl * r_yl) / max(0.1, 1.0 - r_xl * r_yl)
        tau_l, _, p_l = kendall_tau_b_bivariate(xs_l, ys_l, cross_vif=c_vif)
        if lag == 0:
            lag0_tau = tau_l
            lag0_p = p_l
        if abs(tau_l) > abs(best_tau) + 1e-12 or (
            abs(abs(tau_l) - abs(best_tau)) <= 1e-12 and abs(lag) < abs(best_lag)
        ):
            best_tau = tau_l
            best_p = p_l
            best_lag = lag

    if lags_tested == 0:
        return {**empty, "n_common_months": n_m}

    best_p_sidak = (
        round(min(1.0, 1.0 - ((1.0 - min(1.0, max(0.0, best_p))) ** lags_tested)), 6)
        if best_p < 1.0
        else 1.0
    )
    return {
        "n_common_months": n_m,
        "lag_0_monthly_pw_tau": lag0_tau,
        "lag_0_monthly_pw_p": lag0_p,
        "optimal_lag_months": best_lag,
        "optimal_lag_pw_tau": best_tau,
        "optimal_lag_pw_p": best_p,
        "optimal_lag_sidak_p": best_p_sidak,
    }


def bh_q_values(p_values: Sequence[float]) -> List[float]:
    """Benjamini-Hochberg (1995) step-up FDR q-values in original index order."""
    m = len(p_values)
    if m == 0:
        return []
    indexed = sorted(enumerate(p_values), key=lambda kv: float(kv[1]))
    q_vals = [1.0] * m
    prev_q = 1.0
    for rank_idx in range(m - 1, -1, -1):
        orig_idx, p_val = indexed[rank_idx]
        rank = rank_idx + 1
        prev_q = min(prev_q, (float(p_val) * m) / rank)
        q_vals[orig_idx] = min(1.0, prev_q)
    return q_vals


def by_q_values(p_values: Sequence[float]) -> List[float]:
    """Benjamini-Yekutieli (2001) arbitrary-dependence FDR q-values."""
    m = len(p_values)
    if m == 0:
        return []
    c_m = sum(1.0 / k for k in range(1, m + 1))
    scaled = [min(1.0, float(p) * c_m) for p in p_values]
    return bh_q_values(scaled)


# ---------------------------------------------------------------------------
# Astronomical & Elevation-Aware FAO-56 Penman-Monteith PET & VPD
# ---------------------------------------------------------------------------


def extraterrestrial_solar_ra_mj_m2_day(lat_deg: float, month: int) -> float:
    """FAO-56 Eq. (21)-(28) extraterrestrial radiation R_a (MJ m^-2 day^-1)."""
    j_doy = MID_MONTH_DOY[max(1, min(12, month)) - 1]
    phi = math.radians(max(-66.5, min(66.5, lat_deg)))
    dr = 1.0 + 0.033 * math.cos(2.0 * math.pi * j_doy / 365.0)
    delta = 0.409 * math.sin(2.0 * math.pi * j_doy / 365.0 - 1.39)
    ws = math.acos(max(-1.0, min(1.0, -math.tan(phi) * math.tan(delta))))
    g_sc = 0.0820
    ra = (
        (24.0 * 60.0 / math.pi)
        * g_sc
        * dr
        * (ws * math.sin(phi) * math.sin(delta) + math.cos(phi) * math.cos(delta) * math.sin(ws))
    )
    return max(0.5, ra)


def compute_fao56_vpd_and_pet_series(
    t2m_c: Sequence[float],
    t2m_max_c: Sequence[float],
    t2m_min_c: Sequence[float],
    rh2m_pct: Sequence[float],
    sw_dwn_mj_m2_day: Sequence[float],
    ws10m_m_s: Sequence[float],
    lat_deg: float = 0.0,
    elevation_m: float = 180.0,
    months: Optional[Sequence[int]] = None,
    ps_kpa_series: Optional[Sequence[float]] = None,
    qv2m_g_kg_series: Optional[Sequence[float]] = None,
    clrsky_sw_dwn_mj_m2_day: Optional[Sequence[float]] = None,
    albedo_series: Optional[Sequence[float]] = None,
) -> Dict[str, List[float]]:
    """Compute physical VPD (kPa), FAO-56 PET (mm/day), and radiative/aero terms."""
    n = len(t2m_c)
    vpd_series: List[float] = []
    pet_series: List[float] = []
    pet_rad_series: List[float] = []
    pet_aero_series: List[float] = []

    p_kpa_fallback = 101.3 * (((293.0 - 0.0065 * elevation_m) / 293.0) ** 5.26)
    sigma_sb = 4.903e-9

    for idx in range(n):
        t = float(t2m_c[idx])
        tmax = float(t2m_max_c[idx])
        tmin = float(t2m_min_c[idx])
        rh = float(rh2m_pct[idx])
        rs = float(sw_dwn_mj_m2_day[idx])
        u10 = float(ws10m_m_s[idx])
        if any(not math.isfinite(x) or x <= -900.0 for x in (t, tmax, tmin, rh, rs, u10)):
            vpd_series.append(float("nan"))
            pet_series.append(float("nan"))
            pet_rad_series.append(float("nan"))
            pet_aero_series.append(float("nan"))
            continue

        mo = int(months[idx]) if (months is not None and idx < len(months)) else ((idx % 12) + 1)
        p_kpa = (
            float(ps_kpa_series[idx])
            if (ps_kpa_series is not None and idx < len(ps_kpa_series) and math.isfinite(ps_kpa_series[idx]) and ps_kpa_series[idx] > 20.0)
            else p_kpa_fallback
        )

        e0_tmax = 0.6108 * math.exp((17.27 * tmax) / (tmax + 237.3))
        e0_tmin = 0.6108 * math.exp((17.27 * tmin) / (tmin + 237.3))
        e0_t = 0.6108 * math.exp((17.27 * t) / (t + 237.3))
        es = 0.5 * (e0_tmax + e0_tmin)
        ea_rh = es * max(0.0, min(100.0, rh)) / 100.0

        if (
            qv2m_g_kg_series is not None
            and idx < len(qv2m_g_kg_series)
            and math.isfinite(qv2m_g_kg_series[idx])
            and qv2m_g_kg_series[idx] > 0.0
        ):
            qv_kg_kg = float(qv2m_g_kg_series[idx]) * 1.0e-3
            ea_qv = (qv_kg_kg * p_kpa) / (0.622 + 0.378 * qv_kg_kg)
            ea = min(es, ea_qv)
        else:
            ea = ea_rh

        vpd = max(0.0, es - ea)
        vpd_series.append(round(vpd, 5))

        delta = (4098.0 * e0_t) / ((t + 237.3) ** 2)
        u2 = max(0.15, u10 * (4.87 / math.log(67.8 * 10.0 - 5.42)))

        ra = extraterrestrial_solar_ra_mj_m2_day(lat_deg, mo)
        r_so = (
            max(0.5, float(clrsky_sw_dwn_mj_m2_day[idx]))
            if (
                clrsky_sw_dwn_mj_m2_day is not None
                and idx < len(clrsky_sw_dwn_mj_m2_day)
                and math.isfinite(clrsky_sw_dwn_mj_m2_day[idx])
                and clrsky_sw_dwn_mj_m2_day[idx] > 0.5
            )
            else max(0.5, (0.75 + 2.0e-5 * elevation_m) * ra)
        )
        rel_sw = min(1.0, max(0.3, max(0.0, rs) / r_so))
        cloud_factor = max(0.05, 1.35 * rel_sw - 0.35)

        alb_eff = (
            float(albedo_series[idx])
            if (albedo_series is not None and idx < len(albedo_series) and math.isfinite(albedo_series[idx]) and 0.0 <= albedo_series[idx] <= 1.0)
            else 0.23
        )
        r_ns = (1.0 - alb_eff) * max(0.0, rs)
        t_k4 = 0.5 * (((tmax + 273.16) ** 4) + ((tmin + 273.16) ** 4))
        vapor_factor = max(0.05, 0.34 - 0.14 * math.sqrt(max(0.01, ea)))
        r_nl = sigma_sb * t_k4 * vapor_factor * cloud_factor
        r_n_raw = r_ns - r_nl

        t_prev = float(t2m_c[idx - 1]) if (idx > 0 and math.isfinite(t2m_c[idx - 1]) and t2m_c[idx - 1] > -900.0) else None
        t_next = float(t2m_c[idx + 1]) if (idx < n - 1 and math.isfinite(t2m_c[idx + 1]) and t2m_c[idx + 1] > -900.0) else None
        if t_prev is not None and t_next is not None:
            g_soil = 0.07 * (t_next - t_prev)
        elif t_next is not None:
            g_soil = 0.14 * (t_next - t)
        elif t_prev is not None:
            g_soil = 0.14 * (t - t_prev)
        else:
            g_soil = 0.0

        lambda_t = max(2.2, 2.501 - 0.002361 * t)
        inv_lambda = 1.0 / lambda_t
        gamma = (0.00163 * p_kpa) / lambda_t
        avail_energy = max(0.0, r_n_raw - g_soil)
        den = delta + gamma * (1.0 + 0.34 * u2)
        if den > 0.0:
            pet_rad = max(0.0, (inv_lambda * delta * avail_energy) / den)
            pet_aero = max(0.0, (gamma * (900.0 / (t + 273.0)) * u2 * vpd) / den)
            et0 = pet_rad + pet_aero
        else:
            pet_rad, pet_aero, et0 = 0.0, 0.0, 0.0

        pet_series.append(round(et0, 5))
        pet_rad_series.append(round(pet_rad, 5))
        pet_aero_series.append(round(pet_aero, 5))

    return {
        "vpd_kpa": vpd_series,
        "pet_mm_day": pet_series,
        "pet_rad_mm_day": pet_rad_series,
        "pet_aero_mm_day": pet_aero_series,
    }
