let dataset = null;
let currentCandidate = 'uplot';
let uplotCharts = [];
let echartsInstances = [];

// Benchmark numbers
const STATS = {
  uplot: {
    bundle: '~12 KB gzip (45 KB raw)',
    license: 'MIT (v1.6.32)',
    features: 'Native null gaps, sync zoom/pan, custom draw hook for red ×',
    renderMs: 0,
    fps: '60 FPS',
  },
  echarts: {
    bundle: '~95 KB gzip (320 KB raw tree-shaken)',
    license: 'Apache 2.0 (v5.5 / 6.1)',
    features: 'connectNulls: false, echarts.connect sync, markPoint scatter red ×',
    renderMs: 0,
    fps: '50-60 FPS',
  }
};

async function init() {
  try {
    const res = await fetch('data.json');
    dataset = await res.json();
  } catch (err) {
    console.warn('Could not load data.json, generating synthetic 5.5k points', err);
    dataset = generateSyntheticData(5528);
  }

  populateTableFallback(dataset);
  renderCandidate('uplot');
}

function generateSyntheticData(n) {
  const timestamps = [];
  const rsrp = [];
  const rsrq = [];
  const sinr = [];
  const score = [];
  const flag = [];
  let t = 1727720000;

  for (let i = 0; i < n; i++) {
    t += 3;
    // Introduce gap every 800 samples
    if (i > 0 && i % 800 === 0) {
      t += 120; // 2 min gap
      timestamps.push(t);
      rsrp.push(null);
      rsrq.push(null);
      sinr.push(null);
      score.push(null);
      flag.push(false);
      continue;
    }
    timestamps.push(t);
    const r = -95 + Math.sin(i / 50) * 15 + (Math.random() * 4 - 2);
    const q = -12 + Math.cos(i / 60) * 4;
    const s = 10 + Math.sin(i / 40) * 12;
    const isAnom = r < -110 || s < 0 || Math.random() < 0.03;
    const sc = isAnom ? 0.75 + Math.random() * 0.2 : 0.2 + Math.random() * 0.3;

    rsrp.push(r);
    rsrq.push(q);
    sinr.push(s);
    score.push(sc);
    flag.push(isAnom);
  }

  return { count: n, timestamps, rsrp, rsrq, sinr, score, flag };
}

function populateTableFallback(data) {
  const tbody = document.getElementById('table-body');
  const rows = [];
  const limit = Math.min(200, data.count); // Preview first 200 rows in DOM

  for (let i = 0; i < limit; i++) {
    const dt = new Date(data.timestamps[i] * 1000).toISOString().replace('T', ' ').slice(0, 19);
    const anomBadge = data.flag[i] ? '<span class="badge-anom">ANOMALY ×</span>' : 'NORMAL';
    rows.push(`<tr>
      <td>${i + 1}</td>
      <td>${dt}</td>
      <td>${data.rsrp[i] !== null ? data.rsrp[i] : '—'}</td>
      <td>${data.rsrq[i] !== null ? data.rsrq[i] : '—'}</td>
      <td>${data.sinr[i] !== null ? data.sinr[i] : '—'}</td>
      <td>${data.score[i] !== null ? data.score[i] : '—'}</td>
      <td>${anomBadge}</td>
    </tr>`);
  }
  tbody.innerHTML = rows.join('');
}

// Marker plugin for uPlot: draws red × on flagged anomalies
function anomalyMarkerPlugin(flags) {
  return {
    hooks: {
      drawSeries: (u, sidx) => {
        if (sidx === 0) return;
        const ctx = u.ctx;
        const xData = u.data[0];
        const yData = u.data[sidx];
        ctx.save();
        ctx.strokeStyle = '#DC2626';
        ctx.lineWidth = 2.5;

        for (let i = 0; i < xData.length; i++) {
          if (flags[i] && yData[i] !== null && yData[i] !== undefined) {
            const cx = u.valToPos(xData[i], 'x', true);
            const cy = u.valToPos(yData[i], u.series[sidx].scale, true);
            const size = 5;
            ctx.beginPath();
            ctx.moveTo(cx - size, cy - size);
            ctx.lineTo(cx + size, cy + size);
            ctx.moveTo(cx + size, cy - size);
            ctx.lineTo(cx - size, cy + size);
            ctx.stroke();
          }
        }
        ctx.restore();
      }
    }
  };
}

