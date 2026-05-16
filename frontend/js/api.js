/* ── HEMS API Client v3.0 ── */
const API = {
  BASE: 'http://localhost:5000/api',

  async post(ep, body) {
    const r = await fetch(`${API.BASE}${ep}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
    if (!r.ok) throw new Error(`API ${r.status}: ${await r.text()}`);
    return r.json();
  },

  async get(ep) {
    const r = await fetch(`${API.BASE}${ep}`);
    if (!r.ok) throw new Error(`API ${r.status}`);
    return r.json();
  },

  params() {
    return {
      season:           document.getElementById('season').value,
      battery_size:     +document.getElementById('battery_size').value,
      solar_capacity:   +document.getElementById('solar_capacity').value,
      rho:              +document.getElementById('rho').value,
      billing_mode:     document.getElementById('billing_mode').value,
      use_ev:           document.getElementById('use_ev').checked,
      use_gst:          document.getElementById('use_gst').checked,
      use_fca:          document.getElementById('use_fca').checked,
      use_loadshedding: document.getElementById('use_loadshedding').checked
    };
  },

  compare()     { return this.post('/compare', this.params()); },
  billing()     { return this.post('/billing-comparison', this.params()); },
  experiments() { return this.get('/experiments'); }
};