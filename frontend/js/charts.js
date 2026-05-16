/* ── HEMS Chart Library v3.0 ── */

const C = {
  import:   '#f87171', export:  '#34d399', solar:  '#fbbf24',
  charge:   '#818cf8', discharge:'#fb923c',load:   '#e8eaf6',
  soc:      '#4f8ef7', tariff:  '#a78bfa', shadow: '#34d399',
  shed:     'rgba(248,113,113,0.08)', peak: 'rgba(251,191,36,0.06)',
  paper:    '#1a1d27', grid:    '#2e3354', font:   '#9ba4c7'
};

const BASE = {
  paper_bgcolor: C.paper, plot_bgcolor: 'rgba(0,0,0,0)',
  font: { family: 'Inter,sans-serif', color: C.font, size: 12 },
  xaxis: { gridcolor: C.grid, zerolinecolor: C.grid },
  yaxis: { gridcolor: C.grid, zerolinecolor: C.grid },
  legend: { bgcolor: 'rgba(0,0,0,0)', font: { size: 11 } },
  margin: { l: 55, r: 20, t: 28, b: 50 }
};

const CFG = { responsive: true, displaylogo: false,
  modeBarButtonsToRemove: ['lasso2d','select2d'] };

const HRS = Array.from({length:24},(_,i)=>`${String(i).padStart(2,'0')}:00`);

/* Build peak + shedding shape annotations */
function buildShapes(G) {
  const shapes = [];
  // Peak hours
  [18,19,20,21].forEach(h => shapes.push({
    type:'rect', xref:'x', yref:'paper', x0:HRS[h], x1:HRS[(h+1)%24],
    y0:0, y1:1, fillcolor:C.peak, line:{width:0}
  }));
  // Load shedding hours
  if (G) G.forEach((g, h) => {
    if (g === 0) shapes.push({
      type:'rect', xref:'x', yref:'paper', x0:HRS[h], x1:HRS[(h+1)%24],
      y0:0, y1:1, fillcolor:C.shed, line:{width:1, color:'rgba(248,113,113,0.3)', dash:'dot'}
    });
  });
  return shapes;
}

/* ── Schedule Chart ── */
function renderSchedule(data) {
  const o = data.optimal || data;
  if (!o.p_grid_plus) return;
  const G = o.G || Array(24).fill(1);

  Plotly.newPlot('c-schedule', [
    { x:HRS, y:o.p_load, name:'Fixed Load', type:'scatter', mode:'lines',
      fill:'tozeroy', fillcolor:'rgba(232,234,246,0.07)',
      line:{color:C.load, width:2} },
    { x:HRS, y:o.p_pv,   name:'Solar PV',   type:'scatter', mode:'lines',
      fill:'tozeroy', fillcolor:'rgba(251,191,36,0.12)',
      line:{color:C.solar, width:2} },
    { x:HRS, y:o.p_grid_plus,  name:'Grid Import', type:'bar',
      marker:{color:C.import, opacity:.8} },
    { x:HRS, y:o.p_grid_minus.map(v=>-v), name:'Grid Export', type:'bar',
      marker:{color:C.export, opacity:.8} },
    { x:HRS, y:o.p_charge,     name:'Batt Charge',    type:'bar',
      marker:{color:C.charge, opacity:.8} },
    { x:HRS, y:o.p_discharge.map(v=>-v), name:'Batt Discharge', type:'bar',
      marker:{color:C.discharge, opacity:.8} }
  ], {
    ...BASE, barmode:'overlay',
    xaxis:{...BASE.xaxis, title:'Hour', tickangle:-45},
    yaxis:{...BASE.yaxis, title:'Power (kW)'},
    shapes: buildShapes(G),
    annotations:[
      {xref:'paper',yref:'paper',x:.98,y:.98,text:'🔴 Peak  ⚫ Load-Shed',
       showarrow:false,font:{size:10,color:C.font}}
    ]
  }, CFG);
}

