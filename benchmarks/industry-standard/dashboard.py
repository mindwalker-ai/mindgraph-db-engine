#!/usr/bin/env python3
"""Build a self-contained HTML dashboard from MindGraph benchmark evidence."""

from __future__ import annotations

import argparse
import html
import json
import math
from pathlib import Path
from typing import Any


REQUIRED_TOP_LEVEL = {
    "schemaVersion",
    "title",
    "generatedAt",
    "status",
    "release",
    "environment",
    "methodology",
    "suites",
    "artifacts",
}


def _number(value: Any, path: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{path} must be numeric")
    if not math.isfinite(float(value)) or float(value) < 0:
        raise ValueError(f"{path} must be a finite non-negative number")
    return float(value)


def _metric_value(value: Any, path: str) -> float:
    if isinstance(value, dict):
        if "median" not in value:
            raise ValueError(f"{path} must contain median")
        median = _number(value["median"], f"{path}.median")
        runs = value.get("runs", [])
        if not isinstance(runs, list):
            raise ValueError(f"{path}.runs must be an array")
        for index, run in enumerate(runs):
            _number(run, f"{path}.runs[{index}]")
        return median
    return _number(value, path)


def validate(data: dict[str, Any]) -> None:
    missing = REQUIRED_TOP_LEVEL.difference(data)
    if missing:
        raise ValueError(f"missing top-level fields: {', '.join(sorted(missing))}")
    if data["schemaVersion"] != 1:
        raise ValueError("schemaVersion must be 1")
    if data["status"] not in {"verified", "partial", "failed"}:
        raise ValueError("status must be verified, partial, or failed")
    if not isinstance(data["suites"], list) or not data["suites"]:
        raise ValueError("suites must be a non-empty array")

    suite_ids: set[str] = set()
    for suite_index, suite in enumerate(data["suites"]):
        path = f"suites[{suite_index}]"
        for field in ("id", "title", "description", "unit", "lowerIsBetter", "metrics", "series", "validation"):
            if field not in suite:
                raise ValueError(f"{path}.{field} is required")
        if suite["id"] in suite_ids:
            raise ValueError(f"duplicate suite id: {suite['id']}")
        suite_ids.add(suite["id"])
        if not isinstance(suite["metrics"], list) or not suite["metrics"]:
            raise ValueError(f"{path}.metrics must be a non-empty array")
        if not isinstance(suite["series"], list) or not suite["series"]:
            raise ValueError(f"{path}.series must be a non-empty array")

        metric_ids = []
        for metric_index, metric in enumerate(suite["metrics"]):
            for field in ("id", "label"):
                if field not in metric:
                    raise ValueError(f"{path}.metrics[{metric_index}].{field} is required")
            metric_ids.append(metric["id"])
        if len(metric_ids) != len(set(metric_ids)):
            raise ValueError(f"{path}.metrics contains duplicate ids")

        for series_index, series in enumerate(suite["series"]):
            series_path = f"{path}.series[{series_index}]"
            for field in ("id", "label", "kind", "values"):
                if field not in series:
                    raise ValueError(f"{series_path}.{field} is required")
            if series["kind"] not in {"measured", "control", "reference"}:
                raise ValueError(f"{series_path}.kind must be measured, control, or reference")
            for metric_id in metric_ids:
                if metric_id not in series["values"]:
                    raise ValueError(f"{series_path}.values.{metric_id} is required")
                value = series["values"][metric_id]
                if value is not None:
                    _metric_value(value, f"{series_path}.values.{metric_id}")


def _json_for_script(data: dict[str, Any]) -> str:
    return (
        json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )


def render(data: dict[str, Any]) -> str:
    validate(data)
    title = html.escape(str(data["title"]))
    payload = _json_for_script(data)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="dark">
  <title>{title}</title>
  <style>
    :root {{
      --ink-950: #07111f;
      --ink-900: #0b1728;
      --ink-850: #102036;
      --ink-800: #162940;
      --ink-700: #28405b;
      --ink-400: #8ea5bd;
      --ink-200: #cbd8e6;
      --paper: #edf5fb;
      --signal: #21d7c5;
      --signal-strong: #05ae9f;
      --amber: #f6b94a;
      --danger: #f06a6a;
      --radius: 12px;
      --shadow: 0 24px 64px rgba(1, 9, 18, .32);
    }}
    * {{ box-sizing: border-box; }}
    html {{ scroll-behavior: smooth; }}
    body {{
      margin: 0;
      min-height: 100vh;
      min-height: 100dvh;
      color: var(--paper);
      background:
        radial-gradient(circle at 88% -10%, rgba(33, 215, 197, .13), transparent 34rem),
        radial-gradient(circle at -8% 30%, rgba(246, 185, 74, .08), transparent 30rem),
        var(--ink-950);
      font-family: "Avenir Next", Avenir, "Segoe UI", sans-serif;
      line-height: 1.5;
    }}
    body::before {{
      content: "";
      position: fixed;
      inset: 0;
      pointer-events: none;
      opacity: .16;
      background-image: linear-gradient(rgba(255,255,255,.025) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,.025) 1px, transparent 1px);
      background-size: 48px 48px;
      mask-image: linear-gradient(to bottom, black, transparent 72%);
    }}
    button, a {{ -webkit-tap-highlight-color: transparent; }}
    button:focus-visible, a:focus-visible {{ outline: 3px solid var(--amber); outline-offset: 3px; }}
    .shell {{ width: min(1280px, calc(100% - 48px)); margin: 0 auto; padding: 48px 0 96px; position: relative; }}
    .eyebrow, .mono {{ font-family: "IBM Plex Mono", "SFMono-Regular", Consolas, monospace; }}
    .eyebrow {{ color: var(--signal); font-size: 12px; letter-spacing: .16em; text-transform: uppercase; font-weight: 700; }}
    .hero {{ display: grid; grid-template-columns: minmax(0, 1.6fr) minmax(280px, .7fr); gap: 48px; align-items: end; padding: 48px 0 40px; }}
    h1 {{ font-size: clamp(42px, 7vw, 88px); line-height: .98; letter-spacing: -.055em; margin: 16px 0 24px; max-width: 900px; }}
    .lead {{ color: var(--ink-200); font-size: clamp(17px, 2vw, 21px); max-width: 760px; margin: 0; }}
    .release-card {{ background: linear-gradient(145deg, rgba(22, 41, 64, .92), rgba(11, 23, 40, .8)); border: 1px solid rgba(142, 165, 189, .2); border-radius: var(--radius); padding: 24px; box-shadow: var(--shadow); }}
    .release-card dl {{ margin: 20px 0 0; display: grid; gap: 12px; }}
    .release-card div {{ display: grid; grid-template-columns: 96px 1fr; gap: 16px; }}
    dt {{ color: var(--ink-400); font-size: 12px; text-transform: uppercase; letter-spacing: .08em; }}
    dd {{ margin: 0; overflow-wrap: anywhere; }}
    .status {{ display: inline-flex; align-items: center; gap: 8px; font-size: 13px; font-weight: 700; text-transform: uppercase; letter-spacing: .08em; }}
    .status::before {{ content: ""; width: 8px; height: 8px; border-radius: 50%; background: var(--signal); box-shadow: 0 0 18px var(--signal); }}
    .status.partial::before {{ background: var(--amber); box-shadow: 0 0 18px var(--amber); }}
    .status.failed::before {{ background: var(--danger); box-shadow: 0 0 18px var(--danger); }}
    .kpis {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 16px; margin: 8px 0 48px; }}
    .kpi {{ background: rgba(16, 32, 54, .68); border-top: 2px solid var(--signal); padding: 24px; min-height: 152px; }}
    .kpi:nth-child(3), .kpi:nth-child(4) {{ border-top-color: var(--amber); }}
    .kpi strong {{ display: block; font-size: clamp(28px, 4vw, 48px); line-height: 1; letter-spacing: -.04em; margin: 12px 0; }}
    .kpi span {{ color: var(--ink-400); font-size: 14px; }}
    .tabs {{ display: flex; gap: 8px; overflow-x: auto; padding: 8px 0 24px; scrollbar-width: thin; }}
    .tab {{ min-height: 44px; padding: 0 18px; border-radius: 999px; border: 1px solid var(--ink-700); background: transparent; color: var(--ink-200); font: inherit; font-weight: 650; cursor: pointer; white-space: nowrap; transition: background 160ms ease, color 160ms ease, border-color 160ms ease; }}
    .tab:hover {{ border-color: var(--signal); color: var(--paper); }}
    .tab:active {{ background: var(--ink-800); }}
    .tab[aria-selected="true"] {{ background: var(--signal); border-color: var(--signal); color: var(--ink-950); }}
    .suite {{ display: none; }}
    .suite.active {{ display: block; animation: reveal 220ms ease-out; }}
    @keyframes reveal {{ from {{ opacity: 0; transform: translateY(8px); }} to {{ opacity: 1; transform: translateY(0); }} }}
    .suite-head {{ display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 24px; align-items: start; margin: 16px 0 24px; }}
    h2 {{ font-size: clamp(28px, 4vw, 44px); line-height: 1.1; letter-spacing: -.035em; margin: 0 0 12px; }}
    .suite-head p {{ color: var(--ink-400); max-width: 760px; margin: 0; }}
    .toggle {{ display: flex; background: var(--ink-900); border: 1px solid var(--ink-700); border-radius: 999px; padding: 4px; }}
    .toggle button {{ min-height: 40px; padding: 0 16px; border: 0; border-radius: 999px; background: transparent; color: var(--ink-400); cursor: pointer; font: inherit; font-size: 13px; font-weight: 700; }}
    .toggle button.active {{ color: var(--paper); background: var(--ink-700); }}
    .chart-card {{ background: rgba(11, 23, 40, .84); border: 1px solid rgba(142, 165, 189, .18); border-radius: var(--radius); padding: 24px; box-shadow: var(--shadow); }}
    .legend {{ display: flex; flex-wrap: wrap; gap: 16px 24px; margin-bottom: 32px; }}
    .legend-item {{ display: inline-flex; align-items: center; gap: 8px; color: var(--ink-200); font-size: 13px; }}
    .legend-swatch {{ width: 22px; height: 8px; border-radius: 999px; background: var(--series-color); }}
    .legend-item.reference .legend-swatch {{ background: repeating-linear-gradient(90deg, var(--series-color) 0 5px, transparent 5px 8px); border: 1px solid var(--series-color); }}
    .metric-grid {{ display: grid; gap: 24px; }}
    .metric {{ display: grid; grid-template-columns: minmax(120px, 180px) minmax(0, 1fr); gap: 24px; align-items: center; }}
    .metric-name {{ font-weight: 700; }}
    .metric-id {{ color: var(--ink-400); font-size: 12px; display: block; margin-top: 4px; }}
    .bars {{ display: grid; gap: 8px; }}
    .bar-row {{ display: grid; grid-template-columns: minmax(0, 1fr) 96px; gap: 16px; align-items: center; min-height: 32px; }}
    .bar-track {{ height: 14px; background: rgba(142, 165, 189, .12); border-radius: 999px; overflow: hidden; }}
    .bar {{ height: 100%; width: max(3px, calc(var(--bar-size) * 1%)); border-radius: inherit; background: var(--series-color); transition: width 280ms ease; }}
    .bar.reference {{ background: repeating-linear-gradient(90deg, var(--series-color) 0 6px, transparent 6px 10px); border: 1px solid var(--series-color); }}
    .bar-value {{ font-family: "IBM Plex Mono", "SFMono-Regular", Consolas, monospace; font-variant-numeric: tabular-nums; text-align: right; color: var(--paper); font-size: 13px; }}
    .validation {{ margin: 24px 0 0; padding: 16px 20px; border-left: 3px solid var(--signal); background: rgba(33, 215, 197, .07); color: var(--ink-200); }}
    .validation.partial {{ border-left-color: var(--amber); background: rgba(246, 185, 74, .07); }}
    .table-wrap {{ overflow-x: auto; margin-top: 24px; border-radius: var(--radius); border: 1px solid rgba(142, 165, 189, .16); }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; min-width: 720px; }}
    th {{ color: var(--ink-400); text-align: left; font-size: 11px; text-transform: uppercase; letter-spacing: .08em; font-weight: 700; background: var(--ink-900); }}
    th, td {{ padding: 12px 16px; border-bottom: 1px solid rgba(142, 165, 189, .12); }}
    th:not(:first-child), td:not(:first-child) {{ text-align: right; font-variant-numeric: tabular-nums; }}
    .cell-detail {{ display: block; margin-top: 3px; color: var(--ink-400); font-size: 11px; white-space: nowrap; }}
    tbody tr:hover td {{ background: rgba(33, 215, 197, .04); }}
    .methodology {{ margin-top: 64px; display: grid; grid-template-columns: minmax(0, 1.3fr) minmax(300px, .7fr); gap: 24px; }}
    .panel {{ background: rgba(16, 32, 54, .6); border-radius: var(--radius); padding: 24px; }}
    .panel h3 {{ margin: 0 0 16px; font-size: 20px; }}
    .panel ul {{ margin: 0; padding-left: 20px; color: var(--ink-200); }}
    .panel li + li {{ margin-top: 8px; }}
    .environment {{ display: grid; grid-template-columns: 120px 1fr; gap: 12px 16px; margin: 0; }}
    .artifact-list {{ display: grid; gap: 8px; margin-top: 16px; }}
    .artifact-list a {{ color: var(--signal); text-decoration: none; overflow-wrap: anywhere; }}
    .artifact-list a:hover {{ text-decoration: underline; }}
    footer {{ color: var(--ink-400); margin-top: 64px; padding-top: 24px; border-top: 1px solid rgba(142, 165, 189, .16); font-size: 13px; }}
    @media (max-width: 900px) {{
      .hero, .methodology {{ grid-template-columns: 1fr; }}
      .kpis {{ grid-template-columns: repeat(2, 1fr); }}
      .suite-head {{ grid-template-columns: 1fr; }}
      .toggle {{ width: max-content; }}
    }}
    @media (max-width: 620px) {{
      .shell {{ width: min(100% - 32px, 1280px); padding-top: 24px; }}
      .hero {{ gap: 32px; padding-top: 32px; }}
      .kpis {{ grid-template-columns: 1fr; }}
      .metric {{ grid-template-columns: 1fr; gap: 8px; }}
      .chart-card {{ padding: 16px; }}
      .bar-row {{ grid-template-columns: minmax(0, 1fr) 80px; }}
    }}
    @media (prefers-reduced-motion: reduce) {{ *, *::before, *::after {{ scroll-behavior: auto !important; animation: none !important; transition: none !important; }} }}
  </style>
