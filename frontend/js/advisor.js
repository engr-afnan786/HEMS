/* ── HEMS Solar Investment Advisor v5.0 ── */
/* NEW FILE: frontend/js/advisor.js          */

const ADVISOR = {

  async getRecommendations() {
    const body = {
      monthly_units: +document.getElementById('adv-units').value,
      budget:        +document.getElementById('adv-budget').value,
      has_loadshedding: document.getElementById('adv-loadshed').checked,
      wants_battery: (() => {
        const v = document.getElementById('adv-battery').value;
        return v === 'auto' ? null : v === 'yes';
      })(),
      location: document.getElementById('adv-location').value
    };

    const r = await fetch(`${API.BASE}/advisor/recommend`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
    if (!r.ok) throw new Error(`API ${r.status}`);
    return r.json();
  },

  renderResults(data) {
    const wrap = document.getElementById('advisor-results');
    if (!data.recommendations || data.recommendations.length === 0) {
      wrap.innerHTML = `<div class="adv-empty">
        <div style="font-size:40px;margin-bottom:12px">😕</div>
        <h3>No systems fit your budget</h3>
        <p>Try increasing budget or reducing load requirements.</p>
      </div>`;
      return;
    }

    const inp = data.input;

    // Summary card
    let html = `
    <div class="adv-summary">
      <div class="adv-stat">
        <span class="adv-sl">Monthly Bill</span>
        <span class="adv-sv">PKR ${inp.current_bill_pkr.toLocaleString()}</span>
      </div>
      <div class="adv-stat">
        <span class="adv-sl">Annual Cost</span>
        <span class="adv-sv" style="color:var(--red)">PKR ${inp.annual_bill_pkr.toLocaleString()}</span>
      </div>
      <div class="adv-stat">
        <span class="adv-sl">Ideal System</span>
        <span class="adv-sv">${inp.ideal_system_kw} kW</span>
      </div>
      <div class="adv-stat">
        <span class="adv-sl">Options Found</span>
        <span class="adv-sv">${data.total_options}</span>
      </div>
    </div>

    <div class="adv-cards">`;

    for (const rec of data.recommendations) {
      const c = rec.costs;
      const f = rec.financials;
      const isTop = rec.tag.includes('Best') || rec.tag.includes('Fastest');
      const typeColors = {ongrid:'var(--green)', hybrid:'var(--accent)', offgrid:'var(--orange)'};
      const typeLabels = {ongrid:'On-Grid + Net Metering', hybrid:'Hybrid (Grid + Battery)', offgrid:'Off-Grid (Standalone)'};

      html += `
      <div class="adv-card ${isTop ? 'adv-card-top' : ''}" onclick="ADVISOR.selectConfig(${JSON.stringify(rec).replace(/"/g, '&quot;')})">
        <div class="adv-tag">${rec.tag}</div>
        <div class="adv-type" style="color:${typeColors[rec.system_type]}">
          ${typeLabels[rec.system_type] || rec.system_type}</div>

        <div class="adv-size">${rec.system_kw} kW System</div>

        <div class="adv-equip">
          <div class="adv-eq-item">
            <span class="adv-eq-icon">☀️</span>
            <div>
              <b>${rec.num_panels}× ${rec.panel.brand} ${rec.panel.watt}W</b>
              <small>${rec.panel.type} · ${rec.panel.efficiency}% eff · ${rec.panel.warranty}yr warranty</small>
            </div>
          </div>
          <div class="adv-eq-item">
            <span class="adv-eq-icon">⚡</span>
            <div>
              <b>${rec.inverter.brand} ${rec.inverter.model}</b>
              <small>${rec.inverter.type} · ${rec.inverter.kw}kW · ${rec.inverter.warranty}yr</small>
            </div>
          </div>
          ${rec.battery ? `
          <div class="adv-eq-item">
            <span class="adv-eq-icon">🔋</span>
            <div>
              <b>${rec.battery.brand} ${rec.battery.model}</b>
              <small>${rec.battery.kwh}kWh ${rec.battery.type} · ${rec.battery.cycles} cycles · ${rec.battery.warranty}yr</small>
            </div>
          </div>` : `
          <div class="adv-eq-item" style="opacity:0.4">
            <span class="adv-eq-icon">🔋</span>
            <div><b>No Battery</b><small>Grid provides backup</small></div>
          </div>`}
        </div>

        <div class="adv-costs">
          <div class="adv-cost-row"><span>Panels</span><span>PKR ${c.panels.toLocaleString()}</span></div>
          <div class="adv-cost-row"><span>Inverter</span><span>PKR ${c.inverter.toLocaleString()}</span></div>
          ${c.battery > 0 ? `<div class="adv-cost-row"><span>Battery</span><span>PKR ${c.battery.toLocaleString()}</span></div>` : ''}
          <div class="adv-cost-row"><span>Installation</span><span>PKR ${c.installation.toLocaleString()}</span></div>
          ${c.net_metering > 0 ? `<div class="adv-cost-row"><span>Net Metering</span><span>PKR ${c.net_metering.toLocaleString()}</span></div>` : ''}
          <div class="adv-cost-total"><span>Total Investment</span><span>PKR ${c.total.toLocaleString()}</span></div>
        </div>

        <div class="adv-returns">
          <div class="adv-ret">
            <div class="adv-ret-val" style="color:var(--green)">PKR ${f.monthly_savings.toLocaleString()}</div>
            <div class="adv-ret-lbl">Monthly Savings</div>
          </div>
          <div class="adv-ret">
            <div class="adv-ret-val" style="color:var(--accent)">${f.payback_years} yr</div>
            <div class="adv-ret-lbl">Payback Period</div>
          </div>
          <div class="adv-ret">
            <div class="adv-ret-val" style="color:var(--purple)">${f.roi_10yr_pct}%</div>
            <div class="adv-ret-lbl">10-Year ROI</div>
          </div>
        </div>

        <div class="adv-lifetime">
          25-Year Net Profit: <b style="color:var(--green)">PKR ${(f.lifetime_savings_25yr/1000000).toFixed(1)}M</b>
        </div>

        <button class="btn btn-primary adv-select-btn" style="width:100%;margin-top:10px">
          Select & Run Optimizer →
        </button>
      </div>`;
    }

    html += `</div>`;
    wrap.innerHTML = html;

    // Render payback comparison chart
    this.renderPaybackChart(data.recommendations);
  },

  renderPaybackChart(recs) {
    const el = document.getElementById('adv-chart');
    if (!el) return;
    const labels = recs.map(r => `${r.system_kw}kW ${r.system_type}`);
    const paybacks = recs.map(r => r.financials.payback_years);
    const rois = recs.map(r => r.financials.roi_10yr_pct);
    const colors = recs.map(r =>
      r.system_type === 'ongrid' ? '#34d399' :
      r.system_type === 'hybrid' ? '#4f8ef7' : '#fb923c'
    );

    Plotly.newPlot(el, [
      { x: labels, y: paybacks, name: 'Payback (years)', type: 'bar',
        marker: { color: colors, opacity: 0.85 } },
      { x: labels, y: rois, name: '10-Year ROI %', type: 'scatter',
        mode: 'lines+markers', yaxis: 'y2',
        line: { color: '#a78bfa', width: 2.5 }, marker: { size: 8 } }
    ], {
      ...BASE, barmode: 'group',
      xaxis: { ...BASE.xaxis, tickangle: -30 },
      yaxis: { ...BASE.yaxis, title: 'Payback (years)' },
      yaxis2: { title: 'ROI %', overlaying: 'y', side: 'right',
                gridcolor: '#2e3354', color: '#a78bfa' }
    }, CFG);
  },

  selectConfig(rec) {
    // Auto-fill the optimizer sidebar with selected system params
    document.getElementById('battery_size').value = rec.battery ? rec.battery.kwh : 0;
    document.getElementById('solar_capacity').value = rec.system_kw;
    lbl('batt-lbl', rec.battery ? rec.battery.kwh : 0);
    lbl('solar-lbl', rec.system_kw);

    if (rec.net_metering) {
      document.getElementById('billing_mode').value = 'net_metering';
    }

    // Switch to optimizer tab
    document.querySelectorAll('.tab').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
    document.querySelector('.tab[onclick*="schedule"]').classList.add('active');
    document.getElementById('p-schedule').classList.add('active');

    showAlert(`✅ System loaded: ${rec.system_kw}kW ${rec.system_type} with ${rec.panel.brand}. Click "Optimize Now" to see daily schedule.`);

    // Auto-run optimization
    setTimeout(runAll, 500);
  }
};


async function runAdvisor() {
  setLoading(true, 'Analyzing best solar options for you…');
  try {
    const data = await ADVISOR.getRecommendations();
    ADVISOR.renderResults(data);

    // Switch to advisor tab
    document.querySelectorAll('.tab').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
    document.querySelector('.tab[onclick*="advisor"]').classList.add('active');
    document.getElementById('p-advisor').classList.add('active');
  } catch (err) {
    showAlert('❌ Advisor error: ' + err.message);
  } finally {
    setLoading(false);
  }
}