/* ── SOC Chart ── */
function renderSOC(data) {
  const o = data.optimal || data;
  const p = data.params  || {};
  if (!o.soc) return;

  const H25 = Array.from({length:25},(_,i)=>`${String(i%24).padStart(2,'0')}:00`);
  const Em  = p.E_max || 13.5;
  const En  = p.E_min || 2.7;

  // SOC reserve levels
  const reserve = p.soc_reserve_hours || {};
  const res_y   = Array(25).fill(null);
  Object.entries(reserve).forEach(([h,v]) => { if(+h<25) res_y[+h] = v; });

  const traces = [
    { x:H25, y:o.soc, name:'SOC (kWh)', type:'scatter', mode:'lines+markers',
      fill:'tozeroy', fillcolor:'rgba(79,142,247,0.1)',
      line:{color:C.soc, width:2.5}, marker:{size:5} },
    { x:H25, y:Array(25).fill(Em), name:`E_max=${Em}kWh`, type:'scatter', mode:'lines',
      line:{color:C.import, width:1.5, dash:'dash'} },
    { x:H25, y:Array(25).fill(En.toFixed?En.toFixed(1):En), name:`E_min=${typeof En==='number'?En.toFixed(1):En}kWh`,
      type:'scatter', mode:'lines', line:{color:C.solar, width:1.5, dash:'dash'} }
  ];

  if (res_y.some(v=>v!==null)) {
    traces.push({ x:H25, y:res_y, name:'Load-Shed Reserve', type:'scatter',
      mode:'markers', marker:{color:C.import, size:10, symbol:'diamond'} });
  }

  Plotly.newPlot('c-soc', traces, {
    ...BASE,
    xaxis:{...BASE.xaxis, title:'Hour', tickangle:-45},
    yaxis:{...BASE.yaxis, title:'SOC (kWh)', range:[0, Em*1.1]}
  }, CFG);
}

/* ── Cost Comparison ── */
function renderCosts(data) {
  if (!data.baselines || !data.optimal) return;
  const all   = [data.optimal, ...data.baselines];
  const names = ['Optimal (CVXPY)', ...data.baselines.map(b=>b.name)];

  Plotly.newPlot('c-costs', [
    { x:names, y:all.map(r=>r.import_cost_pkr||0),          name:'Grid Import',       type:'bar', marker:{color:C.import} },
    { x:names, y:all.map(r=>-(r.export_revenue_pkr||0)),     name:'Export Revenue (-)', type:'bar', marker:{color:C.export} },
    { x:names, y:all.map(r=>r.degradation_cost_pkr||0),      name:'Degradation',       type:'bar', marker:{color:C.charge} },
    { x:names, y:all.map(r=>r.demand_charge_pkr||0),         name:'Demand Charge',     type:'bar', marker:{color:C.solar} },
    { x:names, y:all.map(r=>r.capacity_tax_pkr||0),          name:'Capacity Tax',      type:'bar', marker:{color:C.tariff} }
  ], {
    ...BASE, barmode:'stack',
    xaxis:{...BASE.xaxis},
    yaxis:{...BASE.yaxis, title:'Cost (PKR/day)'}
  }, CFG);
}

/* ── Shadow Prices ── */
function renderDuals(data) {
  const d = data.dual_analysis || {};
  const o = data.optimal || data;
  const prices = d.energy_shadow_prices || Array(24).fill(0);
  const tariff  = o.tariff || Array(24).fill(0);

  Plotly.newPlot('c-duals', [
    { x:HRS, y:tariff, name:'TOU Tariff', type:'scatter', mode:'lines',
      line:{color:C.tariff, width:2.5} },
    { x:HRS, y:prices, name:'Shadow Price μ_t', type:'scatter', mode:'lines+markers',
      line:{color:C.shadow, width:2}, marker:{size:5} }
  ], {
    ...BASE,
    xaxis:{...BASE.xaxis, title:'Hour'},
    yaxis:{...BASE.yaxis, title:'PKR/kWh'}
  }, CFG);

  // Insights
  const iw = document.getElementById('insights-wrap');
  const ins = d.economic_insights || [];
  const kkt = d.kkt_interpretation || {};
  iw.innerHTML = `
    <h4 style="font-size:13px;margin-bottom:10px;color:var(--accent)">
      🔍 Economic Insights</h4>
    ${ins.map(i=>`
      <div class="insight">
        <div class="idot ${i.includes('⚠️')?'warn':i.includes('✓')?'ok':''}"></div>
        <span>${i}</span>
      </div>`).join('')}
    <h4 style="font-size:13px;margin:14px 0 10px;color:var(--purple)">
      📐 KKT Variable Meanings</h4>
    ${Object.entries(kkt).map(([k,v])=>`
      <div class="insight">
        <div class="idot" style="background:var(--purple)"></div>
        <span><b>${k}:</b> ${v}</span>
      </div>`).join('')}`;
}