</head>
<body>
  <main class="shell">
    <header class="hero">
      <div>
        <div class="eyebrow">Reproducible performance evidence</div>
        <h1 id="page-title"></h1>
        <p class="lead" id="page-subtitle"></p>
      </div>
      <aside class="release-card" aria-label="Benchmark release metadata">
        <div class="status" id="status-label"></div>
        <dl id="release-meta"></dl>
      </aside>
    </header>

    <section class="kpis" id="kpis" aria-label="Benchmark summary"></section>
    <nav class="tabs" id="tabs" aria-label="Benchmark suites" role="tablist"></nav>
    <div id="suite-panels"></div>

    <section class="methodology" id="methodology">
      <article class="panel">
        <div class="eyebrow">Methodology</div>
        <h3>How to interpret this evidence</h3>
        <ul id="method-list"></ul>
      </article>
      <aside class="panel">
        <div class="eyebrow">Execution environment</div>
        <h3>Host fingerprint</h3>
        <dl class="environment" id="environment"></dl>
        <div class="artifact-list" id="artifacts"></div>
      </aside>
    </section>
    <footer id="footer"></footer>
  </main>
  <script id="benchmark-data" type="application/json">{payload}</script>
  <script>
    (() => {{
      const data = JSON.parse(document.getElementById('benchmark-data').textContent);
      const colors = ['#21d7c5', '#f6b94a', '#7aa8ff', '#f06a6a', '#a78bfa'];
      const escapeHtml = (value) => String(value).replace(/[&<>"']/g, char => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[char]));
      const numeric = value => value && typeof value === 'object' ? Number(value.median) : Number(value);
      const format = (value, unit) => {{
        if (value === null || value === undefined) return 'N/A';
        const number = numeric(value);
        if (unit === 'seconds') return `${{number < 0.01 ? number.toFixed(3) : number < 1 ? number.toFixed(2) : number.toFixed(2)}} s`;
        if (unit === 'milliseconds') return `${{number.toFixed(number < 10 ? 2 : 1)}} ms`;
        if (unit === 'ratio') return `${{number.toFixed(1)}}×`;
        if (unit === 'megabytes') return `${{number.toFixed(1)}} MB`;
        return `${{number.toLocaleString()}} ${{unit}}`;
      }};
      const formatCell = (value, unit) => {{
        if (value === null || value === undefined) return 'N/A';
        const primary = escapeHtml(format(value, unit));
        if (!value || typeof value !== 'object' || value.min === undefined || value.max === undefined) return primary;
        const detail = `${{format(value.min, unit)}}–${{format(value.max, unit)}} · CV ${{Number(value.coefficientOfVariationPercent || 0).toFixed(1)}}%`;
        return `${{primary}}<span class="cell-detail">${{escapeHtml(detail)}}</span>`;
      }};
      const validationTotals = data.suites.reduce((acc, suite) => {{
        if (suite.validation.countsTowardTotal !== false) {{ acc.passed += suite.validation.passed || 0; acc.total += suite.validation.total || 0; }}
        return acc;
      }}, {{passed: 0, total: 0}});
      const measuredMetrics = data.suites.reduce((count, suite) => count + suite.metrics.length, 0);
      document.getElementById('page-title').textContent = data.title;
      document.getElementById('page-subtitle').textContent = data.subtitle || 'Measured results, public references, and raw evidence in one auditable report.';
      const status = document.getElementById('status-label');
      status.textContent = data.status;
      status.classList.add(data.status);
      const releaseRows = [
        ['Version', data.release.version], ['Commit', data.release.commit], ['Measured', data.generatedAt], ['Harness', data.release.harnessCommit]
      ];
      document.getElementById('release-meta').innerHTML = releaseRows.map(([key, value]) => `<div><dt>${{escapeHtml(key)}}</dt><dd class="mono">${{escapeHtml(value)}}</dd></div>`).join('');
      const kpis = [
        ['Validated', `${{validationTotals.passed}}/${{validationTotals.total}}`, 'algorithm and query outputs'],
        ['Coverage', measuredMetrics, 'reported benchmark metrics'],
        ['Compute', data.environment.cpuCount, 'logical CPUs on the measured host'],
        ['Memory', data.environment.memoryGiB + ' GiB', 'host RAM; JVM heap is disclosed below']
      ];
      document.getElementById('kpis').innerHTML = kpis.map(([label, value, note]) => `<article class="kpi"><div class="eyebrow">${{escapeHtml(label)}}</div><strong>${{escapeHtml(value)}}</strong><span>${{escapeHtml(note)}}</span></article>`).join('');

      const tabs = document.getElementById('tabs');
      const panels = document.getElementById('suite-panels');
      const activate = id => {{
        document.querySelectorAll('.tab').forEach(tab => tab.setAttribute('aria-selected', tab.dataset.target === id ? 'true' : 'false'));
        document.querySelectorAll('.suite').forEach(panel => panel.classList.toggle('active', panel.id === `suite-${{id}}`));
      }};

      data.suites.forEach((suite, suiteIndex) => {{
        const tab = document.createElement('button');
        tab.className = 'tab'; tab.type = 'button'; tab.role = 'tab'; tab.dataset.target = suite.id;
        tab.setAttribute('aria-controls', `suite-${{suite.id}}`); tab.setAttribute('aria-selected', suiteIndex === 0 ? 'true' : 'false');
        tab.textContent = suite.title; tab.addEventListener('click', () => activate(suite.id)); tabs.appendChild(tab);

        const panel = document.createElement('section');
        panel.className = `suite${{suiteIndex === 0 ? ' active' : ''}}`; panel.id = `suite-${{suite.id}}`; panel.role = 'tabpanel';
        const toggle = suite.unit === 'ratio' ? '' : `<div class="toggle" aria-label="Chart scale"><button type="button" class="active" data-scale="linear">Linear</button><button type="button" data-scale="log">Log</button></div>`;
        panel.innerHTML = `<div class="suite-head"><div><h2>${{escapeHtml(suite.title)}}</h2><p>${{escapeHtml(suite.description)}}</p></div>${{toggle}}</div><div class="chart-card"><div class="legend"></div><div class="metric-grid"></div><div class="validation${{suite.validation.passed === suite.validation.total ? '' : ' partial'}}"></div></div><div class="table-wrap"></div>`;
        panels.appendChild(panel);
        const legend = panel.querySelector('.legend');
        suite.series.forEach((series, index) => {{
          const item = document.createElement('span'); item.className = `legend-item ${{series.kind}}`; item.style.setProperty('--series-color', colors[index % colors.length]);
          item.innerHTML = `<span class="legend-swatch"></span><span>${{escapeHtml(series.label)}} · ${{escapeHtml(series.kind)}}</span>`; legend.appendChild(item);
        }});
        const grid = panel.querySelector('.metric-grid');
        const renderBars = scale => {{
          grid.innerHTML = '';
          suite.metrics.forEach(metric => {{
            const values = suite.series.map(series => series.values[metric.id] == null ? null : numeric(series.values[metric.id]));
            const positive = values.filter(value => value !== null && value > 0);
            const max = positive.length ? Math.max(...positive) : 1;
            const min = positive.length ? Math.min(...positive) : 1;
            const size = value => {{
              if (value === null) return 0;
              if (scale === 'log' && value > 0 && max > min) return 8 + 92 * (Math.log10(value) - Math.log10(min)) / (Math.log10(max) - Math.log10(min));
              return max === 0 ? 0 : 100 * value / max;
            }};
            const rows = suite.series.map((series, index) => {{
              const raw = series.values[metric.id]; const value = raw == null ? null : numeric(raw);
              const range = raw && typeof raw === 'object' && raw.min !== undefined && raw.max !== undefined ? ` title="range ${{escapeHtml(format(raw.min, suite.unit))}}–${{escapeHtml(format(raw.max, suite.unit))}}"` : '';
              return `<div class="bar-row"${{range}}><div class="bar-track"><div class="bar ${{series.kind}}" style="--bar-size:${{size(value)}};--series-color:${{colors[index % colors.length]}}"></div></div><div class="bar-value">${{value === null ? 'N/A' : escapeHtml(format(raw, suite.unit))}}</div></div>`;
            }}).join('');
            const block = document.createElement('div'); block.className = 'metric';
            block.innerHTML = `<div class="metric-name">${{escapeHtml(metric.label)}}<span class="metric-id mono">${{escapeHtml(metric.id)}}</span></div><div class="bars">${{rows}}</div>`; grid.appendChild(block);
          }});
        }};
        renderBars('linear');
        panel.querySelectorAll('[data-scale]').forEach(button => button.addEventListener('click', () => {{ panel.querySelectorAll('[data-scale]').forEach(item => item.classList.toggle('active', item === button)); renderBars(button.dataset.scale); }}));
        const validation = panel.querySelector('.validation');
        const validationLabel = suite.validation.label || `${{suite.validation.passed}} of ${{suite.validation.total}} outputs validated.`;
        validation.innerHTML = `<strong>${{escapeHtml(validationLabel)}}</strong> ${{escapeHtml((suite.validation.notes || []).join(' '))}}`;
        const header = suite.series.map(series => `<th scope="col">${{escapeHtml(series.label)}}</th>`).join('');
        const rows = suite.metrics.map(metric => `<tr><td>${{escapeHtml(metric.label)}}</td>${{suite.series.map(series => `<td>${{formatCell(series.values[metric.id], suite.unit)}}</td>`).join('')}}</tr>`).join('');
        panel.querySelector('.table-wrap').innerHTML = `<table><thead><tr><th scope="col">Metric</th>${{header}}</tr></thead><tbody>${{rows}}</tbody></table>`;
      }});

      const methodology = [...(data.methodology.summary || []), ...(data.methodology.disclosures || [])];
      document.getElementById('method-list').innerHTML = methodology.map(item => `<li>${{escapeHtml(item)}}</li>`).join('');
      document.getElementById('environment').innerHTML = Object.entries(data.environment).map(([key, value]) => `<dt>${{escapeHtml(key.replace(/([A-Z])/g, ' $1'))}}</dt><dd class="mono">${{escapeHtml(value)}}</dd>`).join('');
      document.getElementById('artifacts').innerHTML = `<h3>Raw evidence</h3>` + data.artifacts.map(artifact => `<a href="${{escapeHtml(artifact.path)}}">${{escapeHtml(artifact.label)}}</a>`).join('');
      document.getElementById('footer').textContent = `Generated from schema v${{data.schemaVersion}} evidence. Reference series are never presented as measurements from this host.`;
    }})();
  </script>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="benchmark result JSON")
    parser.add_argument("output", type=Path, help="dashboard HTML")
    args = parser.parse_args()
    data = json.loads(args.input.read_text(encoding="utf-8"))
    output = render(data)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(output, encoding="utf-8")
    print(f"dashboard: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