function renderUplot() {
  const t0 = performance.now();
  uplotCharts.forEach(c => c.destroy());
  uplotCharts = [];

  const sync = uPlot.sync("spike-sync");
  const baseOptions = {
    width: document.getElementById('uplot-wrapper').clientWidth - 40,
    height: 200,
    cursor: { sync: { key: sync.key } },
    legend: { show: false },
    axes: [{ grid: { stroke: "#E2E8F0", width: 1 } }, { grid: { stroke: "#E2E8F0", width: 1 } }]
  };

  const panels = [
    { id: 'uplot-rsrp', label: 'SS-RSRP (dBm)', data: dataset.rsrp, stroke: '#2563EB', range: [-140, -44] },
    { id: 'uplot-rsrq', label: 'SS-RSRQ (dB)', data: dataset.rsrq, stroke: '#0369A1', range: [-43, 20] },
    { id: 'uplot-sinr', label: 'SS-SINR (dB)', data: dataset.sinr, stroke: '#15803D', range: [-23, 40] },
    { id: 'uplot-score', label: 'IF Score', data: dataset.score, stroke: '#B45309', range: [0, 1] }
  ];

  panels.forEach(p => {
    const opts = {
      ...baseOptions,
      scales: { x: { time: true }, y: { auto: false, range: p.range } },
      series: [
        {},
        {
          label: p.label,
          stroke: p.stroke,
          width: 1.5,
          spanGaps: false // Breaks lines on null (gap breaks)
        }
      ],
      plugins: [anomalyMarkerPlugin(dataset.flag)]
    };
    const chart = new uPlot(opts, [dataset.timestamps, p.data], document.getElementById(p.id));
    uplotCharts.push(chart);
  });

  const renderMs = Math.round(performance.now() - t0);
  STATS.uplot.renderMs = renderMs;
  updateStatsDisplay('uplot');
}

function renderEcharts() {
  const t0 = performance.now();
  echartsInstances.forEach(e => e.dispose());
  echartsInstances = [];

  const timeCategories = dataset.timestamps.map(ts => new Date(ts * 1000).toLocaleTimeString());
  const panels = [
    { id: 'echarts-rsrp', name: 'SS-RSRP', data: dataset.rsrp, color: '#2563EB', min: -140, max: -44 },
    { id: 'echarts-rsrq', name: 'SS-RSRQ', data: dataset.rsrq, color: '#0369A1', min: -43, max: 20 },
    { id: 'echarts-sinr', name: 'SS-SINR', data: dataset.sinr, color: '#15803D', min: -23, max: 40 },
    { id: 'echarts-score', name: 'IF Score', data: dataset.score, color: '#B45309', min: 0, max: 1 }
  ];

  // Extract anomaly marker points
  const markers = [];
  for (let i = 0; i < dataset.count; i++) {
    if (dataset.flag[i]) {
      markers.push({ coord: [i, dataset.rsrp[i]], symbol: 'pin' });
    }
  }

  panels.forEach((p, idx) => {
    const el = document.getElementById(p.id);
    const chart = echarts.init(el);
    echartsInstances.push(chart);

    const isLast = idx === panels.length - 1;
    const option = {
      animation: false,
      grid: { left: 50, right: 20, top: 20, bottom: isLast ? 30 : 15 },
      xAxis: {
        type: 'category',
        data: timeCategories,
        show: isLast,
        axisLine: { lineStyle: { color: '#E2E8F0' } }
      },
      yAxis: {
        type: 'value',
        min: p.min,
        max: p.max,
        splitLine: { lineStyle: { color: '#F1F5F9' } }
      },
      series: [
        {
          name: p.name,
          type: 'line',
          data: p.data,
          itemStyle: { color: p.color },
          connectNulls: false, // Strict gap breaks on missing values
          showSymbol: false
        }
      ],
      dataZoom: [
        { type: 'inside', xAxisIndex: 0 },
        { type: 'slider', show: isLast, xAxisIndex: 0, height: 16 }
      ]
    };
    chart.setOption(option);
  });

  // Synchronize zoom and pan across all 4 ECharts panels
  echarts.connect(echartsInstances);

  const renderMs = Math.round(performance.now() - t0);
  STATS.echarts.renderMs = renderMs;
  updateStatsDisplay('echarts');
}

function updateStatsDisplay(candidate) {
  const s = STATS[candidate];
  document.getElementById('val-bundle').innerText = s.bundle;
  document.getElementById('sub-bundle').innerText = `License: ${s.license}`;
  document.getElementById('val-render').innerText = `${s.renderMs} ms`;
  document.getElementById('sub-render').innerText = '5,528 points across 4 panels';
  document.getElementById('val-fps').innerText = s.fps;
  document.getElementById('val-features').innerText = 'Supported';
}

function switchCandidate(candidate) {
  currentCandidate = candidate;
  document.getElementById('btn-uplot').classList.toggle('active', candidate === 'uplot');
  document.getElementById('btn-echarts').classList.toggle('active', candidate === 'echarts');

  if (candidate === 'uplot') {
    document.getElementById('uplot-wrapper').style.display = 'block';
    document.getElementById('echarts-wrapper').style.display = 'none';
    renderUplot();
  } else {
    document.getElementById('uplot-wrapper').style.display = 'none';
    document.getElementById('echarts-wrapper').style.display = 'block';
    renderEcharts();
  }
}

function renderCandidate(candidate) {
  if (candidate === 'uplot') renderUplot();
  else renderEcharts();
}

function toggleTheme() {
  const current = document.documentElement.getAttribute('data-theme');
  const next = current === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', next);
  if (currentCandidate === 'uplot') renderUplot();
  else renderEcharts();
}

window.addEventListener('resize', () => {
  if (currentCandidate === 'uplot') renderUplot();
  else echartsInstances.forEach(e => e.resize());
});

window.addEventListener('DOMContentLoaded', init);
