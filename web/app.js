"use strict";

const ELEMENT_META = {
  air: { label: "Air", color: "#185a8c" },
  fire: { label: "Fire", color: "#b83a24" },
  water: { label: "Water", color: "#0f766e" },
  earth: { label: "Earth", color: "#7c5812" },
};

const INTERVAL_SCALE_FALLBACK = new Set([
  "t2m",
  "t2m_max",
  "ts",
  "ts_minus_t2m_c",
  "precip_minus_pet_mm_day",
  "cloud_radiative_attenuation_wm2",
]);

const STRATUM_SHORT_LABELS = {
  all_valid_days: "All Valid Days",
  low_wind_lt_3ms: "Calm Wind (<3 m/s)",
  higher_wind_ge_3ms: "Higher Wind (>=3 m/s)",
  clear_moderate_cloud_lt_60pct: "Clear/Mod Cloud (<60%)",
  excluding_april_2022: "Excl. Apr 2022",
};

const state = {
  bundle: null,
  element: "air",
  regionId: "kyiv_no2_box",
  metricId: "no2_mean_molec_cm2",
  baseline: "2015_2019",
  mode: "anomaly",
  seasonWindow: "all",
  hoverPointIdx: null,
  activeStratumId: "all_valid_days",
  statsTableTab: "couplings",
  hoverScatterRegionId: null,
  ledger: [],
  mainChartGeom: null,
  scatterGeom: null,
};

const dom = {};

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = String(text);
  return node;
}

function clearNode(node) {
  while (node.firstChild) node.removeChild(node.firstChild);
}

function fmtNum(v, digits = 3) {
  if (v === null || v === undefined || !Number.isFinite(Number(v))) return "n/a";
  return Number(v).toFixed(digits);
}

function fmtSigned(v, digits = 3, suffix = "") {
  if (v === null || v === undefined || !Number.isFinite(Number(v))) return "n/a";
  const num = Number(v);
  const sign = num > 0 ? "+" : "";
  return `${sign}${num.toFixed(digits)}${suffix}`;
}

function fmtSci(v) {
  if (v === null || v === undefined || !Number.isFinite(Number(v))) return "n/a";
  return Number(v).toExponential(2);
}

function fmtCompact(v, digits = 3, signed = false) {
  if (v === null || v === undefined || !Number.isFinite(Number(v))) return "n/a";
  const num = Number(v);
  const abs = Math.abs(num);
  if (abs >= 1e5) {
    const exp = num.toExponential(2);
    return signed && num > 0 ? `+${exp}` : exp;
  }
  return signed ? fmtSigned(num, digits) : fmtNum(num, digits);
}

function isMetricIntervalScale(metricId) {
  if (state.bundle && Array.isArray(state.bundle.variable_catalog)) {
    const entry = state.bundle.variable_catalog.find((v) => v.metric_id === metricId);
    if (entry && typeof entry.is_interval_scale === "boolean") {
      return entry.is_interval_scale;
    }
  }
  return INTERVAL_SCALE_FALLBACK.has(metricId);
}

function setCanvasSize(canvas) {
  const rect = canvas.getBoundingClientRect();
  const dpr = Math.max(1, Math.min(2, window.devicePixelRatio || 1));
  const w = Math.max(300, Math.round(rect.width));
  const h = Math.max(180, Math.round(rect.height));
  if (canvas.width !== Math.round(w * dpr) || canvas.height !== Math.round(h * dpr)) {
    canvas.width = Math.round(w * dpr);
    canvas.height = Math.round(h * dpr);
  }
  const ctx = canvas.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  return { ctx, width: w, height: h };
}

function showLoadError(message) {
  dom.errorBanner.hidden = false;
  dom.errorBanner.textContent = message;
}

function setupElementsMap() {
  dom.errorBanner = document.getElementById("load-error-banner");
  dom.tabs = Array.from(document.querySelectorAll(".el-tab"));
  dom.panelExplorer = document.getElementById("panel-explorer");
  dom.selectRegion = document.getElementById("select-region");
  dom.selectMetric = document.getElementById("select-metric");
  dom.selectBaseline = document.getElementById("select-baseline");
  dom.selectMode = document.getElementById("select-mode");
  dom.selectSeason = document.getElementById("select-season");
  dom.mainChartTitle = document.getElementById("main-chart-title");
  dom.mainChartSubtitle = document.getElementById("main-chart-subtitle");
  dom.legendSeriesSwatch = document.getElementById("legend-series-swatch");
  dom.mainCanvas = document.getElementById("main-series-canvas");
  dom.monthInspector = document.getElementById("month-inspector");
  dom.kpiReadout = document.getElementById("kpi-readout");
  dom.interpReadingText = document.getElementById("interp-reading-text");
  dom.interpCautionText = document.getElementById("interp-caution-text");
  dom.strataButtons = document.getElementById("strata-buttons");
  dom.stratumDetailCard = document.getElementById("stratum-detail-card");
  dom.euWeatherStrip = document.getElementById("eu-weather-strip");
  dom.spearmanWind = document.getElementById("spearman-wind");
  dom.weatherCanvas = document.getElementById("weather-control-canvas");
  dom.boxTiaoGrid = document.getElementById("box-tiao-grid");
  dom.fireVpdCanvas = document.getElementById("fire-vpd-scatter");
  dom.scatterHoverReadout = document.getElementById("scatter-hover-readout");
  dom.regionalTable = document.getElementById("regional-contrast-table");
  dom.trendsTableNote = document.getElementById("trends-table-note");
  dom.statsTable = document.getElementById("stats-rigor-table");
  dom.showCouplingsBtn = document.getElementById("show-couplings-btn");
  dom.showTrendsBtn = document.getElementById("show-trends-btn");
  dom.limitationsList = document.getElementById("limitations-list");
  dom.provenanceBox = document.getElementById("provenance-box");
  dom.openLedgerBtn = document.getElementById("open-ledger-btn");
  dom.closeLedgerBtn = document.getElementById("close-ledger-btn");
  dom.clearLedgerBtn = document.getElementById("clear-ledger-btn");
  dom.pinCurrentBtn = document.getElementById("pin-current-btn");
  dom.ledgerCount = document.getElementById("ledger-count");
  dom.ledgerDialog = document.getElementById("case-ledger-dialog");
  dom.ledgerItems = document.getElementById("ledger-items");
  dom.exportMdBtn = document.getElementById("export-md-btn");
  dom.exportJsonBtn = document.getElementById("export-json-btn");
  dom.modalExportMdBtn = document.getElementById("modal-export-md-btn");
  dom.modalExportJsonBtn = document.getElementById("modal-export-json-btn");
}

function availableMetricsForElementAndRegion(element, regionId) {
  const reg = state.bundle.regions[regionId];
  if (!reg) return [];
  return state.bundle.variable_catalog.filter(
    (v) => v.element === element && Boolean(reg.series[v.metric_id])
  );
}

function syncRegionOptions() {
  clearNode(dom.selectRegion);
  const regList = Object.values(state.bundle.regions);
  for (const reg of regList) {
    const opt = document.createElement("option");
    opt.value = reg.region_id;
    opt.textContent = `${reg.name} (${reg.role.replaceAll("_", " ")})`;
    dom.selectRegion.appendChild(opt);
  }
  dom.selectRegion.value = state.regionId;
}

