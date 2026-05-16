/* ── HEMS Main Controller v3.0 ── */

let state = { data: null, billingData: null, expData: null };

/* ── Utilities ── */
function lbl(id, val) {
  document.getElementById(id).textContent = parseFloat(val).toFixed(1);
}

function setLoading(on, msg='Running CVXPY Solver…') {
  const el  = document.getElementById('loading');
  const sub = document.getElementById('loading-sub');
  const bdg = document.getElementById('status-badge');
  if (on) {
    el.classList.add('active');
    el.querySelector('p').textContent = msg;
    bdg.textContent = 'Solving…';
    bdg.style.cssText = 'background:rgba(251,146,60,.15);color:var(--orange)';
  } else {
    el.classList.remove('active');
    bdg.textContent = 'Ready';
    bdg.style.cssText = 'background:rgba(52,211,153,.15);color:var(--green)';
  }
}

function showAlert(msg) {
  const el = document.getElementById('alert-banner');
  el.textContent = msg;
  el.style.display = 'block';
  setTimeout(() => el.style.display = 'none', 6000);
}

function tab(btn, name) {
  document.querySelectorAll('.tab').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  btn.classList.add('active');
  document.getElementById(`p-${name}`).classList.add('active');
  if (state.data) renderActiveTab(name);
}

function renderActiveTab(name) {
  const d = state.data;
  if (!d) return;
  if (name === 'schedule')    renderSchedule(d);
  if (name === 'soc')         renderSOC(d);
  if (name === 'costs')       { renderCosts(d); renderSavings(d.savings_analysis); }
  if (name === 'duals')       renderDuals(d);
  if (name === 'loadshed')    renderLoadShed(d);
  if (name === 'gantt')       renderGantt(d);
  if (name === 'policy' && state.billingData) renderPolicy(state.billingData);
  if (name === 'experiments' && state.expData) renderExperiments(state.expData);
}

/* ── Update KPIs ── */
function updateKPIs(data) {
  const o  = data.optimal || data;
  const sv = data.savings_analysis || [];
  const bg = sv.find(s => s.baseline?.includes('Grid')) || {};

  document.getElementById('k-cost').textContent  = `PKR ${(o.total_cost_pkr||0).toFixed(0)}`;
  document.getElementById('k-save').textContent  = `PKR ${(bg.savings_pkr||0).toFixed(0)}`;
  document.getElementById('k-exp').textContent   = `PKR ${(o.export_revenue_pkr||0).toFixed(2)}`;
  document.getElementById('k-peak').textContent  = `${(o.P_peak||0).toFixed(2)} kW`;
  document.getElementById('k-pct').textContent   = `${(bg.savings_pct||0).toFixed(1)}%`;
  document.getElementById('k-month').textContent = `PKR ${((o.total_cost_pkr||0)*30).toFixed(0)}`;
}

/* ── Update Tariff Display ── */
function updateTariffDisplay(params) {
  if (!params?.tariff) return;
  const peak   = Math.max(...params.tariff);
  const offpeak= Math.min(...params.tariff);
  const cexp   = params.c_export;
  document.getElementById('t-peak').textContent    = `PKR ${peak.toFixed(2)}`;
  document.getElementById('t-offpeak').textContent = `PKR ${offpeak.toFixed(2)}`;
  document.getElementById('t-export').textContent  = `PKR ${cexp?.toFixed(2)||'—'}`;
}

/* ── Solver Info Bar ── */
function updateSolverBar(data) {
  const o  = data.optimal || data;
  const bar = document.getElementById('solver-bar');
  bar.style.display = 'flex';

  const solver = o.solver || '—';
  const isFallback = o.fallback || solver.includes('GREEDY');
  document.getElementById('solver-info').innerHTML =
    `<span style="color:${isFallback?'var(--orange)':'var(--green)'}">
      ${isFallback?'⚠️ FALLBACK':'✓ Solver'}: ${solver}</span>`;

  const G = o.G || Array(24).fill(1);
  const shedH = G.map((g,i)=>g===0?i:null).filter(v=>v!==null);
  document.getElementById('shedding-info').innerHTML =
    shedH.length
      ? `<span style="color:var(--orange)">⚡ Shedding: ${shedH.length}h</span>`
      : `<span style="color:var(--green)">✓ No shedding</span>`;

  document.getElementById('billing-info').innerHTML =
    `<span style="color:var(--accent)">🏛️ ${(o.billing_mode||'').replace(/_/g,' ')}</span>`;

  const cd = o.simultaneous_cd_kwh || 0;
  document.getElementById('sim-cd-warn').innerHTML =
    cd > 0.01
      ? `<span style="color:var(--red)">⚠️ C/D overlap: ${cd.toFixed(3)}kWh — increase λ</span>`
      : `<span style="color:var(--green)">✓ No C/D overlap</span>`;
}

/* ── EV toggle ── */
document.getElementById('use_ev').addEventListener('change', e => {
  document.getElementById('ev-item').style.opacity = e.target.checked ? '1' : '0.4';
});

/* ── Billing mode note ── */
document.getElementById('billing_mode').addEventListener('change', e => {
  const notes = {
    net_metering:  'Current AEDB policy. IMF may push to gross metering.',
    gross_metering:'⚠️ Proposed policy: export revenue drops ~48%.',
    capacity_tax:  '⚠️ IMF-proposed: fixed PKR 2000/kW/month regardless of generation.'
  };
  document.getElementById('policy-note').textContent = notes[e.target.value] || '';
});

/* ── Main: Run All ── */
async function runAll() {
  setLoading(true, 'Running Convex Optimization…');
  try {
    const data = await API.compare();
    state.data = data;

    if (data.optimal?.fallback) {
      showAlert('⚠️ All convex solvers failed. Greedy fallback active. '
                + 'Check constraints feasibility (e.g., battery too small for load-shed reserve).');
    }

    updateKPIs(data);
    updateSolverBar(data);
    updateTariffDisplay(data.params);

    // Render active tab
    const active = document.querySelector('.tab.active');
    const tabName = active?.getAttribute('onclick')?.match(/tab\(this,'(\w+)'\)/)?.[1] || 'schedule';
    renderActiveTab(tabName);

  } catch (err) {
    showAlert('❌ Error: ' + err.message + ' — Is the Flask server running on port 5000?');
  } finally {
    setLoading(false);
  }
}

/* ── Billing Policy Comparison ── */
async function runBilling() {
  setLoading(true, 'Comparing Billing Policies…');
  try {
    const bdata = await API.billing();
    state.billingData = bdata;

    // Switch to policy tab
    document.querySelectorAll('.tab').forEach((b,i) => b.classList.toggle('active', i===5));
    document.querySelectorAll('.panel').forEach((p,i) => p.classList.toggle('active', i===5));
    renderPolicy(bdata);
  } catch (err) {
    showAlert('❌ Policy comparison failed: ' + err.message);
  } finally {
    setLoading(false);
  }
}

/* ── Experiments ── */
async function runExperiments() {
  setLoading(true, 'Running 6 Parameter Sweep Experiments…');
  try {
    const exp = await API.experiments();
    state.expData = exp;

    document.querySelectorAll('.tab').forEach((b,i) => b.classList.toggle('active', i===6));
    document.querySelectorAll('.panel').forEach((p,i) => p.classList.toggle('active', i===6));
    renderExperiments(exp);
  } catch (err) {
    showAlert('❌ Experiments failed: ' + err.message);
  } finally {
    setLoading(false);
  }
}

/* ── Auto-run on load ── */
window.addEventListener('load', () => {
  setTimeout(runAll, 300);
});