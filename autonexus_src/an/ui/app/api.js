/* AutoNexus app shell — API client for /api/v1 */
const motionBundle = document.createElement("script");
motionBundle.src = "/app/motion.bundle.js";
motionBundle.defer = true;
document.head.appendChild(motionBundle);

const AN = {
  tokenKey: "autonexusOwnerToken",
  get token() { return sessionStorage.getItem(this.tokenKey) || ""; },
  set token(v) { if (v) sessionStorage.setItem(this.tokenKey, v); else sessionStorage.removeItem(this.tokenKey); },

  async login(email, password) {
    const r = await fetch("/api/v1/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    const j = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(AN.errorMessage(j, r, "Login failed"));
    const t = j.token || j.access_token;
    if (!t) throw new Error("No token in response");
    this.token = t;
    return j;
  },

  async api(path, opts = {}) {
    const headers = Object.assign({}, opts.headers || {});
    if (this.token) headers.Authorization = "Bearer " + this.token;
    if (opts.body && !headers["Content-Type"]) headers["Content-Type"] = "application/json";
    const r = await fetch("/api/v1" + path, Object.assign({}, opts, { headers }));
    const j = await r.json().catch(() => ({}));
    if (r.status === 401) this.token = "";
    if (!r.ok) throw new Error(AN.errorMessage(j, r));
    return j;
  },

  errorMessage(body, response, fallback = "Request failed") {
    const detail = body && body.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) return detail.map(x => [x.loc && x.loc.join("."), x.msg].filter(Boolean).join(": ")).join("; ");
    return (body && body.message) || (response && response.statusText) || fallback;
  },

  // Convenience
  overview: () => AN.api("/overview"),
  inventory: (part) => AN.api("/inventory/" + encodeURIComponent(part)),
  forecast: (dealer, part, horizon = 14) =>
    AN.api(`/forecast?dealer=${encodeURIComponent(dealer)}&part=${encodeURIComponent(part)}&horizon_days=${horizon}`),
  forecastXgb: (dealer, part, horizon = 14) => {
    let q = `horizon_days=${horizon}`;
    if (dealer) q += `&dealer=${encodeURIComponent(dealer)}`;
    if (part) q += `&part=${encodeURIComponent(part)}`;
    return AN.api("/forecast/xgboost?" + q);
  },
  workshop: (dealer, part) =>
    AN.api(`/workshop/evaluate?dealer=${encodeURIComponent(dealer)}&part=${encodeURIComponent(part)}`),
  twin: (part) => AN.api("/twin/state?part=" + encodeURIComponent(part)),
  vehicles: () => AN.api("/vehicles"),
  approvals: (status) => AN.api("/approvals" + (status ? "?status=" + encodeURIComponent(status) : "")),
  decide: (id, decision, note = "") =>
    AN.api(`/approvals/${encodeURIComponent(id)}/decision`, {
      method: "POST",
      body: JSON.stringify({ decision, note }),
    }),
  startShortage: (dealer, part, qty) =>
    AN.api("/workflows/shortage", {
      method: "POST",
      body: JSON.stringify({ dealer, part, required_qty: qty }),
    }),
  suppliers: (part, qty = 10) =>
    AN.api(`/suppliers/rank?part=${encodeURIComponent(part)}&qty=${qty}`),
  route: (src, dst) =>
    AN.api(`/route?src=${encodeURIComponent(src)}&dst=${encodeURIComponent(dst)}`),
};

function navActive() {
  const path = location.pathname.replace(/\/+$/, "") || "/app";
  document.querySelectorAll(".nav a").forEach((a) => {
    const href = a.getAttribute("href").replace(/\/+$/, "");
    a.classList.toggle("active", href === path || (path === "/app" && href === "/app/"));
  });
}

function authBar(rootId = "auth") {
  const el = document.getElementById(rootId);
  if (!el) return;
  el.innerHTML = `
    <input id="auth-email" type="email" placeholder="Configured owner email" autocomplete="username"/>
    <input id="auth-pass" type="password" placeholder="password"/>
    <button class="btn primary" id="auth-login">Sign in</button>
    <button class="btn" id="auth-out">Sign out</button>
    <span class="muted mono" id="auth-status">${AN.token ? "Signed in" : "Not signed in — some actions need login"}</span>
  `;
  el.querySelector("#auth-login").onclick = async () => {
    try {
      await AN.login(el.querySelector("#auth-email").value, el.querySelector("#auth-pass").value);
      el.querySelector("#auth-status").textContent = "Signed in";
      el.querySelector("#auth-status").className = "okmsg mono";
      if (window.onAuth) window.onAuth();
    } catch (e) {
      el.querySelector("#auth-status").textContent = e.message;
      el.querySelector("#auth-status").className = "err mono";
    }
  };
  el.querySelector("#auth-out").onclick = () => {
    AN.token = "";
    el.querySelector("#auth-status").textContent = "Signed out";
    el.querySelector("#auth-status").className = "muted mono";
  };
}

function sideNav() {
  return `
  <aside class="side">
    <div class="brand">
      <div class="brand-mark">AN</div>
      <div><strong>AUTONEXUS</strong><span>Kolkata operations</span></div>
    </div>
    <nav class="nav">
      <div class="group">Today</div>
      <a href="/app/">Situation board</a>
      <a href="/app/approvals.html">Waiting for your OK</a>
      <div class="group">Stock &amp; buying</div>
      <a href="/app/stock.html">Stock management</a>
      <a href="/app/buying.html">Buying parts</a>
      <a href="/app/forecast.html">Predict demand</a>
      <div class="group">Service</div>
      <a href="/app/workshop.html">Workshop schedule</a>
      <a href="/app/vehicles.html">Cars waiting to sell</a>
      <div class="group">Live</div>
      <a href="/world" target="_blank">Live operations map ↗</a>
      <a href="/docs" target="_blank">API docs ↗</a>
    </nav>
  </aside>`;
}