function syncMetricOptions() {
  clearNode(dom.selectMetric);
  let matches = availableMetricsForElementAndRegion(state.element, state.regionId);
  if (matches.length === 0) {
    // External EU regions lack NO2/Fire; smoothly switch to first Ukraine region or fallback metric
    state.regionId = "kyiv_no2_box";
    dom.selectRegion.value = state.regionId;
    matches = availableMetricsForElementAndRegion(state.element, state.regionId);
  }
  for (const item of matches) {
    const opt = document.createElement("option");
    opt.value = item.metric_id;
    opt.textContent = `${item.label} [${item.unit}]`;
    dom.selectMetric.appendChild(opt);
  }
  if (!matches.some((m) => m.metric_id === state.metricId)) {
    state.metricId = matches[0].metric_id;
  }
  dom.selectMetric.value = state.metricId;

  // VIIRS fire starts in 2019; disable 2015-2019 option when invalid (<2 baseline years)
  const opt15 = dom.selectBaseline.querySelector('option[value="2015_2019"]');
  if (state.metricId.startsWith("fire_")) {
    if (opt15) {
      opt15.disabled = true;
      opt15.textContent = "2015–2019 (N/A — VIIRS starts 2019)";
    }
    if (state.baseline === "2015_2019") {
      state.baseline = "2019_2021";
      dom.selectBaseline.value = state.baseline;
    }
  } else if (opt15) {
    opt15.disabled = false;
    opt15.textContent = "2015–2019 (5-yr OMI pre-COVID)";
  }
}

function activateElementTab(elementName, moveFocus = false) {
  state.element = elementName;
  state.hoverPointIdx = null;
  document.documentElement.style.setProperty("--accent-current", ELEMENT_META[elementName].color);

  for (const tab of dom.tabs) {
    const active = tab.dataset.element === elementName;
    tab.setAttribute("aria-selected", active ? "true" : "false");
    tab.tabIndex = active ? 0 : -1;
    if (active) {
      dom.panelExplorer.setAttribute("aria-labelledby", tab.id);
      if (moveFocus) tab.focus();
    }
  }
  syncMetricOptions();
  renderExplorer();
}

function getFilteredSeriesPoints() {
  const reg = state.bundle.regions[state.regionId];
  const ser = reg.series[state.metricId];
  const anomKey = state.baseline === "2015_2019" ? "anom_2015_2019" : "anom_2019_2021";
  const baseKey = state.baseline === "2015_2019" ? "baseline_2015_2019_by_month" : "baseline_2019_2021_by_month";

  const pts = [];
  for (let i = 0; i < reg.months.length; i += 1) {
    const mo = reg.month_nums[i];
    if (state.seasonWindow === "mar_aug" && (mo < 3 || mo > 8)) continue;
    const rawVal = ser.raw[i];
    const anomVal = ser[anomKey] ? ser[anomKey][i] : null;
    const val = state.mode === "anomaly" ? anomVal : rawVal;
    if (val === null || val === undefined || !Number.isFinite(val)) continue;
    const climVal = ser[baseKey] ? ser[baseKey][String(mo)] : null;
    pts.push({
      month: reg.months[i],
      year: reg.years[i],
      monthNum: mo,
      value: val,
      raw: rawVal,
      anom: anomVal,
      clim: climVal,
      flag: ser.flags[i] || "",
    });
  }
  return { reg, ser, pts };
}

function computeMarAugComparisonFromSeries(reg, ser) {
  const baseYears = state.baseline === "2015_2019" ? [2015, 2019] : [2019, 2021];
  const bVals = [];
  const tVals = [];
  const distinctBaseYears = new Set();
  for (let i = 0; i < reg.months.length; i += 1) {
    const mo = reg.month_nums[i];
    const yr = reg.years[i];
    const v = ser.raw[i];
    if (mo < 3 || mo > 8 || v === null || !Number.isFinite(v)) continue;
    if (yr >= baseYears[0] && yr <= baseYears[1]) {
      bVals.push(v);
      distinctBaseYears.add(yr);
    }
    if (yr === 2022) tVals.push(v);
  }
  if (bVals.length === 0 || tVals.length === 0 || distinctBaseYears.size < 2) return null;
  const mean = (arr) => arr.reduce((a, b) => a + b, 0) / arr.length;
  const baseMean = mean(bVals);
  const t22Mean = mean(tVals);
  const diff = t22Mean - baseMean;
  const isInterval = isMetricIntervalScale(state.metricId);
  let pct = null;
  if (!isInterval && Math.abs(baseMean) > 1e-9) {
    pct = (diff / Math.abs(baseMean)) * 100.0;
  }
  return { baseMean, t22Mean, diff, pct, isInterval, nBase: bVals.length, n22: tVals.length };
}