/* ── Load Shedding Chart ── */
function renderLoadShed(data) {
  const o = data.optimal || data;
  const G = o.G || Array(24).fill(1);
  const soc = o.soc || Array(25).fill(0);
  const p_gp = o.p_grid_plus || Array(24).fill(0);

  Plotly.newPlot('c-loadshed', [
    { x:HRS, y:G, name:'Grid Availability G_t', type:'bar',
      marker:{color:G.map(g=>g?'rgba(52,211,153,0.7)':'rgba(248,113,113,0.7)')} },
    { x:HRS, y:p_gp, name:'Grid Import (kW)', type:'scatter', mode:'lines',
      yaxis:'y2', line:{color:C.import, width:2} }
  ], {
    ...BASE,
    xaxis:{...BASE.xaxis, title:'Hour', tickangle:-45},
    yaxis:{...BASE.yaxis, title:'G_t (1=available, 0=shed)', range:[-0.1,1.5]},
    yaxis2:{title:'Grid Import (kW)', overlaying:'y', side:'right',
      gridcolor:C.grid, color:C.import}
  }, CFG);

  // Info card
  const shed_hrs = G.map((g,i)=>g===0?i:null).filter(v=>v!==null);
  const li = document.getElementById('ls-info');
  li.innerHTML = `
    <h4 style="font-size:13px;margin-bottom:10px;">⚡ Load Shedding Summary</h4>
    <div class="insight"><div class="idot warn"></div>
      <span>Shedding hours: ${shed_hrs.length>0?shed_hrs.map(h=>HRS[h]).join(', '):'None scheduled'}</span></div>
    <div class="insight"><div class="idot"></div>
      <span>Battery must maintain ${(0.4*((data.params||{}).E_max||13.5)).toFixed(1)} kWh reserve before shedding periods.</span></div>
    <div class="insight"><div class="idot ok"></div>
      <span>Energy balance constraint modified: G_t × p⁺_t and G_t × p⁻_t. Grid terms → 0 during outage.</span></div>`;
}

/* ── Policy Comparison Chart ── */
function renderPolicy(bdata) {
  const modes  = Object.keys(bdata);
  const costs  = modes.map(m => bdata[m].cost || 0);
  const exprevs= modes.map(m => bdata[m].export_revenue || 0);
  const captax = modes.map(m => bdata[m].capacity_tax || 0);
  const labels = {
    net_metering:  'Net Metering\n(PKR 19.32/kWh)',
    gross_metering:'Gross Metering\n(PKR 10.00/kWh)',
    capacity_tax:  'Capacity Tax\n(PKR 2000/kW/mo)'
  };

  Plotly.newPlot('c-policy', [
    { x:modes.map(m=>labels[m]||m), y:costs,   name:'Total Cost', type:'bar',
      marker:{color:[C.green, C.solar, C.import]} },
    { x:modes.map(m=>labels[m]||m), y:captax,  name:'Capacity Tax', type:'bar',
      marker:{color:C.tariff, opacity:.7} }
  ], {
    ...BASE, barmode:'group',
    xaxis:{...BASE.xaxis},
    yaxis:{...BASE.yaxis, title:'Cost (PKR/day)'}
  }, CFG);

  const pd = document.getElementById('policy-details');
  pd.innerHTML = `
    <h4 style="font-size:13px;margin-bottom:10px;">🏛️ Policy Analysis</h4>
    <div class="insight"><div class="idot ok"></div>
      <span><b>Net Metering</b> (current): Export at PKR 19.32/kWh. Best for households with excess solar.</span></div>
    <div class="insight"><div class="idot warn"></div>
      <span><b>Gross Metering</b> (proposed): Export drops to PKR 10.00/kWh. Reduces solar ROI by ~48%.</span></div>
    <div class="insight"><div class="idot warn"></div>
      <span><b>Capacity Tax</b> (IMF push): Fixed PKR 2000/kW/month regardless of generation. Heaviest burden for large PV systems.</span></div>
    <div class="insight"><div class="idot"></div>
      <span>This dashboard serves as a <b>policy analysis tool</b> — adjust PV capacity and compare modes to evaluate investment decisions.</span></div>`;
}