function renderMainCanvas(reg, ser, pts) {
  const { ctx, width, height } = setCanvasSize(dom.mainCanvas);
  ctx.clearRect(0, 0, width, height);

  if (pts.length === 0) {
    ctx.fillStyle = "#5b6472";
    ctx.font = "13px sans-serif";
    ctx.fillText("No valid points under current baseline/filter selection.", 24, 60);
    state.mainChartGeom = null;
    return;
  }

  const pad = { left: 62, right: 20, top: 20, bottom: 34 };
  const plotW = Math.max(40, width - pad.left - pad.right);
  const plotH = Math.max(40, height - pad.top - pad.bottom);

  const ys = pts.map((p) => p.value);
  let yMin = Math.min(...ys);
  let yMax = Math.max(...ys);
  if (state.mode === "anomaly") {
    yMin = Math.min(yMin, 0);
    yMax = Math.max(yMax, 0);
  }
  const span = Math.max(1e-6, yMax - yMin);
  yMin -= span * 0.12;
  yMax += span * 0.12;

  const xFor = (idx) => (pts.length === 1 ? pad.left + plotW / 2 : pad.left + (idx / (pts.length - 1)) * plotW);
  const yFor = (val) => pad.top + ((yMax - val) / (yMax - yMin)) * plotH;

  // Grid & Y ticks
  ctx.strokeStyle = "#e8e3d9";
  ctx.lineWidth = 1;
  ctx.fillStyle = "#5b6472";
  ctx.font = "11px ui-monospace, monospace";
  ctx.textAlign = "right";
  ctx.textBaseline = "middle";
  for (let t = 0; t <= 4; t += 1) {
    const val = yMin + (t / 4) * (yMax - yMin);
    const y = yFor(val);
    ctx.beginPath();
    ctx.moveTo(pad.left, y);
    ctx.lineTo(width - pad.right, y);
    ctx.stroke();
    ctx.fillText(
      Math.abs(val) >= 100 ? val.toFixed(0) : span < 0.15 ? val.toFixed(3) : val.toFixed(2),
      pad.left - 8,
      y
    );
  }

  // Zero reference line in anomaly mode
  if (state.mode === "anomaly") {
    const yZero = yFor(0);
    ctx.save();
    ctx.setLineDash([5, 4]);
    ctx.strokeStyle = "#647082";
    ctx.beginPath();
    ctx.moveTo(pad.left, yZero);
    ctx.lineTo(width - pad.right, yZero);
    ctx.stroke();
    ctx.restore();
  }

  // War onset hairline between 2022-02 and 2022-03
  const invIdx = pts.findIndex((p) => p.month >= "2022-03");
  if (invIdx > 0) {
    const xInv = 0.5 * (xFor(invIdx - 1) + xFor(invIdx));
    ctx.save();
    ctx.setLineDash([3, 3]);
    ctx.strokeStyle = "#9b2226";
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(xInv, pad.top);
    ctx.lineTo(xInv, height - pad.bottom);
    ctx.stroke();
    ctx.fillStyle = "#9b2226";
    ctx.font = "700 10px sans-serif";
    ctx.textAlign = "left";
    ctx.fillText("2022-02-24", Math.min(xInv + 4, width - 78), pad.top + 10);
    ctx.restore();
  }

  // Soft shading against 0 in anomaly mode
  const accent = ELEMENT_META[ser.element].color;
  if (state.mode === "anomaly") {
    const yZero = yFor(0);
    ctx.save();
    ctx.beginPath();
    ctx.moveTo(xFor(0), yZero);
    for (let i = 0; i < pts.length; i += 1) {
      ctx.lineTo(xFor(i), yFor(pts[i].value));
    }
    ctx.lineTo(xFor(pts.length - 1), yZero);
    ctx.closePath();
    ctx.fillStyle = `${accent}1c`;
    ctx.fill();
    ctx.restore();
  }

  // Line trace (break across gaps > 2 months cleanly)
  ctx.strokeStyle = accent;
  ctx.lineWidth = 2;
  ctx.beginPath();
  for (let i = 0; i < pts.length; i += 1) {
    const x = xFor(i);
    const y = yFor(pts[i].value);
    const prev = i > 0 ? pts[i - 1] : null;
    const monthGap = prev ? (pts[i].year - prev.year) * 12 + (pts[i].monthNum - prev.monthNum) : 0;
    if (i === 0 || monthGap > 2) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  }
  ctx.stroke();

  // Quality-flagged hollow amber diamonds & post-invasion points
  for (let i = 0; i < pts.length; i += 1) {
    const p = pts[i];
    const x = xFor(i);
    const y = yFor(p.value);
    if (p.flag) {
      ctx.save();
      ctx.translate(x, y);
      ctx.rotate(Math.PI / 4);
      ctx.fillStyle = "#ffffff";
      ctx.strokeStyle = "#b45309";
      ctx.lineWidth = 2;
      ctx.fillRect(-4.5, -4.5, 9, 9);
      ctx.strokeRect(-4.5, -4.5, 9, 9);
      ctx.restore();
    } else if (p.month >= "2022-03") {
      ctx.fillStyle = accent;
      ctx.beginPath();
      ctx.arc(x, y, 2.8, 0, Math.PI * 2);
      ctx.fill();
    }
  }

  // X ticks (annual January or first seen of each year)
  ctx.fillStyle = "#5b6472";
  ctx.font = "11px ui-monospace, monospace";
  ctx.textAlign = "center";
  ctx.textBaseline = "top";
  const seenYears = new Set();
  for (let i = 0; i < pts.length; i += 1) {
    if (!seenYears.has(pts[i].year)) {
      seenYears.add(pts[i].year);
      ctx.fillText(String(pts[i].year), xFor(i), height - pad.bottom + 8);
    }
  }

  // Active hover/focus highlight
  if (state.hoverPointIdx !== null && state.hoverPointIdx >= 0 && state.hoverPointIdx < pts.length) {
    const p = pts[state.hoverPointIdx];
    const hx = xFor(state.hoverPointIdx);
    const hy = yFor(p.value);
    ctx.save();
    ctx.strokeStyle = "#151a22";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(hx, pad.top);
    ctx.lineTo(hx, height - pad.bottom);
    ctx.stroke();
    ctx.fillStyle = "#151a22";
    ctx.beginPath();
    ctx.arc(hx, hy, 5, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();
  }

  state.mainChartGeom = { pts, pad, plotW, width, xFor };
}

function updateMonthInspector(pts, idx, ser) {
  if (idx === null || idx < 0 || idx >= pts.length) {
    dom.monthInspector.textContent = "Hover chart or focus and press Left/Right arrows to inspect exact monthly values & flags.";
    return;
  }
  const p = pts[idx];
  const baseLabel = state.baseline === "2015_2019" ? "2015–19" : "2019–21";
  const unit = ser.display_unit;
  const anomTxt = p.anom === null ? "n/a" : fmtSigned(p.anom, 3, ` ${unit}`);
  const climTxt = p.clim === null ? "n/a" : `${fmtNum(p.clim, 3)} ${unit}`;
  const flagTxt = p.flag ? `  |  QUALITY FLAG: ${p.flag}` : "";
  dom.monthInspector.textContent = `${p.month}  |  Observed: ${fmtNum(p.raw, 3)} ${unit}  |  ${baseLabel} clim: ${climTxt}  |  Anomaly: ${anomTxt}${flagTxt}`;
}

function renderExplorer() {
  const { reg, ser, pts } = getFilteredSeriesPoints();
  const baseTxt = state.baseline === "2015_2019" ? "2015–2019" : "2019–2021";
  dom.mainChartTitle.textContent = `${reg.name} — ${ser.label}`;
  dom.mainChartSubtitle.textContent =
    `${state.mode === "anomaly" ? "Deseasonalized anomaly relative to" : "Monthly values (climatology ref:"} ${baseTxt} in ${ser.display_unit}) | Area: ${reg.area_km2.toLocaleString()} km²`;
  dom.legendSeriesSwatch.style.background = ELEMENT_META[ser.element].color;

  renderMainCanvas(reg, ser, pts);
  updateMonthInspector(pts, state.hoverPointIdx, ser);

  // KPI cards & tailored Reading/Caution interpreter
  clearNode(dom.kpiReadout);
  const comp = computeMarAugComparisonFromSeries(reg, ser);
  const addKpi = (lbl, val) => {
    const box = el("div", "kpi-box");
    box.appendChild(el("span", "kpi-label", lbl));
    box.appendChild(el("span", "kpi-val", val));
    dom.kpiReadout.appendChild(box);
  };

  if (comp) {
    addKpi(`${baseTxt} Mar–Aug`, `${fmtNum(comp.baseMean, 3)} ${ser.display_unit}`);
    addKpi("2022 Mar–Aug", `${fmtNum(comp.t22Mean, 3)} ${ser.display_unit}`);
    addKpi("Absolute Shift", fmtSigned(comp.diff, 3, ` ${ser.display_unit}`));
    addKpi(
      "Relative Shift",
      comp.isInterval ? "Interval scale (no %)" : comp.pct === null ? "n/a" : fmtSigned(comp.pct, 1, "%")
    );
  } else {
    addKpi("Mar–Aug Comparison", "Baseline unavailable for this variable");
  }

  // Seasonal MK match if Kyiv
  const trendRow =
    state.regionId === "kyiv_no2_box"
      ? state.bundle.multi_element_trends_and_couplings.kyiv_seasonal_trends.find((t) => t.metric_id === state.metricId)
      : null;

  const readingParts = [];
  if (comp) {
    const pctDesc = comp.isInterval
      ? "(percent change withheld on interval Celsius scale)"
      : comp.pct !== null
        ? `(${fmtSigned(comp.pct, 1, "%")})`
        : "";
    readingParts.push(
      `In ${reg.name}, Mar–Aug 2022 averaged ${fmtNum(comp.t22Mean, 3)} ${ser.display_unit} vs ${fmtNum(comp.baseMean, 3)} in ${baseTxt}, a shift of ${fmtSigned(comp.diff, 3)} ${ser.display_unit} ${pctDesc}.`
    );
  }
  if (trendRow) {
    readingParts.push(
      `Over 2015–2022 (${trendRow.n_months} months), Kyiv Hirsch–Slack Seasonal Sen slope is ${fmtCompact(trendRow.hirsch_slack_sen_slope_per_decade, 3, true)} ${trendRow.units}/decade [95% CI: ${fmtCompact(trendRow.ci95_low_per_decade, 3, true)} to ${fmtCompact(trendRow.ci95_high_per_decade, 3, true)}], BH-FDR q = ${fmtNum(trendRow.bh_fdr_q_value, 3)}.`
    );
  } else if (state.metricId.startsWith("fire_")) {
    readingParts.push(
      "VIIRS S-NPP fire density normalizes detections by area (1,000 km²) and observed satellite days; contrast Vegetation/Conflict type0 against static Industrial Flare type2."
    );
  } else {
    readingParts.push(
      "Positive anomalies sit above the seasonal 0 baseline; compare regional anomalies in Section 3 to separate climate drying from conflict activity."
    );
  }
  dom.interpReadingText.textContent = readingParts.join(" ");

  const cautionParts = [
    "Single post-invasion season (n = 1 Mar–Aug 2022): before/after hypothesis testing remains not_assessed and standalone war causation is not_established.",
  ];
  if (state.metricId === "no2_mean_molec_cm2") {
    cautionParts.push("April 2022 OMI contains only 8/30 valid days (hollow diamond marker); verify sensitivity excluding 2022-04 and <3 m/s calm wind in Section 2.");
  } else if (state.metricId.startsWith("fire_")) {
    cautionParts.push("VIIRS S-NPP suffered orbit outage days in March and July–August 2022; rates normalize by observed satellite days.");
  } else if (isMetricIntervalScale(state.metricId)) {
    cautionParts.push("This series sits on an interval/signed balance scale without a true zero, so absolute physical shifts are valid while % changes are withheld.");
  } else {
    cautionParts.push("MERRA-2 / CERES grid resolution (~50 km) captures regional synoptic regimes rather than micro-local street conditions; an 8-year record is shorter than WMO 30-year climatology.");
  }
  dom.interpCautionText.textContent = cautionParts.join(" ");
}

function renderWeatherSection() {
  const sens = state.bundle.kyiv_daily_wind_cloud_sensitivity;
  const bt = state.bundle.kyiv_intervention_and_weather_controls;
  dom.spearmanWind.textContent = fmtNum(sens.pre_invasion_daily_spearman_no2_vs_ws10m, 3);

  clearNode(dom.strataButtons);
  for (const s of sens.strata) {
    const btn = el("button", `pill-btn${s.stratum_id === state.activeStratumId ? " active" : ""}`, STRATUM_SHORT_LABELS[s.stratum_id] || s.stratum_id);
    btn.type = "button";
    btn.setAttribute("aria-pressed", s.stratum_id === state.activeStratumId ? "true" : "false");
    btn.addEventListener("click", () => {
      state.activeStratumId = s.stratum_id;
      renderWeatherSection();
    });
    dom.strataButtons.appendChild(btn);
  }

  const active = sens.strata.find((s) => s.stratum_id === state.activeStratumId) || sens.strata[0];
  clearNode(dom.stratumDetailCard);
  dom.stratumDetailCard.appendChild(el("div", null, `${active.rule}`));
  dom.stratumDetailCard.appendChild(
    el(
      "div",
      "muted-meta",
      `Sample days — 2015–19: ${active.n_days_2015_2019}d | 2019–21: ${active.n_days_2019_2021}d | 2022: ${active.n_days_2022}d`
    )
  );
  dom.stratumDetailCard.appendChild(
    el(
      "strong",
      null,
      `2022 NO2 shift: ${fmtSigned(active.vs_2015_2019_pct_change, 2, "%")} vs 2015–19 (${fmtSigned(active.vs_2019_2021_pct_change, 2, "%")} vs 2019–21) | Mean 2022 wind: ${fmtNum(active.mean_ws10m_2022_ms, 2)} m/s`
    )
  );

  // External EU weather context cards
  clearNode(dom.euWeatherStrip);
  for (const eu of state.bundle.regional_fire_water_earth_contrast.external_eu_weather_context_2015_2019_vs_2022) {
    const card = el("div", "mini-stat");
    card.appendChild(el("span", "pill-k", eu.region_name));
    card.appendChild(
      el(
        "strong",
        null,
        `Cloud ${fmtNum(eu.cloud_amt_2015_2019_pct, 1)}→${fmtNum(eu.cloud_amt_2022_pct, 1)}% | VPD ${fmtNum(eu.vpd_2015_2019_kpa, 2)}→${fmtNum(eu.vpd_2022_kpa, 2)} kPa`
      )
    );
    dom.euWeatherStrip.appendChild(card);
  }

  // Render Observed vs Weather-Expected NO2 canvas
  const series = bt.weather_residual_monthly_series || [];
  const { ctx, width, height } = setCanvasSize(dom.weatherCanvas);
  ctx.clearRect(0, 0, width, height);
  if (series.length > 0) {
    const pad = { left: 54, right: 16, top: 18, bottom: 28 };
    const plotW = Math.max(40, width - pad.left - pad.right);
    const plotH = Math.max(40, height - pad.top - pad.bottom);
    const obs = series.map((r) => Number(r.no2_anomaly_molec_cm2) * 1e-15);
    const wth = series.map((r) => Number(r.weather_predicted_no2_anomaly_molec_cm2) * 1e-15);
    const allY = [...obs, ...wth, 0];
    let yMin = Math.min(...allY);
    let yMax = Math.max(...allY);
    const span = Math.max(0.5, yMax - yMin);
    yMin -= span * 0.1;
    yMax += span * 0.1;
    const xFor = (i) => pad.left + (i / Math.max(1, series.length - 1)) * plotW;
    const yFor = (v) => pad.top + ((yMax - v) / (yMax - yMin)) * plotH;

    // Grid & zero
    ctx.strokeStyle = "#e8e3d9";
    ctx.lineWidth = 1;
    ctx.fillStyle = "#5b6472";
    ctx.font = "10px ui-monospace, monospace";
    ctx.textAlign = "right";
    ctx.textBaseline = "middle";
    for (let t = 0; t <= 4; t += 1) {
      const val = yMin + (t / 4) * (yMax - yMin);
      const y = yFor(val);
      ctx.beginPath();
      ctx.moveTo(pad.left, y);
      ctx.lineTo(width - pad.right, y);
      ctx.stroke();
      ctx.fillText(`${val.toFixed(1)}e15`, pad.left - 5, y);
    }

    ctx.save();
    ctx.setLineDash([4, 4]);
    ctx.strokeStyle = "#7f8c8d";
    ctx.beginPath();
    ctx.moveTo(pad.left, yFor(0));
    ctx.lineTo(width - pad.right, yFor(0));
    ctx.stroke();
    ctx.restore();

    const invIdx = series.findIndex((r) => r.month >= "2022-03");
    if (invIdx > 0) {
      const xi = 0.5 * (xFor(invIdx - 1) + xFor(invIdx));
      ctx.save();
      ctx.setLineDash([3, 3]);
      ctx.strokeStyle = "#9b2226";
      ctx.beginPath();
      ctx.moveTo(xi, pad.top);
      ctx.lineTo(xi, height - pad.bottom);
      ctx.stroke();
      ctx.fillStyle = "#9b2226";
      ctx.font = "700 9.5px sans-serif";
      ctx.textAlign = "right";
      ctx.fillText("2022-02-24", Math.max(xi - 3, pad.left + 64), pad.top + 20);
      ctx.restore();
    }

    // X year labels
    ctx.fillStyle = "#5b6472";
    ctx.font = "10px ui-monospace, monospace";
    ctx.textAlign = "center";
    ctx.textBaseline = "top";
    const wYears = new Set();
    series.forEach((r, idx) => {
      const yr = String(r.month).slice(0, 4);
      if (!wYears.has(yr)) {
        wYears.add(yr);
        ctx.fillText(yr, xFor(idx), height - pad.bottom + 7);
      }
    });

    // Observed NO2
    ctx.strokeStyle = "#185a8c";
    ctx.lineWidth = 1.9;
    ctx.beginPath();
    obs.forEach((v, i) => (i === 0 ? ctx.moveTo(xFor(i), yFor(v)) : ctx.lineTo(xFor(i), yFor(v))));
    ctx.stroke();

    // Weather-expected counterfactual
    ctx.strokeStyle = "#b45309";
    ctx.lineWidth = 1.7;
    ctx.beginPath();
    wth.forEach((v, i) => (i === 0 ? ctx.moveTo(xFor(i), yFor(v)) : ctx.lineTo(xFor(i), yFor(v))));
    ctx.stroke();

    // Compact legend
    ctx.font = "600 10px sans-serif";
    ctx.textAlign = "left";
    ctx.fillStyle = "#185a8c";
    ctx.fillText("— Observed NO2 Anom", pad.left + 6, pad.top + 8);
    ctx.fillStyle = "#b45309";
    ctx.fillText("— Expected from Local Weather", pad.left + 135, pad.top + 8);
  }

  clearNode(dom.boxTiaoGrid);
  const models = [
    ["Unadjusted Step", bt.box_tiao_unadjusted_all_months],
    ["+ Meteorology (All Mo)", bt.box_tiao_weather_controlled_all_months],
    ["+ Met Excl. Apr 2022", bt.box_tiao_weather_controlled_excl_apr2022],
    ["+ Met Mar–Aug Only", bt.box_tiao_weather_controlled_mar_aug_only],
  ];
  for (const [label, m] of models) {
    const box = el("div", "mini-stat");
    box.appendChild(el("span", "pill-k", label));
    box.appendChild(
      el(
        "strong",
        null,
        `delta ${fmtSci(m.delta_step)} | R²=${fmtNum(m.r_squared, 3)} | p=${fmtNum(m.p_value_ar1, 3)}`
      )
    );
    dom.boxTiaoGrid.appendChild(box);
  }
}

function renderContrastSection() {
  const rows = state.bundle.regional_fire_water_earth_contrast.regions || [];
  const { ctx, width, height } = setCanvasSize(dom.fireVpdCanvas);
  ctx.clearRect(0, 0, width, height);

  const pad = { left: 56, right: 24, top: 20, bottom: 38 };
  const plotW = Math.max(40, width - pad.left - pad.right);
  const plotH = Math.max(40, height - pad.top - pad.bottom);

  const xs = rows.map((r) => Number(r.vpd_diff_kpa));
  const ys = rows.map((r) => Number(r.fire_type0_pct_change));
  const xMin = Math.min(-0.08, ...xs) - 0.025;
  const xMax = Math.max(0.15, ...xs) + 0.03;
  const yMin = Math.min(-70, ...ys) - 12;
  const yMax = Math.max(95, ...ys) + 14;

  const xFor = (v) => pad.left + ((v - xMin) / (xMax - xMin)) * plotW;
  const yFor = (v) => pad.top + ((yMax - v) / (yMax - yMin)) * plotH;

  // Quadrant hairlines at 0,0
  ctx.save();
  ctx.setLineDash([4, 4]);
  ctx.strokeStyle = "#949ba6";
  ctx.beginPath();
  ctx.moveTo(xFor(0), pad.top);
  ctx.lineTo(xFor(0), height - pad.bottom);
  ctx.moveTo(pad.left, yFor(0));
  ctx.lineTo(width - pad.right, yFor(0));
  ctx.stroke();
  ctx.restore();

  // Axes ticks
  ctx.fillStyle = "#5b6472";
  ctx.font = "10px ui-monospace, monospace";
  ctx.textAlign = "right";
  ctx.textBaseline = "middle";
  [-50, 0, 50].forEach((yv) => {
    const py = yFor(yv);
    ctx.fillText(`${yv}%`, pad.left - 6, py);
  });
  ctx.textAlign = "center";
  ctx.textBaseline = "top";
  [0, 0.05, 0.1, 0.15].forEach((xv) => {
    ctx.fillText(`${xv >= 0 ? "+" : ""}${xv.toFixed(2)} kPa`, xFor(xv), height - pad.bottom + 8);
  });

  const pointsMeta = [];
  for (const r of rows) {
    const px = xFor(Number(r.vpd_diff_kpa));
    const py = yFor(Number(r.fire_type0_pct_change));
    const isConflict = r.role === "war_theater_study" || r.role === "primary_urban_study";
    const fill = isConflict ? "#b83a24" : "#0f766e";
    const isSelected = r.region_id === state.regionId || r.region_id === state.hoverScatterRegionId;

    ctx.fillStyle = fill;
    ctx.beginPath();
    ctx.arc(px, py, isSelected ? 8 : 6, 0, Math.PI * 2);
    ctx.fill();
    if (isSelected) {
      ctx.strokeStyle = "#151a22";
      ctx.lineWidth = 2;
      ctx.stroke();
    }
    ctx.fillStyle = "#151a22";
    ctx.font = "600 10.5px sans-serif";
    ctx.textAlign = px > width * 0.68 ? "right" : "left";
    const lx = px > width * 0.68 ? px - 10 : px + 10;
    ctx.fillText(`${r.region_name.split(" (")[0]} (${fmtSigned(r.fire_type0_pct_change, 0, "%")})`, lx, py + 2);
    pointsMeta.push({ row: r, x: px, y: py });
  }
  state.scatterGeom = { pointsMeta };

  // Accessible Regional Table
  const tbody = dom.regionalTable.querySelector("tbody");
  clearNode(tbody);
  const colLabels = [
    "Region",
    "Fire type0 %",
    "Flare type2 %",
    "Delta VPD (kPa)",
    "Delta Soil Wet",
    "Delta T2M (C)",
  ];
  for (const r of rows) {
    const tr = document.createElement("tr");
    const th = el("th", null, r.region_name);
    th.scope = "row";
    tr.appendChild(th);

    const cells = [
      { txt: fmtSigned(r.fire_type0_pct_change, 1, "%"), cls: r.fire_type0_pct_change > 0 ? "val-pos" : "val-neg" },
      { txt: r.fire_type2_pct_change === null ? "n/a (0->0)" : fmtSigned(r.fire_type2_pct_change, 1, "%"), cls: "" },
      { txt: fmtSigned(r.vpd_diff_kpa, 3, " kPa"), cls: r.vpd_diff_kpa > 0.08 ? "val-pos" : "" },
      { txt: fmtSigned(r.gwettop_diff, 3), cls: r.gwettop_diff < -0.02 ? "val-pos" : "" },
      { txt: fmtSigned(r.t2m_diff_c, 2, " °C"), cls: "" },
    ];
    cells.forEach((c, idx) => {
      const td = el("td", `num-cell ${c.cls}`, c.txt);
      td.style.setProperty("--col-label", `"${colLabels[idx + 1]}"`);
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  }
}

function renderStatsTableSection() {
  const mt = state.bundle.multi_element_trends_and_couplings;
  const thead = dom.statsTable.querySelector("thead");
  const tbody = dom.statsTable.querySelector("tbody");
  clearNode(thead);
  clearNode(tbody);

  if (state.statsTableTab === "couplings") {
    dom.showCouplingsBtn.classList.add("active");
    dom.showTrendsBtn.classList.remove("active");
    dom.trendsTableNote.textContent =
      "AR(1)-prewhitened Kendall tau-b lagged monthly couplings (2015–2022) after Sidak lag correction and Benjamini–Hochberg FDR across 8 tested physical pairs.";
    const cols = ["Relationship", "Region", "Lag (mo)", "PW tau-b", "Sidak p", "BH-FDR q", "FDR <= 0.05"];
    const htr = document.createElement("tr");
    cols.forEach((c) => htr.appendChild(el("th", null, c)).setAttribute("scope", "col"));
    thead.appendChild(htr);

    for (const row of mt.prewhitened_cross_element_couplings) {
      const tr = document.createElement("tr");
      const th = el("th", null, row.relationship);
      th.scope = "row";
      tr.appendChild(th);
      const vals = [
        row.region_id,
        String(row.optimal_lag_months),
        fmtSigned(row.optimal_lag_pw_tau, 3),
        fmtNum(row.optimal_lag_sidak_p, 4),
        fmtNum(row.bh_fdr_q_value, 4),
        row.bh_fdr_significant_05 ? "YES" : "No",
      ];
      vals.forEach((v, i) => {
        const td = el("td", i >= 2 ? "num-cell" : null, v);
        td.style.setProperty("--col-label", `"${cols[i + 1]}"`);
        if (i === 5) {
          clearNode(td);
          td.appendChild(el("span", `sig-badge ${row.bh_fdr_significant_05 ? "sig-yes" : "sig-no"}`, v));
        }
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    }
  } else {
    dom.showTrendsBtn.classList.add("active");
    dom.showCouplingsBtn.classList.remove("active");
    dom.trendsTableNote.textContent = mt.note;
    const cols = ["Kyiv Metric", "Element", "Sen Slope / Dec", "95% CI", "Seasonal p", "BH-FDR q", "FDR <= 0.05"];
    const htr = document.createElement("tr");
    cols.forEach((c) => htr.appendChild(el("th", null, c)).setAttribute("scope", "col"));
    thead.appendChild(htr);

    for (const row of mt.kyiv_seasonal_trends) {
      const tr = document.createElement("tr");
      const th = el("th", null, `${row.label} (${row.units})`);
      th.scope = "row";
      tr.appendChild(th);
      const vals = [
        row.element.toUpperCase(),
        fmtCompact(row.hirsch_slack_sen_slope_per_decade, 3, true),
        `[${fmtCompact(row.ci95_low_per_decade, 3, true)}, ${fmtCompact(row.ci95_high_per_decade, 3, true)}]`,
        fmtNum(row.seasonal_p_value, 4),
        fmtNum(row.bh_fdr_q_value, 4),
        row.bh_fdr_significant_05 ? "YES" : "No",
      ];
      vals.forEach((v, i) => {
        const td = el("td", i >= 1 ? "num-cell" : null, v);
        td.style.setProperty("--col-label", `"${cols[i + 1]}"`);
        if (i === 5) {
          clearNode(td);
          td.appendChild(el("span", `sig-badge ${row.bh_fdr_significant_05 ? "sig-yes" : "sig-no"}`, v));
        }
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    }
  }
}

function renderLimitationsAndProvenance() {
  clearNode(dom.limitationsList);
  for (const item of state.bundle.limitations || []) {
    dom.limitationsList.appendChild(el("li", null, item));
  }
  clearNode(dom.provenanceBox);
  const prov = state.bundle.provenance || {};
  const lines = [
    `Generated UTC: ${state.bundle.generated_at_utc}`,
    `Giovanni NO2 CSV: ${prov.giovanni_no2_csv?.file || "n/a"} (sha256: ${(prov.giovanni_no2_csv?.sha256 || "").slice(0, 16)}...)`,
    `NASA POWER Monthly: ${prov.power_monthly_json?.file || "n/a"} (sha256: ${(prov.power_monthly_json?.sha256 || "").slice(0, 16)}...)`,
    `NASA POWER Kyiv Daily: ${prov.power_daily_json?.file || "n/a"} (sha256: ${(prov.power_daily_json?.sha256 || "").slice(0, 16)}...)`,
    `NO2 Monthly SHA-256: ${(prov.no2_monthly_csv_sha256 || "").slice(0, 16)}...`,
    `VIIRS Fire Monthly SHA-256: ${(prov.fire_monthly_csv_sha256 || "").slice(0, 16)}...`,
  ];
  lines.forEach((ln) => dom.provenanceBox.appendChild(el("div", null, ln)));
}

function renderLedgerModal() {
  dom.ledgerCount.textContent = String(state.ledger.length);
  clearNode(dom.ledgerItems);
  if (state.ledger.length === 0) {
    dom.ledgerItems.appendChild(
      el("p", "muted-meta", "No pinned observations yet. Use '+ Pin Active Reading to Ledger' in Section 1 to capture a finding.")
    );
    return;
  }
  state.ledger.forEach((item, idx) => {
    const card = el("div", "ledger-item");
    const head = el("div", "ledger-item-head");
    head.appendChild(el("span", null, `${idx + 1}. ${item.regionName} — ${item.metricLabel} (${item.element.toUpperCase()})`));
    const rmBtn = el("button", "btn", "Remove");
    rmBtn.type = "button";
    rmBtn.addEventListener("click", () => {
      state.ledger.splice(idx, 1);
      renderLedgerModal();
    });
    head.appendChild(rmBtn);
    card.appendChild(head);
    card.appendChild(el("div", null, item.summary));
    card.appendChild(el("div", "muted-meta", `Baseline: ${item.baseline} | Causal status: not_established (n=1 war season)`));
    dom.ledgerItems.appendChild(card);
  });
}

function pinCurrentReading() {
  const { reg, ser } = getFilteredSeriesPoints();
  const comp = computeMarAugComparisonFromSeries(reg, ser);
  const baseLabel = state.baseline === "2015_2019" ? "2015-2019" : "2019-2021";
  const pctStr = comp && !comp.isInterval && comp.pct !== null ? ` (${fmtSigned(comp.pct, 1, "%")})` : "";
  const summary = comp
    ? `Mar-Aug 2022 = ${fmtNum(comp.t22Mean, 3)} vs ${fmtNum(comp.baseMean, 3)} ${ser.display_unit}; diff = ${fmtSigned(comp.diff, 3)} ${ser.display_unit}${pctStr}.`
    : "Descriptive multi-year trajectory pinned.";
  state.ledger.push({
    pinnedAt: new Date().toISOString(),
    element: ser.element,
    regionId: reg.region_id,
    regionName: reg.name,
    metricId: state.metricId,
    metricLabel: ser.label,
    baseline: baseLabel,
    summary,
  });
  renderLedgerModal();
}

function downloadBlob(filename, content, mimeType) {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function exportMarkdownBrief() {
  const bt = state.bundle.kyiv_intervention_and_weather_controls;
  const fwe = state.bundle.regional_fire_water_earth_contrast.regions || [];
  const lines = [
    "# Ukraine & Kyiv 4-Elements Environmental Trend Brief",
    "",
    `- Generated: ${new Date().toISOString()}`,
    `- Conflict onset: ${state.bundle.conflict_start}`,
    `- Before/After Significance: ${state.bundle.status.before_after_significance}`,
    `- Causal Attribution: ${state.bundle.status.causal_attribution}`,
    "",
    "## Kyiv Air Meteorology Control (NO2 + MERRA-2)",
    `- Unadjusted Box-Tiao step: delta=${fmtSci(bt.box_tiao_unadjusted_all_months.delta_step)}, R²=${fmtNum(bt.box_tiao_unadjusted_all_months.r_squared, 4)}`,
    `- Weather-controlled Box-Tiao step: delta=${fmtSci(bt.box_tiao_weather_controlled_all_months.delta_step)}, R²=${fmtNum(bt.box_tiao_weather_controlled_all_months.r_squared, 4)}, p_ar1=${fmtNum(bt.box_tiao_weather_controlled_all_months.p_value_ar1, 4)}`,
    "",
    "## Regional Fire x Water x Earth Contrast (Mar-Aug 2022 vs 2019-2021)",
    ...fwe.map(
      (r) =>
        `- ${r.region_name}: type0 ${fmtSigned(r.fire_type0_pct_change, 1, "%")}, type2 ${r.fire_type2_pct_change === null ? "n/a" : fmtSigned(r.fire_type2_pct_change, 1, "%")}, dVPD ${fmtSigned(r.vpd_diff_kpa, 3, " kPa")}, dGWETTOP ${fmtSigned(r.gwettop_diff, 3)}`
    ),
    "",
    "## Investigator Case Ledger Notes",
    ...(state.ledger.length
      ? state.ledger.map((it, idx) => `${idx + 1}. **${it.regionName} — ${it.metricLabel}** (${it.baseline}): ${it.summary}`)
      : ["- No manual notes pinned."]),
    "",
    "## Limitations",
    ...state.bundle.limitations.map((l) => `- ${l}`),
  ];
  downloadBlob("ukraine_4elements_brief.md", `${lines.join("\n")}\n`, "text/markdown;charset=utf-8");
}

function exportJsonSnapshot() {
  const snapshot = {
    exported_at_utc: new Date().toISOString(),
    case_id: state.bundle.case_id,
    status: state.bundle.status,
    active_view: {
      element: state.element,
      region_id: state.regionId,
      metric_id: state.metricId,
      baseline: state.baseline,
      mode: state.mode,
    },
    pinned_ledger: state.ledger,
    limitations: state.bundle.limitations,
  };
  downloadBlob("ukraine_4elements_snapshot.json", JSON.stringify(snapshot, null, 2), "application/json;charset=utf-8");
}

function bindEvents() {
  // Accessible tablist click + keyboard Left/Right/Home/End navigation
  dom.tabs.forEach((tab, idx) => {
    tab.addEventListener("click", () => activateElementTab(tab.dataset.element, false));
    tab.addEventListener("keydown", (event) => {
      let next = null;
      if (event.key === "ArrowRight") next = (idx + 1) % dom.tabs.length;
      else if (event.key === "ArrowLeft") next = (idx - 1 + dom.tabs.length) % dom.tabs.length;
      else if (event.key === "Home") next = 0;
      else if (event.key === "End") next = dom.tabs.length - 1;
      if (next !== null) {
        event.preventDefault();
        activateElementTab(dom.tabs[next].dataset.element, true);
      }
    });
  });

  dom.selectRegion.addEventListener("change", () => {
    state.regionId = dom.selectRegion.value;
    state.hoverPointIdx = null;
    syncMetricOptions();
    renderExplorer();
    renderContrastSection();
  });

  dom.selectMetric.addEventListener("change", () => {
    state.metricId = dom.selectMetric.value;
    if (state.metricId.startsWith("fire_") && state.baseline === "2015_2019") {
      state.baseline = "2019_2021";
      dom.selectBaseline.value = state.baseline;
    }
    state.hoverPointIdx = null;
    renderExplorer();
  });

  dom.selectBaseline.addEventListener("change", () => {
    state.baseline = dom.selectBaseline.value;
    renderExplorer();
  });

  dom.selectMode.addEventListener("change", () => {
    state.mode = dom.selectMode.value;
    renderExplorer();
  });

  dom.selectSeason.addEventListener("change", () => {
    state.seasonWindow = dom.selectSeason.value;
    state.hoverPointIdx = null;
    renderExplorer();
  });

  // Main chart pointer & keyboard inspection
  dom.mainCanvas.addEventListener("mousemove", (event) => {
    if (!state.mainChartGeom || state.mainChartGeom.pts.length === 0) return;
    const rect = dom.mainCanvas.getBoundingClientRect();
    const mx = event.clientX - rect.left;
    let bestIdx = 0;
    let bestDist = Infinity;
    state.mainChartGeom.pts.forEach((_, idx) => {
      const dist = Math.abs(state.mainChartGeom.xFor(idx) - mx);
      if (dist < bestDist) {
        bestDist = dist;
        bestIdx = idx;
      }
    });
    if (bestIdx !== state.hoverPointIdx) {
      state.hoverPointIdx = bestIdx;
      const { reg, ser, pts } = getFilteredSeriesPoints();
      renderMainCanvas(reg, ser, pts);
      updateMonthInspector(pts, bestIdx, ser);
    }
  });

  dom.mainCanvas.addEventListener("mouseleave", () => {
    state.hoverPointIdx = null;
    const { reg, ser, pts } = getFilteredSeriesPoints();
    renderMainCanvas(reg, ser, pts);
    updateMonthInspector(pts, null, ser);
  });

  dom.mainCanvas.addEventListener("keydown", (event) => {
    if (!state.mainChartGeom || state.mainChartGeom.pts.length === 0) return;
    const n = state.mainChartGeom.pts.length;
    if (event.key === "ArrowRight") {
      event.preventDefault();
      state.hoverPointIdx = state.hoverPointIdx === null ? n - 1 : Math.min(n - 1, state.hoverPointIdx + 1);
    } else if (event.key === "ArrowLeft") {
      event.preventDefault();
      state.hoverPointIdx = state.hoverPointIdx === null ? 0 : Math.max(0, state.hoverPointIdx - 1);
    } else {
      return;
    }
    const { reg, ser, pts } = getFilteredSeriesPoints();
    renderMainCanvas(reg, ser, pts);
    updateMonthInspector(pts, state.hoverPointIdx, ser);
  });

  // Fire-VPD scatter hover & click-to-select-region
  const findNearestScatter = (event) => {
    if (!state.scatterGeom) return null;
    const rect = dom.fireVpdCanvas.getBoundingClientRect();
    const mx = event.clientX - rect.left;
    const my = event.clientY - rect.top;
    let best = null;
    let minDist = 26;
    for (const pm of state.scatterGeom.pointsMeta) {
      const d = Math.hypot(pm.x - mx, pm.y - my);
      if (d < minDist) {
        minDist = d;
        best = pm.row;
      }
    }
    return best;
  };

  dom.fireVpdCanvas.addEventListener("mousemove", (event) => {
    const hit = findNearestScatter(event);
    const hitId = hit ? hit.region_id : null;
    if (hitId !== state.hoverScatterRegionId) {
      state.hoverScatterRegionId = hitId;
      renderContrastSection();
    }
    dom.fireVpdCanvas.style.cursor = hit ? "pointer" : "default";
    if (hit) {
      dom.scatterHoverReadout.textContent =
        `${hit.region_name}: Fire type0 ${fmtSigned(hit.fire_type0_pct_change, 1, "%")} | Flare type2 ${hit.fire_type2_pct_change === null ? "n/a" : fmtSigned(hit.fire_type2_pct_change, 1, "%")} | dVPD ${fmtSigned(hit.vpd_diff_kpa, 3, " kPa")} | dSoil ${fmtSigned(hit.gwettop_diff, 3)} | dT2M ${fmtSigned(hit.t2m_diff_c, 2, " C")}`;
    }
  });

  dom.fireVpdCanvas.addEventListener("click", (event) => {
    const hit = findNearestScatter(event);
    if (hit) {
      state.regionId = hit.region_id;
      dom.selectRegion.value = hit.region_id;
      activateElementTab("fire", false);
      renderContrastSection();
    }
  });

  dom.fireVpdCanvas.addEventListener("keydown", (event) => {
    if (!state.scatterGeom || state.scatterGeom.pointsMeta.length === 0) return;
    const metas = state.scatterGeom.pointsMeta;
    const curIdx = metas.findIndex((m) => m.row.region_id === (state.hoverScatterRegionId || state.regionId));
    if (event.key === "ArrowRight") {
      event.preventDefault();
      const nxt = metas[(curIdx + 1) % metas.length].row;
      state.hoverScatterRegionId = nxt.region_id;
      dom.scatterHoverReadout.textContent =
        `${nxt.region_name}: Fire type0 ${fmtSigned(nxt.fire_type0_pct_change, 1, "%")} | Flare type2 ${nxt.fire_type2_pct_change === null ? "n/a" : fmtSigned(nxt.fire_type2_pct_change, 1, "%")} | dVPD ${fmtSigned(nxt.vpd_diff_kpa, 3, " kPa")} | dSoil ${fmtSigned(nxt.gwettop_diff, 3)} | dT2M ${fmtSigned(nxt.t2m_diff_c, 2, " C")} (press Enter to load)`;
      renderContrastSection();
    } else if (event.key === "ArrowLeft") {
      event.preventDefault();
      const prvIdx = curIdx <= 0 ? metas.length - 1 : curIdx - 1;
      const prv = metas[prvIdx].row;
      state.hoverScatterRegionId = prv.region_id;
      dom.scatterHoverReadout.textContent =
        `${prv.region_name}: Fire type0 ${fmtSigned(prv.fire_type0_pct_change, 1, "%")} | Flare type2 ${prv.fire_type2_pct_change === null ? "n/a" : fmtSigned(prv.fire_type2_pct_change, 1, "%")} | dVPD ${fmtSigned(prv.vpd_diff_kpa, 3, " kPa")} | dSoil ${fmtSigned(prv.gwettop_diff, 3)} | dT2M ${fmtSigned(prv.t2m_diff_c, 2, " C")} (press Enter to load)`;
      renderContrastSection();
    } else if (event.key === "Enter" && state.hoverScatterRegionId) {
      event.preventDefault();
      state.regionId = state.hoverScatterRegionId;
      dom.selectRegion.value = state.hoverScatterRegionId;
      activateElementTab("fire", false);
      renderContrastSection();
    }
  });

  dom.showCouplingsBtn.addEventListener("click", () => {
    state.statsTableTab = "couplings";
    renderStatsTableSection();
  });
  dom.showTrendsBtn.addEventListener("click", () => {
    state.statsTableTab = "trends";
    renderStatsTableSection();
  });

  dom.pinCurrentBtn.addEventListener("click", pinCurrentReading);
  dom.exportMdBtn.addEventListener("click", exportMarkdownBrief);
  dom.exportJsonBtn.addEventListener("click", exportJsonSnapshot);
  dom.modalExportMdBtn.addEventListener("click", exportMarkdownBrief);
  dom.modalExportJsonBtn.addEventListener("click", exportJsonSnapshot);

  // Dialog open/close + mandatory light-dismiss fallback when closedBy is unsupported
  dom.openLedgerBtn.addEventListener("click", () => {
    renderLedgerModal();
    dom.ledgerDialog.showModal();
  });
  dom.closeLedgerBtn.addEventListener("click", () => dom.ledgerDialog.close());
  dom.clearLedgerBtn.addEventListener("click", () => {
    state.ledger = [];
    renderLedgerModal();
  });

  if (!("closedBy" in HTMLDialogElement.prototype)) {
    dom.ledgerDialog.addEventListener("click", (event) => {
      if (event.target !== dom.ledgerDialog) return;
      const rect = dom.ledgerDialog.getBoundingClientRect();
      const inside =
        event.clientX >= rect.left &&
        event.clientX <= rect.right &&
        event.clientY >= rect.top &&
        event.clientY <= rect.bottom;
      if (!inside) dom.ledgerDialog.close();
    });
  }

  let resizeTimer = null;
  window.addEventListener("resize", () => {
    if (resizeTimer) clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => {
      renderExplorer();
      renderWeatherSection();
      renderContrastSection();
    }, 80);
  });
}

async function init() {
  setupElementsMap();
  bindEvents();
  try {
    const resp = await fetch("./data/ukraine_4elements_bundle.json", { cache: "no-store" });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    state.bundle = await resp.json();

    document.getElementById("status-onset").textContent = state.bundle.conflict_start;
    document.getElementById("status-ba-sig").textContent = state.bundle.status.before_after_significance;
    document.getElementById("status-causal").textContent = state.bundle.status.causal_attribution;

    const btUn = state.bundle.kyiv_intervention_and_weather_controls.box_tiao_unadjusted_all_months;
    const btWth = state.bundle.kyiv_intervention_and_weather_controls.box_tiao_weather_controlled_all_months;
    document.getElementById("status-r2-gain").textContent = `${fmtNum(btUn.r_squared, 3)} -> ${fmtNum(btWth.r_squared, 3)}`;

    syncRegionOptions();
    syncMetricOptions();
    renderExplorer();
    renderWeatherSection();
    renderContrastSection();
    renderStatsTableSection();
    renderLimitationsAndProvenance();
    renderLedgerModal();
  } catch (err) {
    showLoadError(
      `Could not load ./data/ukraine_4elements_bundle.json (${err.message}). Serve this folder over HTTP (e.g. python3 -m http.server 8080 --directory web) rather than opening directly via file://.`
    );
  }
}

window.addEventListener("DOMContentLoaded", init);