/* ── Experiments ── */
function renderExperiments(exp) {
  if (exp.exp1_robustness) {
    const d = exp.exp1_robustness.filter(r=>r.feasible);
    Plotly.newPlot('c-pareto',[{
      x:d.map(r=>r.rho), y:d.map(r=>r.cost),
      type:'scatter', mode:'lines+markers',
      line:{color:C.soc,width:2}, marker:{size:8,color:C.import}
    }],{...BASE, xaxis:{...BASE.xaxis,title:'ρ (kW)'},
      yaxis:{...BASE.yaxis,title:'Cost (PKR/day)'}},CFG);
  }
  if (exp.exp2_battery) {
    const d = exp.exp2_battery.filter(r=>r.feasible);
    Plotly.newPlot('c-batt',[{
      x:d.map(r=>r.E_max), y:d.map(r=>r.cost),
      type:'scatter', mode:'lines+markers', fill:'tozeroy',
      fillcolor:'rgba(79,142,247,0.08)', line:{color:C.soc,width:2}
    }],{...BASE, xaxis:{...BASE.xaxis,title:'Battery (kWh)'},
      yaxis:{...BASE.yaxis,title:'Cost (PKR/day)'}},CFG);
  }
  if (exp.exp3_solar) {
    const d = exp.exp3_solar.filter(r=>r.feasible);
    Plotly.newPlot('c-solar',[{
      x:d.map(r=>r.PV_rated), y:d.map(r=>r.cost),
      type:'bar', marker:{color:C.solar,opacity:.85}
    }],{...BASE, xaxis:{...BASE.xaxis,title:'Solar (kW)'},
      yaxis:{...BASE.yaxis,title:'Cost (PKR/day)'}},CFG);
  }
  if (exp.exp6_degradation) {
    const d = exp.exp6_degradation.filter(r=>r.feasible);
    Plotly.newPlot('c-degrad',[
      { x:d.map(r=>r.lambda), y:d.map(r=>r.cost),
        name:'Cost', type:'scatter', mode:'lines+markers',
        line:{color:C.import,width:2} },
      { x:d.map(r=>r.lambda), y:d.map(r=>r.cycling_kwh),
        name:'Cycling kWh', type:'scatter', mode:'lines+markers',
        yaxis:'y2', line:{color:C.charge,width:2} }
    ],{...BASE, xaxis:{...BASE.xaxis,title:'λ (PKR/kWh)'},
      yaxis:{...BASE.yaxis,title:'Cost'}, yaxis2:{
        title:'Cycling kWh',overlaying:'y',side:'right',
        gridcolor:C.grid,color:C.charge}},CFG);
  }
}

/* ── Gantt ── */
function renderGantt(data) {
  const o = data.optimal || data;
  if (!o.schedules) return;
  const colors = ['#4f8ef7','#34d399','#fbbf24','#a78bfa'];
  const names  = Object.keys(o.schedules);
  Plotly.newPlot('c-gantt',
    names.map((n,i)=>({
      x:HRS, y:o.schedules[n],
      name:n.replace(/_/g,' ').replace(/\b\w/g,l=>l.toUpperCase()),
      type:'bar', marker:{color:colors[i%colors.length],opacity:.85}
    })),
    { ...BASE, barmode:'stack',
      xaxis:{...BASE.xaxis,title:'Hour',tickangle:-45},
      yaxis:{...BASE.yaxis,title:'Schedule [0,1]',range:[0,1.5]} },
    CFG);
}

/* ── Savings Table ── */
function renderSavings(savings) {
  if (!savings?.length) return;
  const wrap = document.getElementById('savings-wrap');
  wrap.innerHTML = `
    <h4 style="font-size:13px;margin-bottom:10px;">💰 Financial Delta Engine — Daily Savings (PKR)</h4>
    <table>
      <thead><tr>
        <th>Baseline</th><th>Baseline Cost</th><th>Optimal Cost</th>
        <th>Daily Saving</th><th>%</th><th>Monthly Saving</th>
      </tr></thead>
      <tbody>${savings.map(s=>`
        <tr>
          <td>${s.baseline}</td>
          <td>PKR ${s.baseline_cost?.toFixed(0)||'—'}</td>
          <td>PKR ${s.optimal_cost?.toFixed(0)||'—'}</td>
          <td class="${(s.savings_pkr||0)>=0?'pos':'neg'}">PKR ${(s.savings_pkr||0).toFixed(0)}</td>
          <td class="${(s.savings_pct||0)>=0?'pos':'neg'}">${(s.savings_pct||0).toFixed(1)}%</td>
          <td class="${(s.monthly_pkr||0)>=0?'pos':'neg'}">PKR ${(s.monthly_pkr||0).toFixed(0)}</td>
        </tr>`).join('')}
      </tbody>
    </table>`;
}