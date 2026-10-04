"use strict";
(() => {
  /* ================= utilities ================= */
  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => [...el.querySelectorAll(s)];
  const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const ROLES = ["A", "B", "C"];
  const P = {
    grid: '<rect x="3" y="3" width="7" height="9" rx="1.5"/><rect x="14" y="3" width="7" height="5" rx="1.5"/><rect x="14" y="12" width="7" height="9" rx="1.5"/><rect x="3" y="16" width="7" height="5" rx="1.5"/>',
    plus: '<path d="M12 5v14M5 12h14"/>',
    folder: '<path d="M4 20h16a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.7-.9l-.8-1.2A2 2 0 0 0 7.9 3H4a2 2 0 0 0-2 2v13c0 1.1.9 2 2 2Z"/>',
    settings: '<path d="M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3M1 14h6M9 8h6M17 16h6"/>',
    shield: '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="m9 12 2 2 4-4"/>',
    check: '<path d="M20 6 9 17l-5-5"/>',
    x: '<path d="M18 6 6 18M6 6l12 12"/>',
    alert: '<path d="m21.7 18-8-14a2 2 0 0 0-3.5 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.7-3Z"/><path d="M12 9v4M12 17h.01"/>',
    clock: '<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>',
    play: '<path d="m6 3 14 9-14 9V3z"/>',
    file: '<path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/><path d="M14 2v6h6M16 13H8M16 17H8M10 9H8"/>',
    book: '<path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20V2H6.5A2.5 2.5 0 0 0 4 4.5v15z"/><path d="M6.5 17A2.5 2.5 0 0 0 4 19.5 2.5 2.5 0 0 0 6.5 22H20v-5"/>',
    user: '<path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
    users: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.9M16 3.1a4 4 0 0 1 0 7.8"/>',
    activity: '<path d="M22 12h-4l-3 9L9 3l-3 9H2"/>',
    layers: '<path d="m12 2 10 5-10 5L2 7l10-5z"/><path d="m2 17 10 5 10-5M2 12l10 5 10-5"/>',
    refresh: '<path d="M21 12a9 9 0 1 1-3-6.7L21 8"/><path d="M21 3v5h-5"/>',
    download: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3"/>',
    printer: '<path d="M6 9V2h12v7M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><rect x="6" y="14" width="12" height="8"/>',
    upload: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M17 8l-5-5-5 5M12 3v12"/>',
    trash: '<path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>',
    git: '<circle cx="18" cy="18" r="3"/><circle cx="6" cy="6" r="3"/><path d="M13 6h3a2 2 0 0 1 2 2v7M11 18H8a2 2 0 0 1-2-2V9"/>',
    cpu: '<rect x="4" y="4" width="16" height="16" rx="2"/><rect x="9" y="9" width="6" height="6"/><path d="M9 1v3M15 1v3M9 20v3M15 20v3M20 9h3M20 14h3M1 9h3M1 14h3"/>',
    zap: '<path d="M13 2 3 14h9l-1 8 10-12h-9l1-8z"/>',
    info: '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/>',
    chevron: '<path d="m9 18 6-6-6-6"/>',
    arrowLeft: '<path d="M19 12H5M12 19l-7-7 7-7"/>',
    flask: '<path d="M9 3h6M10 3v7.4L4.6 19a1.5 1.5 0 0 0 1.3 2.2h12.2a1.5 1.5 0 0 0 1.3-2.2L14 10.4V3"/><path d="M7 15h10"/>',
    pen: '<path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z"/>',
    lock: '<rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>',
    steth: '<path d="M4.8 2.3A.3.3 0 1 0 5 2H4a2 2 0 0 0-2 2v5a6 6 0 0 0 12 0V4a2 2 0 0 0-2-2h-1a.2.2 0 1 0 .3.3"/><path d="M8 15v1a6 6 0 0 0 12 0v-4"/><circle cx="20" cy="10" r="2"/>',
    search: '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
    code: '<path d="m16 18 6-6-6-6M8 6l-6 6 6 6"/>',
    database: '<ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5v14c0 1.7 4 3 9 3s9-1.3 9-3V5"/><path d="M3 12c0 1.7 4 3 9 3s9-1.3 9-3"/>',
    message: '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>',
    sparkles: '<path d="M12 3l1.9 5.8L20 10l-6.1 1.2L12 17l-1.9-5.8L4 10l6.1-1.2Z"/><path d="M19 17v4M17 19h4"/>',
    target: '<circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/>',
    link: '<path d="M10 13a5 5 0 0 0 7.5.5l3-3a5 5 0 0 0-7-7l-1.7 1.7"/><path d="M14 11a5 5 0 0 0-7.5-.5l-3 3a5 5 0 0 0 7 7l1.7-1.7"/>',
  };
  const icon = (n, cls = "ic") => `<svg class="${cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${P[n] || ""}</svg>`;

  const ROLE = {
    A: { name: "Anticoagulation benefit & duration", short: "Anticoagulation" },
    B: { name: "Drug eligibility & safety", short: "Medication safety" },
    C: { name: "Bleeding risk & patient constraints", short: "Bleeding risk" },
    D: { name: "Synthesis & targeted revision", short: "Coordinator" },
  };
  const STATUS = {
    approved: { t: "Approved", c: "ok" }, needs_human_review: { t: "Needs human review", c: "warn" },
    failed: { t: "Failed", c: "bad" }, running: { t: "Running", c: "run" }, interrupted: { t: "Interrupted", c: "gray" },
  };
  const TASK = { assess: "Assessment", synthesize: "Synthesize", review: "Review", revise: "Targeted revision" };
  const TASK_SHORT = { assess: "Assess", synthesize: "Synthesis", review: "Review", revise: "Revise" };
  const VERDICT = { approve: { t: "Approved", c: "ok" }, revise: { t: "Revise", c: "warn" }, needs_information: { t: "Missing information", c: "bad" } };
  const DECISION = { accept: { t: "Accept", c: "ok", i: "check" }, accept_with_changes: { t: "Accept with changes", c: "warn", i: "pen" }, reject: { t: "Reject", c: "bad", i: "x" } };
  const QUICK = ["Age", "Sex", "Weight", "VTE type & site", "Diagnosis date", "Serum creatinine", "eGFR / CrCl", "Platelets", "Liver function", "Bleeding history", "Concomitant medication", "Pregnancy / lactation", "Active cancer", "Planned surgery"];

  const S = { info: null, run: null, runTab: "report", evMap: {}, w: null, hist: { q: "", f: "all" }, runs: [], signDecision: "" };
  let apiKey = "";
  let cleanup = [];
  let routeVersion = 0;
  let drawerFocus = null;

  async function api(path, opts = {}) {
    const init = { method: opts.method || (opts.body ? "POST" : "GET"), headers: {} };
    if (opts.body) { init.headers["Content-Type"] = "application/json"; init.body = JSON.stringify(opts.body); }
    const res = await fetch(path, init);
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
    return data;
  }
  const fmtTime = (iso) => { if (!iso) return "—"; const d = new Date(iso); return isNaN(d) ? iso : d.toLocaleString("en-US", { hour12: false, year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" }); };
  const fmtSec = (s) => (s == null ? "—" : s < 60 ? `${Number(s).toFixed(1)} s` : `${Math.floor(s / 60)} m ${Math.round(s % 60)} s`);
  const badge = (t, c, extra = "") => `<span class="badge ${c} ${extra}">${esc(t)}</span>`;
  const statusBadge = (s) => { const x = STATUS[s] || { t: s || "Unknown", c: "gray" }; return badge(x.t, x.c); };
  const roleTag = (r, size) => `<span class="role-tag ${r}"${size ? ` style="width:${size}px;height:${size}px;font-size:${Math.round(size * .48)}px;border-radius:${Math.round(size / 3.4)}px"` : ""}>${r}</span>`;
  const crumb = (...xs) => [`<span>VTE Review</span>`, ...xs.map((x, i) => (i === xs.length - 1 ? `<b>${esc(x)}</b>` : `<span>${esc(x)}</span>`))].join(`<span class="sep">/</span>`);
  const fmtVal = (v) => (typeof v === "boolean" ? (v ? "Yes" : "No") : typeof v === "string" ? v : JSON.stringify(v));
  function reasonText(r) {
    if (!r) return "";
    const map = {
      all_required_reviews_passed: "All specialists approved the current draft",
      missing_information: "Additional patient data or evidence is required",
      revision_limit: "Revision limit reached with unresolved issues",
      no_change_after_revision: "No changes were made; the review loop stopped",
      source_verification_required: "Confirm source readings, dates and conflicting records before review",
      clinical_data_requires_review: "Draft available; dependent decisions need additional clinical data",
    };
    if (map[r]) return map[r];
    if (r.startsWith("no_retrieved_evidence:")) return `No matching evidence for: ${r.split(":")[1]}`;
    return `Run error: ${r}`;
  }
  function toast(msg, type = "info") {
    const el = document.createElement("div");
    el.className = `toast ${type}`;
    el.innerHTML = icon(type === "ok" ? "check" : type === "bad" ? "alert" : "info") + `<span>${esc(msg)}</span>`;
    $("#toasts").append(el);
    setTimeout(() => { el.style.transition = ".3s"; el.style.opacity = "0"; setTimeout(() => el.remove(), 300); }, 3800);
  }
  function setView(html, crumbs) {
    const v = $("#view");
    v.innerHTML = html;
    // Link visible field labels for keyboard and assistive technology users.
    $$(".field", v).forEach((field, n) => {
      const label = $("label", field), input = $("input,textarea,select", field);
      if (label && input) { input.id ||= `field-${n}`; label.htmlFor = input.id; }
    });
    if (crumbs !== undefined) $("#crumbs").innerHTML = crumbs;
  }
  const loading = () => `<div class="empty"><div class="spinner" style="margin:0 auto 10px;width:22px;height:22px"></div>Loading…</div>`;
  function jsonHTML(v) {
    const s = esc(JSON.stringify(v, null, 2));
    return s.replace(/(&quot;(?:[^&\\]|\\.|&(?!quot;))*?&quot;)(\s*:)?|\b(true|false|null)\b|-?\b\d+(?:\.\d+)?(?:[eE][+-]?\d+)?\b/g,
      (m, str, colon, b) => (str ? (colon ? `<span class="k">${str}</span>${colon}` : `<span class="s">${str}</span>`) : b ? `<span class="b">${m}</span>` : `<span class="n">${m}</span>`));
  }

  /* ================= diff ================= */
  const tok = (s) => String(s || "").match(/[A-Za-z0-9_.%\-]+|\s+|[\s\S]/gu) || [];
  function diffHTML(a, b) {
    const A = tok(a), B = tok(b), n = A.length, m = B.length;
    if (n * m > 2.5e6) return `<del>${esc(a)}</del><ins>${esc(b)}</ins>`;
    const dp = Array.from({ length: n + 1 }, () => new Uint32Array(m + 1));
    for (let i = n - 1; i >= 0; i--) for (let j = m - 1; j >= 0; j--) dp[i][j] = A[i] === B[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
    const out = []; let i = 0, j = 0;
    const push = (t, s) => { const last = out[out.length - 1]; if (last && last[0] === t) last[1] += s; else out.push([t, s]); };
    while (i < n && j < m) {
      if (A[i] === B[j]) { push("=", A[i]); i++; j++; } else if (dp[i + 1][j] >= dp[i][j + 1]) { push("-", A[i++]); } else { push("+", B[j++]); }
    }
    while (i < n) push("-", A[i++]);
    while (j < m) push("+", B[j++]);
    return out.map(([t, s]) => (t === "=" ? esc(s) : t === "+" ? `<ins>${esc(s)}</ins>` : `<del>${esc(s)}</del>`)).join("");
  }

  /* ================= event derivation ================= */
  function derive(events) {
    const st = { agents: {}, calls: [], drafts: [], rounds: [], phases: [], approvals: { A: null, B: null, C: null }, finished: null, started: null, now: 0, version: 0 };
    for (const r of [...ROLES, "D"]) st.agents[r] = { state: "idle", label: "Waiting", note: "" };
    const open = {};
    const phase = (label, sub = "") => { const last = st.phases[st.phases.length - 1]; if (last && last.state === "active") last.state = "done"; st.phases.push({ label, sub, state: "active" }); };
    for (const e of events) {
      st.now = Math.max(st.now, e.elapsed_s || 0);
      if (e.event === "started") { st.started = e; phase("Retrieval"); }
      else if (e.event === "call_started") {
        const c = { task: e.task, role: e.role, version: e.version, start: e.elapsed_s, end: null, status: "running" };
        st.calls.push(c); open[`${e.task}|${e.role}`] = c;
        st.agents[e.role] = { state: "working", label: `${TASK[e.task] || e.task}${e.task === "review" ? ` v${e.version}` : ""}…`, note: "" };
        const last = st.phases[st.phases.length - 1];
        if (e.task === "assess" && (!last || last.label !== "Parallel assessment")) phase("Parallel assessment", "A · B · C");
        if (e.task === "synthesize") phase("D synthesizes");
        if (e.task === "revise") phase("D revises");
      } else if (e.event === "call_completed" || e.event === "call_failed") {
        const c = open[`${e.task}|${e.role}`] || {};
        c.end = e.elapsed_s; c.status = e.event === "call_failed" ? "failed" : "done";
        c.output = e.output; c.duration = e.duration_s; c.usage = e.usage; c.model = e.model; c.error = e.error;
        const a = st.agents[e.role];
        if (e.event === "call_failed") { Object.assign(a, { state: "bad", label: "Call failed", note: e.error || "" }); const last = st.phases[st.phases.length - 1]; if (last) last.state = "fail"; }
        else if (e.task === "assess") Object.assign(a, { state: "ok", label: "Assessment complete", note: e.output?.summary || "" });
        else if (e.task === "review") {
          const v = e.output?.verdict;
          const n = e.output?.issues?.length || 0;
          st.approvals[e.role] = v === "approve" ? e.version : null;
          Object.assign(a, { state: v === "approve" ? "ok" : v === "revise" ? "warn" : "bad", label: v === "approve" ? `v${e.version} Approved` : v === "revise" ? `v${e.version} Revise · ${n} issues` : `Missing information · ${n} issues`, note: e.output?.note || "" });
        } else Object.assign(a, { state: "ok", label: e.task === "revise" ? "Revision complete" : "Draft created", note: e.output?.reason || "" });
      } else if (e.event === "draft_created") {
        st.version = e.version; st.drafts.push({ version: e.version, draft: e.draft, reason: "", roles: [...ROLES], initial: true });
        st.agents.D = { state: "ok", label: `Draft created v${e.version}`, note: "" };
      } else if (e.event === "draft_revised") {
        st.version = e.version; st.drafts.push({ version: e.version, draft: e.draft, reason: e.reason, roles: e.roles || [] });
        for (const r of e.roles || []) st.approvals[r] = null;
        st.agents.D = { state: "ok", label: `Revised to v${e.version}`, note: e.reason || "" };
      } else if (e.event === "review_round") {
        st.rounds.push({ version: e.version, roles: e.roles });
        phase(`Specialist review v${e.version}`, (e.roles || []).join(" · "));
        for (const r of ROLES) if (!(e.roles || []).includes(r) && st.approvals[r] != null) st.agents[r] = { state: "ok", label: `Still approved (v${st.approvals[r]} unchanged since then)`, note: "No review needed this round" };
      } else if (e.event === "finished") {
        st.finished = e;
        const last = st.phases[st.phases.length - 1];
        if (last && last.state === "active") last.state = e.status === "failed" ? "fail" : "done";
        st.phases.push({ label: e.status === "approved" ? "Approved" : e.status === "failed" ? "Failed" : "Human review", sub: "", state: e.status === "approved" ? "done" : e.status === "failed" ? "fail" : "stop" });
        if (st.agents.D.state === "idle" || st.agents.D.state === "working") st.agents.D = { state: e.status === "failed" ? "bad" : "ok", label: STATUS[e.status]?.t || e.status, note: "" };
      }
    }
    if (!st.finished) {
      if (!st.rounds.length) st.phases.push({ label: "Specialist review", sub: "", state: "pending" });
      st.phases.push({ label: "Result", sub: "", state: "pending" });
    }
    return st;
  }

  /* ================= drawer ================= */
  function openDrawer(html) {
    if (!$("#drawer").classList.contains("on")) drawerFocus = document.activeElement;
    const drawer = $("#drawer"); drawer.innerHTML = html; drawer.inert = false;
    $$(".field", drawer).forEach((field,n)=>{const label=$("label",field),input=$("input,textarea,select",field);if(label&&input){input.id ||= `drawer-field-${n}`;label.htmlFor=input.id;}});
    drawer.classList.add("on"); $("#drawer-mask").classList.add("on"); drawer.setAttribute("aria-hidden", "false");
    $(".app").inert = true;
    $("button", drawer)?.focus();
  }
  function closeDrawer() {
    const drawer = $("#drawer");
    if (!drawer.classList.contains("on")) return;
    $(".app").inert = false;
    if (drawerFocus?.isConnected) drawerFocus.focus();
    drawer.classList.remove("on"); $("#drawer-mask").classList.remove("on"); drawer.setAttribute("aria-hidden", "true"); drawer.inert = true;
  }

  function openEvidence(id) {
    const doc = S.evMap[id];
    if (!doc) return toast("Evidence not found", "bad");
    openDrawer(`<div class="dh"><div class="stat-ic" style="background:var(--brand-soft);color:var(--brand)">${icon("book")}</div>
      <div style="flex:1;min-width:0"><div class="muted small mono">${esc(doc.id)}</div><h3 style="margin:2px 0 0;font-size:16px">${esc(doc.title)}</h3></div>
      <button class="btn ghost sm" data-action="close-drawer" title="Close">${icon("x")}</button></div>
      <div class="db stack">
        ${doc.synthetic ? `<div class="notice warn">${icon("flask")}<div>Synthetic test material, not clinical evidence.</div></div>` : ""}
        <dl class="facts"><dt>Source</dt><dd>${esc(doc.source)}</dd><dt>Version</dt><dd>${esc(doc.version)}</dd>
        <dt>Roles</dt><dd>${(doc.roles || []).map((r) => roleTag(r, 20)).join(" ")}</dd><dt>Material type</dt><dd>${doc.synthetic ? "Synthetic test material" : "Source material (declared by uploader)"}</dd></dl>
        <div><div class="muted small" style="margin-bottom:6px">Source passage</div><div class="quote">${esc(doc.text)}</div></div>
      </div>`);
  }

  /* ================= dashboard ================= */
  function runRows(runs) {
    if (!runs.length) return `<tr><td colspan="6"><div class="empty">${icon("folder")}<div>No matching reviews</div></div></td></tr>`;
    return runs.map((r) => `<tr class="click" tabindex="0" role="link" aria-label="Open case ${esc(r.case_id || r.id)}" data-action="open-run" data-id="${esc(r.id)}">
      <td><div style="font-weight:600">${esc(r.case_id || "—")}</div><div class="muted small trunc">${esc(r.question || "")}</div></td>
      <td>${statusBadge(r.status)}</td>
      <td>${r.mode === "llm" ? `<span class="chip">${icon("cpu")}${esc(r.model || "LLM")}</span>` : `<span class="chip">${icon("flask")}Demo${r.scenario ? " · " + esc(S.info?.scenarios?.[r.scenario]?.title || r.scenario) : ""}</span>`}</td>
      <td>${r.version != null ? `v${r.version} · Revisions ${r.revisions ?? 0}` : "—"}</td>
      <td>${r.signoff ? badge(DECISION[r.signoff.decision]?.t || r.signoff.decision, DECISION[r.signoff.decision]?.c || "gray") + `<div class="muted small">${esc(r.signoff.reviewer)}</div>` : r.status === "approved" || r.status === "needs_human_review" ? badge("Awaiting sign-off", "gray") : "—"}</td>
      <td class="muted small" style="white-space:nowrap">${fmtTime(r.created_at)}</td></tr>`).join("");
  }
  const runTable = (runs, id = "") => `<div class="table-wrap"><table class="table"><thead><tr><th>Case / Question</th><th>Status</th><th>Mode</th><th>Version</th><th>Physician review</th><th>Date</th></tr></thead><tbody ${id ? `id="${id}"` : ""}>${runRows(runs)}</tbody></table></div>`;

  async function viewDashboard() {
    const route = routeVersion;
    setView(loading(), crumb("Overview"));
    try {
      const [data, library] = await Promise.all([api("/api/runs"), api("/api/knowledge")]);
      if (route !== routeVersion) return;
      const runs = data.runs, stats = library.stats;
      const n = (status) => runs.filter((r) => r.status === status).length;
      const metric = (value, label, ic) => `<div class="metric-card"><div class="metric-top">${label}${icon(ic)}</div><div class="metric-value">${value}</div></div>`;
      const recent = runs.length ? runTable(runs.slice(0, 5)) : `<div class="recent-empty"><div class="empty-file">${icon("file")}</div><b>No reviews yet</b><a href="#/new" class="btn sm" style="margin-top:14px">${icon("plus")}New review</a></div>`;
      setView(`<div class="dashboard-stack"><div class="dashboard-head"><h1>Overview</h1><div class="row wrap"><button class="btn" data-action="quick-demo" data-s="targeted">${icon("play")}Run demo</button><a class="btn primary" href="#/new">${icon("plus")}New review</a></div></div>
      <section class="agent-team"><div class="team-heading"><h2>Review team</h2><span>3 specialists · 1 coordinator</span></div><div class="robot-grid">${[...ROLES,"D"].map((r) => `<button class="robot-card ${r}" data-action="agent-profile" data-r="${r}" aria-label="View Agent ${r}: ${ROLE[r].short}"><span class="robot-id">AGENT ${r}</span><img src="/static/agent-${r.toLowerCase()}.svg" alt="Agent ${r} robot wearing a white coat"><strong>${ROLE[r].short}</strong><span class="robot-description">${({A:"Benefit & duration",B:"Eligibility & dosing",C:"Bleeding & constraints",D:"Synthesis & revision"})[r]}</span><span class="robot-details">View role ${icon("chevron")}</span></button>`).join("")}</div><div class="team-process"><span>${icon("users")}Parallel assessment</span>${icon("chevron")}<span>${icon("layers")}Coordinated draft</span>${icon("chevron")}<span>${icon("refresh")}Targeted review</span></div></section>
      <div class="dashboard-stats">${metric(runs.length,"Total reviews","folder")}${metric(n("approved"),"Agent-approved","shield")}${metric(n("needs_human_review"),"Needs human review","alert")}${metric(stats.documents,"Knowledge documents","book")}</div>
      <div class="dashboard-bottom"><section class="card recent-card"><div class="card-h"><h3>Recent reviews</h3><a href="#/history" class="btn ghost sm">View all${icon("chevron")}</a></div>${recent}</section><section class="card library-summary"><div class="card-h"><h3>Knowledge base</h3>${icon("database")}</div><div class="card-b"><div class="library-numbers"><b>${stats.documents}<small>documents</small></b><b>${stats.chunks}<small>passages</small></b></div><div class="library-status">${icon("check")}Full-text search ready</div><a class="btn primary" href="#/knowledge" style="width:100%;margin-top:22px">${icon("book")}Open library</a></div></section></div></div>`);
    } catch (e) {
      if (route !== routeVersion) return;
      setView(`<div class="empty">${icon("alert")}<p>Unable to load the workspace.</p><button class="btn" data-action="reload">Try again</button></div>`); toast(e.message,"bad");
    }
  }

  /* ================= history ================= */
  async function viewHistory() {
    const route = routeVersion;
    setView(loading(), crumb("Reviews"));
    try { S.runs = (await api("/api/runs")).runs; } catch (e) { toast(e.message, "bad"); S.runs = []; }
    if (route !== routeVersion) return;
    const filters = [["all", "All"], ["approved", "Approved"], ["needs_human_review", "Needs human review"], ["failed", "Failed"], ["running", "Running"], ["unsigned", "Awaiting sign-off"]];
    setView(`<div class="page-h"><div><h1 class="h1">Reviews</h1><p class="lead">Records stored in <span class="mono">${esc(S.info?.runs_dir || "runs/")}</span></p></div>
      <a class="btn primary" href="#/new">${icon("plus")}New review</a></div>
      <div class="card"><div class="card-h history-tools"><div class="seg">${filters.map(([k, t]) => `<button data-action="hist-f" data-f="${k}" class="${S.hist.f === k ? "on" : ""}">${t}</button>`).join("")}</div>
      <div class="row" style="width:300px;position:relative"><input class="input" data-input="hist-q" placeholder="Search case ID, question or run ID" value="${esc(S.hist.q)}"></div></div>
      ${runTable(filterRuns(), "hist-body")}</div>`, crumb("Reviews"));
  }
  function filterRuns() {
    const q = S.hist.q.trim().toLowerCase();
    return S.runs.filter((r) => {
      if (S.hist.f === "unsigned") { if (!(r.status === "approved" || r.status === "needs_human_review") || r.signoff) return false; }
      else if (S.hist.f !== "all" && r.status !== S.hist.f) return false;
      return !q || [r.id, r.case_id, r.question].some((x) => String(x || "").toLowerCase().includes(q));
    });
  }

  /* ================= new review wizard ================= */
  const W_KEY = "vte.wizard.v1";
  const blankCase = () => ({ case_id: "", question: "", facts: [["", ""]], missing: [] });
  const defaultWizard = () => ({ step: 0, caseMode: "form", case: blankCase(), evidence: null, evidenceName: "", evidenceCheck: null, mode: "demo", scenario: "targeted", useDemoData: true, pace: 0.8, settings: null, llm: { base_url: "", model: "", role_models: {} } });
  function loadWizard() { try { const w = JSON.parse(localStorage.getItem(W_KEY)); if (w && w.case) return Object.assign(defaultWizard(), w); } catch { /* ignore */ } return defaultWizard(); }
  function saveWizard() { try { localStorage.setItem(W_KEY, JSON.stringify(S.w)); } catch { /* quota exceeded: keep in memory */ } }
  function caseFromJSON(o) {
    if (!o || typeof o !== "object" || Array.isArray(o) || typeof o.case_id !== "string" || typeof o.question !== "string" || !o.facts || typeof o.facts !== "object" || Array.isArray(o.facts) || !Array.isArray(o.missing_information) || o.missing_information.some((v) => typeof v !== "string")) throw new Error("Expected case_id, question, a facts object and a missing_information string array");
    const facts = Object.entries(o.facts || {}).map(([k, v]) => [k, typeof v === "string" ? v : JSON.stringify(v)]);
    const extra = Object.fromEntries(["patient","task_type","candidate_plan","observations","source_ids","source_context"].filter(k=>k in o).map(k=>[k,o[k]]));
    return { case_id: String(o.case_id || ""), question: String(o.question || ""), facts: facts.length ? facts : [["", ""]], missing: [...new Set((o.missing_information || []).map(String))], extra };
  }
  function parseVal(v) {
    const t = String(v).trim();
    if (/^-?\d+(\.\d+)?$/.test(t)) return Number(t);
    if (t === "true" || t === "false") return t === "true";
    if (/^[[{]/.test(t)) { try { return JSON.parse(t); } catch { /* keep string */ } }
    return t;
  }
  function buildCase() {
    const c = S.w.case, facts = {};
    for (const [k, v] of c.facts) if (String(k).trim() && String(v).trim()) facts[String(k).trim()] = parseVal(v);
    return { ...(c.extra || {}), case_id: c.case_id.trim(), question: c.question.trim(), facts, missing_information: c.missing.filter((x) => x.trim()) };
  }
  function caseChecks() {
    const c = buildCase(), out = [];
    if (S.w.jsonError) out.push(["bad", "Fix the case JSON before starting"]);
    out.push(c.case_id ? ["ok", `Case ID: ${c.case_id}`] : ["bad", "Enter a de-identified case ID"]);
    out.push(c.question ? ["ok", "Decision question provided"] : ["bad", "Enter a decision question"]);
    const n = Object.keys(c.facts).length;
    const sourced = (c.observations||[]).filter(o=>o.status==='confirmed').length;
    out.push(n || sourced ? ["ok", `Facts entered: ${n} · Confirmed source readings: ${sourced}`] : ["bad", "Enter a verified patient fact or confirm a sourced observation"]);
    const keys = S.w.case.facts.map(([k]) => String(k).trim()).filter(Boolean);
    if (new Set(keys).size !== keys.length) out.push(["bad", "Merge duplicate fields before starting"]);
    out.push(c.missing_information.length ? ["warn", `Missing fields: ${c.missing_information.length} (included in the review)`] : ["info", "No missing information listed"]);
    return out;
  }
  const checkList = (items) => `<div class="check-list">${items.map(([s, t]) => `<div class="check-item ${s}">${icon(s === "ok" ? "check" : s === "bad" ? "x" : s === "warn" ? "alert" : "info")}<span>${esc(t)}</span></div>`).join("")}</div>`;
  function defaultsToSettings() { const d = S.info?.defaults || { max_revisions: 3, max_concurrency: 3, call_timeout: 60, top_k: 4 }; return { max_revisions: d.max_revisions, concurrency: d.max_concurrency, timeout: d.call_timeout, top_k: d.top_k }; }

  async function viewNew() { S.w = S.w || loadWizard(); if (!S.w.settings) S.w.settings = defaultsToSettings(); S.evMap = Object.fromEntries((S.w.evidence || []).map((d) => [d.id, d])); await hydrateCaseSources(); if(location.hash.startsWith("#/new"))renderWizard(); }
  async function hydrateCaseSources(){const c=S.w.case;const ids=c.extra?.source_ids||[];const records=await Promise.all(ids.map(async id=>{try{return await api(`/api/sources/${encodeURIComponent(id)}`);}catch{return {id,name:id+" (source unavailable)",mime:"text/plain",images:[]};}}));if(c===S.w.case)S.w.sources=records;}
  function renderWizard() {
    const w = S.w;
    const steps = [["Case details", "De-identified patient facts"], ["Evidence", "Select sources"], ["Run setup", "Demo or model"]];
    const body = [stepCase, stepEvidence, stepRun][w.step]();
    setView(`<div class="page-h"><div><h1 class="h1">New review</h1><p class="lead">Case, evidence and run configuration.</p></div>
      <button class="btn ghost" data-action="w-reset">${icon("refresh")}Reset</button></div>
      <div class="steps">${steps.map(([t, s], i) => `<button class="step ${i === w.step ? "on" : ""} ${i < w.step ? "done" : ""}" data-action="w-step" data-i="${i}"><span class="n">${i < w.step ? icon("check") : i + 1}</span><span><b>${t}</b><span class="s">${s}</span></span></button>`).join("")}</div>
      ${body}
      <div class="row" style="margin-top:20px">${w.step > 0 ? `<button class="btn" data-action="w-prev">${icon("arrowLeft")}Back</button>` : ""}<span class="spacer"></span>${w.step < 2 ? `<button class="btn primary" data-action="w-next">Next${icon("chevron")}</button>` : ""}</div>`, crumb("New review"));
    if (w.step === 0) refreshCaseSide();
  }
  const factRow = ([k, v], i) => `<div class="kv"><input class="input" data-input="fact-k" data-i="${i}" value="${esc(k)}" placeholder="Field, e.g. CrCl"><input class="input" data-input="fact-v" data-i="${i}" value="${esc(v)}" placeholder="Value and unit"><button class="btn ghost sm" data-action="fact-del" data-i="${i}" title="Remove">${icon("x")}</button></div>`;
  function stepCase() {
    const w = S.w, c = w.case;
    const form = `
      <div class="notice warn">${icon("lock")}<div>Use a <b>de-identified</b> case. Omit names and personal identifiers.</div></div>
      <div class="field" style="margin-top:16px"><label>Case ID</label><input class="input" data-input="case" data-k="case_id" value="${esc(c.case_id)}" placeholder="e.g. DEID-2026-001"></div>
      <div class="field" style="margin-top:14px"><label>Decision question</label><textarea class="textarea" data-input="case" data-k="question" placeholder="State the treatment decision and relevant clinical context">${esc(c.question)}</textarea><span class="hint">Specify the decision and treatment stage.</span></div>
      ${patientContextHTML()}
      <div class="field" style="margin-top:14px"><label>Verified patient facts</label>
        <div id="facts">${c.facts.map(factRow).join("")}</div>
        <div class="row wrap" style="margin-top:8px"><button class="btn sm" data-action="fact-add">${icon("plus")}Add field</button><span class="muted small">Quick add:</span>${QUICK.map((q) => `<button class="chip" data-action="fact-quick" data-k="${esc(q)}">${esc(q)}</button>`).join("")}</div>
        <span class="hint">Numbers and true / false are recognized automatically.</span></div>
      <div class="field" style="margin-top:14px"><label>Missing information</label>
        <div class="tags-input">${c.missing.map((m, i) => `<span class="tag-x">${esc(m)}<button data-action="miss-del" data-i="${i}" title="Remove">${icon("x")}</button></span>`).join("")}<input data-key="miss-add" placeholder="Add missing information, then press Enter"></div></div>`;
    const json = `<textarea class="textarea code" data-input="case-json" spellcheck="false">${esc(w.jsonError ? w.jsonDraft : JSON.stringify(buildCase(), null, 2))}</textarea><div id="json-err" class="small muted" style="margin-top:6px">Valid JSON syncs to the form.</div>`;
    return `<div class="grid g-side">
      <div class="card"><div class="card-h"><h3>${icon("file")}Case details</h3>
        <div class="row"><div class="seg"><button data-action="case-mode" data-m="form" class="${w.caseMode === "form" ? "on" : ""}">${icon("pen")}Form</button><button data-action="case-mode" data-m="json" class="${w.caseMode === "json" ? "on" : ""}">${icon("code")}JSON</button></div></div></div>
        <div class="card-b">${w.caseMode === "form" ? form : json}</div>
        <div class="card-h" style="border-top:1px solid var(--line-2);border-bottom:0">
          <div class="row wrap"><button class="btn sm" data-action="case-demo">${icon("flask")}Workflow demo</button><button class="btn sm" data-action="case-clinical">${icon("file")}Clinical example</button>
          <label class="btn sm" tabindex="0" role="button">${icon("upload")}Import JSON<input type="file" accept=".json,application/json" data-change="case-file" hidden></label></div>
          <button class="btn ghost sm danger" data-action="case-clear">${icon("trash")}Clear</button></div>
      </div>
      <div class="stack">
        <div class="card"><div class="card-h"><h3>${icon("shield")}Validation</h3></div><div class="card-b" id="case-check"></div></div>
        <details class="card preview-details"><summary>View structured case</summary><pre class="json" id="case-preview"></pre></details>
      </div></div>${intakeHTML()}`;
  }
  function refreshCaseSide() {
    const el = $("#case-check"); if (el) el.innerHTML = checkList(caseChecks());
    const pv = $("#case-preview"); if (pv) pv.innerHTML = jsonHTML(buildCase());
  }
  function stepEvidence() {
    const w = S.w, ev = w.evidence, ck = w.evidenceCheck;
    const left = ev ? `
      <div class="card-h"><h3>${icon("database")}${esc(w.evidenceName || "Evidence")}</h3><div class="row">
        <label class="btn sm" tabindex="0" role="button">${icon("upload")}Replace<input type="file" accept=".json,application/json" data-change="evidence-file" hidden></label>
        <button class="btn ghost sm danger" data-action="ev-clear">${icon("trash")}Remove</button></div></div>
      <div class="table-wrap"><table class="table"><thead><tr><th>ID / Title</th><th>Version</th><th>Roles</th><th>Source</th></tr></thead><tbody>
      ${ev.map((d) => `<tr class="click" data-action="evidence" data-id="${esc(d.id)}"><td><div class="mono small muted">${esc(d.id)}</div><div style="font-weight:600">${esc(d.title)}</div></td><td class="small">${esc(d.version)}</td><td>${(d.roles || []).map((r) => roleTag(r, 20)).join(" ")}</td><td>${d.synthetic ? badge("Synthetic", "warn") : badge("Source material", "ok")}</td></tr>`).join("")}
      </tbody></table></div>` : `
      <div class="card-h"><h3>${icon("database")}Evidence</h3></div>
      <div class="card-b">
        <label tabindex="0" role="button" class="dropzone" style="display:block">${icon("upload")}<div style="font-weight:600;color:var(--text-2)">Drop or select an evidence JSON file</div><div class="small">Array of evidence entries with source and version metadata</div><input type="file" accept=".json,application/json" data-change="evidence-file" hidden></label>
        <div class="row" style="margin-top:14px"><button class="btn sm" data-action="ev-demo">${icon("flask")}Load synthetic demo evidence</button></div>
        <details style="margin-top:16px"><summary class="muted small" style="cursor:pointer">Evidence format</summary><pre class="json" style="margin-top:10px">${jsonHTML([{ id: "SOURCE-SECTION-001", title: "Source title", source: "Source URL or document reference", version: "Version or date", text: "Verified source passage", roles: ["A", "B", "C"], synthetic: false }])}</pre></details>
      </div>`;
    const right = ck && ck.ok ? `<div class="grid g-2" style="gap:10px">
        <div class="card stat" style="box-shadow:none"><div><div class="stat-v">${ck.count}</div><div class="stat-l">Passages</div></div></div>
        <div class="card stat" style="box-shadow:none"><div><div class="stat-v" style="color:${ck.synthetic ? "var(--warn)" : "var(--ok)"}">${ck.synthetic}</div><div class="stat-l">Synthetic passages</div></div></div></div>
        <div class="muted small" style="margin:14px 0 8px">Eligible passages by role</div>
        <div class="appr">${ROLES.map((r) => `<div class="appr-cell ${ck.roles[r] ? "ok" : "no"}">${roleTag(r)}<div><div class="lbl">${ROLE[r].short}</div><b>Passages: ${ck.roles[r]}</b></div></div>`).join("")}</div>
        ${ROLES.some((r) => !ck.roles[r]) ? `<div class="notice warn" style="margin-top:12px">${icon("alert")}<div>One or more specialists have no eligible evidence.</div></div>` : ""}
        ${ck.synthetic ? `<div class="notice warn" style="margin-top:12px">${icon("flask")}<div>Synthetic material can only be used in demo mode.</div></div>` : ""}`
      : `<div class="muted">Select knowledge documents or import evidence before a model run.</div>`;
    return `<div class="evidence-library-link"><div>${icon("database")}<span>${w.knowledgeIds?.length ? `Library documents selected: ${w.knowledgeIds.length}` : "Select saved documents from your knowledge base"}</span></div><a class="btn" href="#/knowledge">${icon("book")}Choose from library</a></div><div class="grid g-side"><div class="card">${left}</div>
      <div class="stack"><div class="card"><div class="card-h"><h3>${icon("shield")}Evidence check</h3></div><div class="card-b">${right}</div></div>
      <div class="notice info">${icon("info")}<div>Citations reference the passages retrieved for this run.</div></div></div></div>`;
  }
  function startChecks() {
    const w = S.w, items = [];
    const env = S.info?.env || {};
    if (w.mode === "demo") {
      items.push(["ok", "Offline demo using deterministic responses"]);
      if (w.useDemoData) items.push(["ok", "Use the built-in synthetic case and evidence"]);
      else {
        items.push(...caseChecks().filter(([s]) => s !== "info"));
        items.push(w.evidence ? ["ok", `Evidence passages: ${w.evidence.length}`] : ["warn", "Using built-in synthetic evidence"]);
      }
    } else {
      items.push(...caseChecks().filter(([s]) => s !== "info"));
      const ck = w.evidenceCheck;
      if (!w.evidence) items.push(["bad", "Select or import evidence for a model run"]);
      else if (ck?.synthetic) items.push(["bad", `Evidence contains ${ck.synthetic} synthetic entries; not available in model mode`]);
      else items.push(["ok", `Evidence passages: ${w.evidence.length}`]);
      if (ck?.ok) for (const r of ROLES) if (!ck.roles[r]) items.push(["warn", `${r} has no eligible evidence`]);
      items.push(w.llm.model || env.model ? ["ok", `Model: ${w.llm.model || env.model}`] : ["bad", "Enter a model name"]);
      items.push(apiKey || env.api_key_set ? ["ok", apiKey ? "API key is set for this session" : "Using the server API key"] : ["bad", "Enter an API key"]);
      if (S.info && !S.info.httpx) items.push(["bad", 'Install the model adapter: python -m pip install -e ".[llm]"']);
      items.push(["warn", "Case and evidence will be sent to the configured endpoint"]);
    }
    const limits = [["max_revisions", "Max revisions", 0], ["concurrency", "Concurrency", 1], ["timeout", "Timeout", 1], ["top_k", "Passages", 1]];
    for (const [key, label, min] of limits) {
      const n = Number(w.settings?.[key]);
      if (!Number.isFinite(n) || !Number.isInteger(n) || n < min || String(w.settings?.[key]).trim() === "") items.push(["bad", `${label} must be an integer ≥ ${min}`]);
    }
    return { items, ok: !items.some(([s]) => s === "bad") };
  }
  function stepRun() {
    const w = S.w, env = S.info?.env || {}, sc = S.info?.scenarios || {};
    const modeCard = (m, ic, c, t, d) => `<button class="mode-card ${w.mode === m ? "on" : ""}" data-action="w-mode" data-m="${m}"><div class="stat-ic" style="background:var(--${c}-soft);color:var(--${c})">${icon(ic)}</div><div><b>${t}</b><p>${d}</p></div></button>`;
    const demo = `<div class="card"><div class="card-h"><h3>${icon("flask")}Demo scenarios</h3><span class="muted small">Choose a workflow scenario</span></div><div class="card-b">
        <div class="grid g-3" style="gap:10px">${Object.entries(sc).map(([k, v]) => `<button class="scenario ${w.scenario === k ? "on" : ""}" data-action="w-scenario" data-s="${k}"><b>${esc(v.title)} ${v.expect === "approved" ? badge("Approved", "ok", "nodot") : badge("Human review", "warn", "nodot")}</b><p>${esc(v.desc)}</p></button>`).join("")}</div>
        <div class="hr"></div>
        <div class="grid g-2"><div class="field"><label>Demo delay per call: <span id="pace-v">${Number(w.pace).toFixed(1)}</span> s</label><input type="range" min="0" max="2" step="0.1" value="${w.pace}" data-input="pace"></div>
        <label class="row" style="gap:8px;cursor:pointer"><input type="checkbox" data-change="use-demo" ${w.useDemoData ? "checked" : ""}> Use the built-in synthetic case and evidence</label></div>
      </div></div>`;
    const llm = `<div class="card"><div class="card-h"><h3>${icon("cpu")}Model endpoint</h3><span class="muted small">Structured output & tools</span></div><div class="card-b stack" style="gap:14px">${apiStyleHTML()}
        <div class="grid g-2"><div class="field"><label>Base URL</label><input class="input" data-input="llm" data-k="base_url" value="${esc(w.llm.base_url)}" placeholder="${esc(env.base_url || "https://api.openai.com/v1")}"></div>
        <div class="field"><label>Model name</label><input class="input" data-input="llm" data-k="model" value="${esc(w.llm.model)}" placeholder="${esc(env.model || "Model identifier")}"></div></div>
        <div class="field"><label>API Key</label><input class="input" type="password" autocomplete="off" data-input="apikey" value="${esc(apiKey)}" placeholder="${env.api_key_set ? "Server key is configured; leave blank to use it" : "sk-…"}"><span class="hint">${icon("lock")} Kept in this page session only.</span></div>
        <details><summary class="muted small" style="cursor:pointer">Assign models by role (optional)</summary><div class="grid g-4" style="margin-top:10px">${[...ROLES, "D"].map((r) => `<div class="field"><label>${r} · ${ROLE[r].short}</label><input class="input" data-input="llm-role" data-r="${r}" value="${esc(w.llm.role_models?.[r] || "")}" placeholder="${esc(env.role_models?.[r] || "Default")}"></div>`).join("")}</div></details>
        <div class="notice warn">${icon("alert")}<div>The configured endpoint receives the case and selected evidence.</div></div>
      </div></div>`;
    const s = w.settings;
    const num = (k, l, h, min, step = 1) => `<div class="field"><label>${l}</label><input class="input" type="number" min="${min}" step="${step}" data-input="setting" data-k="${k}" value="${esc(s[k])}"><span class="hint">${h}</span></div>`;
    const { items, ok } = startChecks();
    return `<div class="grid g-side"><div class="stack">
      <div class="grid g-2">${modeCard("demo", "flask", "brand", "Demo", "Explore the workflow without an API key")}${modeCard("llm", "cpu", "ok", "Model", "Use your configured model endpoint")}</div>
      ${w.mode === "demo" ? demo : llm}
      <div class="card"><div class="card-h"><h3>${icon("settings")}Advanced settings</h3></div><div class="card-b"><div class="grid g-4">
        ${num("max_revisions", "Max revisions", "Maximum revisions by D", 0)}${num("concurrency", "Concurrency", "Concurrent model calls", 1)}${num("timeout", "Timeout (seconds)", "Timeout per model call", 1)}${num("top_k", "Passages per role", "Top-K passages", 1)}
      </div></div></div>
    </div>
    <div class="card" style="position:sticky;top:0"><div class="card-h"><h3>${icon("target")}Preflight checks</h3></div><div class="card-b">
      ${checkList(items)}
      <button class="btn primary lg" style="width:100%;margin-top:18px" data-action="start" ${ok ? "" : "disabled"}>${icon("play")}Start review</button>
      <div class="muted small" style="margin-top:10px">Progress and results are saved locally.</div>
    </div></div></div>`;
  }

  /* ================= run detail ================= */
  async function viewRun(id, tab) {
    const route = routeVersion;
    setView(loading(), crumb("Reviews", id));
    let d;
    try { d = await api(`/api/runs/${encodeURIComponent(id)}`); }
    catch (e) { if (route !== routeVersion) return; setView(`<div class="empty">${icon("alert")}<div>${esc(e.message)}</div><a class="btn" href="#/history" style="margin-top:12px">Back to reviews</a></div>`); return; }
    if (route !== routeVersion) return;
    S.run = d; S.signDecision = "";
    S.runTab = tab || (d.status === "running" ? "live" : "report");
    S.evMap = Object.fromEntries((d.result?.evidence || []).map((x) => [x.id, x]));
    renderRunShell();
    if (d.status === "running") startStream(id);
  }
  function renderRunShell() {
    const d = S.run, done = !!d.result;
    const tabs = [["report", "steth", "Report"], ["live", "activity", "Live workflow"], ["versions", "git", "Version history"], ["audit", "database", "Audit log"]];
    const mode = d.mode === "llm" ? `<span class="chip">${icon("cpu")}${esc(d.meta?.model || "LLM")}</span>` : `<span class="chip">${icon("flask")}Demo${d.scenario ? " · " + esc(S.info?.scenarios?.[d.scenario]?.title || d.scenario) : ""}</span>`;
    setView(`<div class="run-head"><div class="title">
        <div class="row wrap"><a href="#/history" class="btn ghost sm">${icon("arrowLeft")}Back</a><span class="chip mono">${esc(d.id)}</span><span id="run-status">${statusBadge(d.status)}</span>${mode}</div>
        <h1 class="q">${esc(d.case?.question || "")}</h1>
        <div class="muted small">Case ${esc(d.case_id)} · Created ${fmtTime(d.created_at)}</div></div>
      <div class="row no-print">
        <button class="btn" data-action="reuse-case" title="Start another review with this case">${icon("refresh")}Reuse case</button>
        ${done ? `<a class="btn" href="/api/runs/${encodeURIComponent(d.id)}/report.md">${icon("download")}Report .md</a><a class="btn" href="/api/runs/${encodeURIComponent(d.id)}/result.json">${icon("code")}Data .json</a>` : ""}
        <button class="btn primary" data-action="print" ${done ? "" : "disabled"}>${icon("printer")}Print / PDF</button></div></div>
      <div class="tabs">${tabs.map(([k, ic, t]) => `<button class="${S.runTab === k ? "on" : ""}" data-action="tab" data-t="${k}">${icon(ic)}${t}</button>`).join("")}</div>
      <div id="run-body"></div>`, crumb("Reviews", d.case_id || d.id));
    renderRunBody();
  }
  function renderRunBody() {
    const el = $("#run-body"); if (!el) return;
    const d = S.run;
    if (S.runTab === "live") { el.innerHTML = liveHTML(d); drawWires(); }
    else if (S.runTab === "versions") el.innerHTML = versionsHTML(d);
    else if (S.runTab === "audit") el.innerHTML = auditHTML(d);
    else el.innerHTML = reportHTML(d);
  }
  let rafPending = false;
  const scheduleRender = () => { if (rafPending) return; rafPending = true; requestAnimationFrame(() => { rafPending = false; if (S.runTab === "live") renderRunBody(); }); };
  function startStream(id) {
    const route = routeVersion;
    let maxSeq = Math.max(0, ...S.run.events.map((e) => e.seq || 0));
    S.lastEvAt = performance.now();
    const es = new EventSource(`/api/runs/${encodeURIComponent(id)}/stream?after=${maxSeq}`);
    es.onopen = () => { if (route === routeVersion) $("#run-status").innerHTML = statusBadge(S.run.status); };
    es.onerror = () => { if (route === routeVersion) $("#run-status").innerHTML = badge("Disconnected · reconnecting", "warn"); };
    es.onmessage = (m) => {
      if (route !== routeVersion) return;
      const ev = JSON.parse(m.data);
      if (ev.seq && ev.seq <= maxSeq) return;
      maxSeq = Math.max(maxSeq, ev.seq || 0);
      S.run.events.push(ev); S.lastEvAt = performance.now();
      scheduleRender();
    };
    es.addEventListener("done", async () => {
      es.close();
      if (route !== routeVersion || !S.run || S.run.id !== id) return;
      try {
        const d = await api(`/api/runs/${encodeURIComponent(id)}`);
        if (route !== routeVersion) return;
        S.run = d; S.evMap = Object.fromEntries((d.result?.evidence || []).map((x) => [x.id, x]));
        renderRunShell();
        const s = STATUS[d.status] || {};
        toast(`Review complete: ${s.t || d.status}`, d.status === "approved" ? "ok" : d.status === "failed" ? "bad" : "info");
      } catch (e) { toast(e.message, "bad"); }
    });
    const tick = setInterval(() => { if (S.runTab === "live" && S.run?.status === "running") { const g = $("#gantt"); if (g) g.innerHTML = ganttHTML(derive(S.run.events)); const c = $("#elapsed"); if (c) c.textContent = fmtSec(liveNow(derive(S.run.events))); } }, 250);
    cleanup.push(() => { es.close(); clearInterval(tick); });
  }
  const liveNow = (st) => (S.run?.status === "running" && !st.finished ? st.now + (performance.now() - (S.lastEvAt || performance.now())) / 1000 : st.now);

  /* ---------- live monitor ---------- */
  function agentCard(r, a) {
    const ic = a.state === "working" ? `<span class="spinner"></span>` : a.state === "ok" ? icon("check") : a.state === "warn" ? icon("alert") : a.state === "bad" ? icon("x") : icon("clock");
    const color = { ok: "var(--ok)", warn: "var(--warn)", bad: "var(--bad)", working: "var(--run)" }[a.state] || "var(--text-3)";
    return `<div class="agent ${r === "D" ? "D" : ""} ${a.state}" data-role="${r}">
      <div class="ah"><img class="agent-avatar" src="/static/agent-${r.toLowerCase()}.svg" alt="Agent ${r}"><div><div class="an">${r === "D" ? "D · Coordinator" : `Agent ${r} · ${ROLE[r].short}`}</div><div class="ar">${ROLE[r].name}</div></div></div>
      <div class="astate" style="color:${color}">${ic}<span>${esc(a.label)}</span></div>
      ${a.note ? `<div class="anote">${esc(a.note)}</div>` : ""}</div>`;
  }
  function ganttHTML(st) {
    const now = liveNow(st), total = Math.max(now, 0.5);
    const rows = [...ROLES, "D"].map((r) => `<div class="g-row"><div class="g-l">${roleTag(r, 20)}${r === "D" ? "Coord." : "Agent"}</div><div class="g-track">
      ${st.calls.filter((c) => c.role === r).map((c) => {
        const end = c.end ?? now, left = (c.start / total) * 100, width = Math.max(((end - c.start) / total) * 100, 0.8);
        const mark = c.task === "review" && c.output ? (c.output.verdict === "approve" ? " ✓" : " ✗") : "";
        return `<div class="g-bar ${c.status === "running" ? "running" : ""}" style="left:${left}%;width:${width}%;background-color:${c.status === "failed" ? "var(--bad)" : `var(--${r})`}" title="${esc(TASK[c.task])}${c.version ? ` v${c.version}` : ""} · ${(end - c.start).toFixed(2)} s">${esc(TASK_SHORT[c.task] || c.task)}${c.version ? ` v${c.version}` : ""}${mark}</div>`;
      }).join("")}</div></div>`).join("");
    return `${rows}<div class="g-axis"><div></div><div>${[0, .25, .5, .75, 1].map((f) => `<span>${(total * f).toFixed(1)}s</span>`).join("")}</div></div>`;
  }
  function timelineItem(e) {
    const R = (r) => `<b>${r === "D" ? "Coordinator D" : `Agent ${r}`}</b>`;
    switch (e.event) {
      case "started": return ["var(--brand)", "Run started", `Max revisions ${e.settings?.max_revisions} · Concurrency ${e.settings?.max_concurrency} · Prompt ${e.prompt_version}`];
      case "clinical_checked": return ["var(--brand)", "Clinical data checked", `${e.report?.issues?.length || 0} findings · ${e.report?.calculations?.length || 0} calculations`];
      case "tool_started": return [`var(--${e.role})`, `${R(e.role)} requested a tool`, e.tool];
      case "tool_completed": return [`var(--${e.role})`, `${R(e.role)} received tool results`, `${e.tool} · ${e.result?.status || "complete"}`];
      case "call_completed":
        if (e.task === "assess") return [`var(--${e.role})`, `${R(e.role)} completed assessment`, e.output?.summary];
        if (e.task === "synthesize") return ["var(--D)", `${R("D")} created a draft`, ""];
        if (e.task === "revise") return ["var(--D)", `${R("D")} completed revision`, e.output?.reason];
        if (e.task === "review") { const v = VERDICT[e.output?.verdict] || {}; return [v.c === "ok" ? "var(--ok)" : v.c === "warn" ? "var(--warn)" : "var(--bad)", `${R(e.role)} Review v${e.version}: ${v.t || e.output?.verdict}`, [e.output?.note, ...(e.output?.issues || []).map((i) => `[${i.id}] ${i.problem}`)].filter(Boolean).join(" ")]; }
        return null;
      case "call_failed": return ["var(--bad)", `${R(e.role)} ${TASK[e.task] || e.task}Failed`, e.error];
      case "draft_created": return ["var(--D)", `Draft created <b>v${e.version}</b>`, "A / B / C review in parallel"];
      case "review_round": return ["var(--brand)", `Version ${e.version}  review started`, `Reviewers: ${(e.roles || []).join(", ")}`];
      case "draft_revised": return ["var(--D)", `Draft revised to <b>v${e.version}</b>`, `Review again: ${(e.roles || []).join(", ")}${e.reason ? " · " + e.reason : ""}`];
      case "finished": return [e.status === "approved" ? "var(--ok)" : e.status === "failed" ? "var(--bad)" : "var(--warn)", `Run finished: <b>${esc(STATUS[e.status]?.t || e.status)}</b>`, reasonText(e.reason)];
      default: return null;
    }
  }
  function liveHTML(d) {
    const st = derive(d.events);
    const fin = st.finished;
    const items = d.events.map((e) => [e, timelineItem(e)]).filter(([, x]) => x).reverse();
    S.lastTimelineSeq = S.lastTimelineSeq || {};
    const seen = S.lastTimelineSeq[d.id] || 0;
    S.lastTimelineSeq[d.id] = Math.max(seen, ...d.events.map((e) => e.seq || 0));
    const phaseIc = (p) => (p.state === "done" ? icon("check") : p.state === "fail" ? icon("x") : p.state === "stop" ? icon("alert") : p.state === "active" ? icon("zap") : "");
    return `<div class="stack">
      ${fin ? `<div class="notice ${fin.status === "approved" ? "info" : fin.status === "failed" ? "bad" : "warn"}">${icon(fin.status === "approved" ? "check" : "alert")}<div style="flex:1"><b>${esc(STATUS[fin.status]?.t || fin.status)}</b>: ${esc(reasonText(fin.reason))}</div>${d.result ? `<button class="btn sm primary" data-action="tab" data-t="report">${icon("steth")}View report</button>` : ""}</div>` : ""}
      <div class="card"><div class="card-h"><h3>${icon("layers")}Progress</h3><span class="row muted small">${icon("clock")}<span id="elapsed">${fmtSec(liveNow(st))}</span></span></div>
        <div class="phases">${st.phases.map((p) => `<div class="phase ${p.state}"><div class="dot">${phaseIc(p)}</div><span>${esc(p.label)}</span>${p.sub ? `<span class="small" style="margin-top:-6px">${esc(p.sub)}</span>` : ""}</div>`).join("")}</div></div>
      <div class="grid g-side"><div class="stack">
        <div class="card"><div class="card-h"><h3>${icon("users")}Agent collaboration</h3><span class="muted small">${st.version ? `Current draft v${st.version}` : "No draft yet"}</span></div>
          <div class="board" id="board"><svg class="wires"></svg><div class="agents">${ROLES.map((r) => agentCard(r, st.agents[r])).join("")}</div>${agentCard("D", st.agents.D)}</div></div>
        <div class="card"><div class="card-h"><h3>${icon("clock")}Call timeline</h3><span class="muted small">Overlapping bars indicate parallel calls</span></div><div class="gantt" id="gantt">${ganttHTML(st)}</div></div>
      </div>
      <div class="card"><div class="card-h"><h3>${icon("activity")}Events</h3>${badge(`${items.length} events`, "gray", "nodot")}</div>
        <ul class="timeline">${items.map(([e, [color, m, dd]]) => `<li class="${(e.seq || 0) > seen ? "new" : ""}" style="--tl:${color}"><div class="t">+${(e.elapsed_s ?? 0).toFixed(2)}s</div><div class="m">${m}</div>${dd ? `<div class="d">${esc(dd)}</div>` : ""}</li>`).join("") || `<li><div class="m muted">Waiting for events…</div></li>`}</ul></div>
      </div></div>`;
  }
  function drawWires() {
    const board = $("#board"); if (!board) return;
    const svg = $("svg.wires", board), D = $(".agent.D", board);
    if (!svg || !D) return;
    const st = derive(S.run.events);
    const rb = board.getBoundingClientRect(), rd = D.getBoundingClientRect();
    const paths = ROLES.map((r, i) => {
      const a = $(`.agent[data-role="${r}"]`, board).getBoundingClientRect();
      const x1 = a.left + a.width / 2 - rb.left, y1 = a.bottom - rb.top;
      const x2 = rd.left + rd.width / 2 - rb.left + (i - 1) * 60, y2 = rd.top - rb.top;
      const my = (y1 + y2) / 2;
      const flow = st.agents[r].state === "working" || st.agents.D.state === "working";
      return `<path class="${flow ? "flow" : ""}" d="M${x1},${y1} C${x1},${my} ${x2},${my} ${x2},${y2}"/>`;
    });
    svg.setAttribute("viewBox", `0 0 ${rb.width} ${rb.height}`);
    svg.innerHTML = paths.join("");
  }

  /* ---------- physician report ---------- */
  const evChips = (ids) => (ids || []).map((id) => `<button class="chip" data-action="evidence" data-id="${esc(id)}">${icon("book")}${esc(id)}</button>`).join("");
  function reportHTML(d) {
    const r = d.result;
    if (!r) {
      if (d.status === "running") return `<div class="card"><div class="empty">${icon("activity")}<div style="font-weight:600;color:var(--text-2)">Review in progress</div><div>The report appears when the run is complete.</div><button class="btn primary" style="margin-top:14px" data-action="tab" data-t="live">${icon("activity")}View live workflow</button></div></div>`;
      return `<div class="verdict bad"><div class="big-ic">${icon("x")}</div><div><h3>${d.status === "interrupted" ? "Run interrupted" : "Failed"}</h3><p>${esc(d.reason ? reasonText(d.reason) : "The service stopped before a result was produced.")}</p></div></div>`;
    }
    const v = { approved: ["ok", "check", d.signoffs.length ? "Agent review complete · physician review recorded" : "Agent review complete · awaiting physician", "The exact draft reviewed by the specialists."], needs_human_review: ["warn", "alert", "Needs human review", "Review the draft and unresolved issues below."], failed: ["bad", "x", "Failed", "The run stopped due to an error."] }[r.status] || ["bad", "x", r.status, ""];
    const draft = r.draft, c = d.case || {};
    const m = r.metrics || {};
    const pendingRoles = ROLES.filter((x) => r.approvals?.[x] == null);
    const facts = Object.entries(r.clinical_checks?.normalized_facts || c.facts || {});
    const sections = draft ? ROLES.map((x) => {
      const s = draft.sections[x], ap = r.approvals?.[x], rev = r.reviews?.[x];
      return `<div class="section-card ${x}"><div class="sh">${roleTag(x, 32)}<div style="flex:1"><div class="name">Agent ${x} · ${ROLE[x].name}</div><div class="sub">${ROLE[x].short} section</div></div>${ap != null ? badge(`v${ap} Approved`, "ok") : badge(VERDICT[rev?.verdict]?.t || "Not approved", rev?.verdict === "needs_information" ? "bad" : "warn")}</div>
        <div class="sb"><div class="stext">${esc(s.text)}</div>${rev?.note ? `<div class="row muted small" style="margin-top:12px;align-items:flex-start">${icon("message")}<span>Review note: ${esc(rev.note)}</span></div>` : ""}</div>
        <div class="sf"><span>Cited evidence</span>${evChips(s.evidence_ids)}${s.depends_on?.length ? `<span style="margin-left:10px">Dependencies</span>${s.depends_on.map((y) => roleTag(y, 20)).join("")}` : ""}</div></div>`;
    }).join("") : "";
    const issues = pendingRoles.flatMap((x) => (r.reviews?.[x]?.issues || []).map((i) => [x, r.reviews[x].verdict, i]));
    const last = d.signoffs.at(-1);
    return `<div class="print-only" style="margin-bottom:14px"><h2 style="margin:0">VTE review report</h2><div class="small muted">Run ${esc(d.id)} · Case ${esc(c.case_id)} · Generated ${fmtTime(d.created_at)} · Printed ${fmtTime(new Date().toISOString())}</div><div class="hr"></div></div>
    <div class="grid g-side"><div class="stack">
      <div class="verdict ${v[0]}"><div class="big-ic">${icon(v[1])}</div><div><h3>${v[2]}</h3><p>${esc(reasonText(r.reason))}.${v[3]}</p></div>
        <div class="verdict-kpis"><div><b>v${r.version}</b><span>Draft version</span></div><div><b>${r.revisions}</b><span>D revisions</span></div><div><b>${m.calls ?? "—"}</b><span>Model calls</span></div><div><b>${fmtSec(m.elapsed_s)}</b><span>Elapsed time</span></div></div></div>
      ${r.mode === "synthetic_demo" ? `<div class="notice warn">${icon("flask")}<div><b>Synthetic demo</b> · Workflow illustration only.</div></div>` : ""}
      ${(r.clinical_checks?.issues||[]).some(i=>i.severity==='blocking')?`<div class="card"><div class="card-h"><h3>${icon("alert")}Clinical information to resolve</h3></div><div class="card-b">${checkList(r.clinical_checks.issues.filter(i=>i.severity==='blocking').map(i=>['warn',i.roles.join('/')+': '+i.message]))}</div></div>`:""}
      <div class="card"><div class="card-h"><h3>${icon("user")}Case summary</h3><span class="chip mono">${esc(c.case_id)}</span></div><div class="card-b">
        <div style="font-weight:600;margin-bottom:10px">${esc(c.question)}</div>
        <dl class="facts">${facts.map(([k, val]) => `<dt>${esc(k)}</dt><dd>${esc(fmtVal(val))}</dd>`).join("")}</dl>
        ${(c.missing_information || []).length ? `<div style="margin-top:12px"><div class="muted small" style="margin-bottom:6px">Missing information</div><div class="row wrap">${c.missing_information.map((x) => `<span class="tag-x" style="padding-right:10px">${icon("alert")}${esc(x)}</span>`).join("")}</div></div>` : ""}
      </div></div>
      ${draft ? `<div class="plan"><div class="plan-label">${icon("target")}SHARED PLAN</div><div class="plan-text">${esc(draft.shared_plan)}</div></div>${sections}` : ""}
      ${issues.length ? `<div class="card"><div class="card-h"><h3>${icon("alert")}Open issues</h3>${badge(`${issues.length} items`, "warn", "nodot")}</div><div class="card-b">${issues.map(([x, verdict, i]) => `<div class="issue"><div class="ih">${roleTag(x, 22)}<span class="mono">${esc(i.id)}</span>${badge(VERDICT[verdict]?.t || verdict, VERDICT[verdict]?.c || "warn")}</div><div>${esc(i.problem)}</div><div class="req"><b>Requested change: </b>${esc(i.requested_change)}</div>${i.evidence_ids?.length || i.related_roles?.length ? `<div class="row wrap" style="margin-top:8px">${evChips(i.evidence_ids)}${(i.related_roles || []).map((y) => roleTag(y, 20)).join("")}</div>` : ""}</div>`).join("")}</div></div>` : ""}
      <div class="notice">${icon("shield")}<div>Research output. Final clinical decisions require physician review.</div></div>
      <div class="print-only" style="margin-top:18px">${last ? `<div>Reviewer: <b>${esc(last.reviewer)}</b> Decision: <b>${esc(DECISION[last.decision]?.t)}</b> Time: ${fmtTime(last.signed_at)}</div>${last.comment ? `<div>Note: ${esc(last.comment)}</div>` : ""}<div class="small muted mono">Draft SHA-256: ${esc(last.draft_sha256)}</div>` : `<div style="margin-top:28px">Physician signature: ＿＿＿＿＿＿＿＿  Date: ＿＿＿＿＿＿＿＿</div>`}</div>
    </div>
    <div class="stack no-print">
      <div class="card"><div class="card-h"><h3>${icon("users")}Specialist approvals</h3></div><div class="card-b"><div class="appr" style="grid-template-columns:1fr">
        ${ROLES.map((x) => { const ap = r.approvals?.[x]; const rv = r.reviews?.[x]; return `<div class="appr-cell ${ap != null ? "ok" : "no"}">${roleTag(x)}<div style="flex:1"><div class="lbl">${ROLE[x].name}</div><b>${ap != null ? `v${ap} Approved` : VERDICT[rv?.verdict]?.t || "Not approved"}</b></div>${ap != null ? icon("check") : icon("alert")}</div>`; }).join("")}
        <div class="appr-cell" style="background:var(--D-soft);border-color:#c6d5fb">${roleTag("D")}<div style="flex:1"><div class="lbl">Coordinator · synthesis and revision</div><b>Total ${r.revisions}  revisions</b></div></div>
      </div></div></div>
      ${signHTML(d)}
      <div class="card"><div class="card-h"><h3>${icon("book")}Cited evidence</h3>${badge(`Passages: ${(r.evidence || []).length}`, "gray", "nodot")}</div><div class="card-b" style="padding-top:4px;padding-bottom:4px">
        ${(r.evidence || []).map((e) => `<div class="ev-row"><div><div style="font-weight:600">${esc(e.title)}</div><div class="muted small">${esc(e.id)} · ${esc(e.version)} ${e.synthetic ? "· Synthetic" : ""}</div></div><button class="btn ghost sm" data-action="evidence" data-id="${esc(e.id)}">Source${icon("chevron")}</button></div>`).join("") || `<div class="muted">None</div>`}
      </div></div>
    </div></div>`;
  }
  function signHTML(d) {
    const r = d.result;
    if (!r || !r.draft) return "";
    const last = d.signoffs.at(-1);
    const dec = S.signDecision;
    const hist = d.signoffs.slice().reverse().map((s) => `<div class="seal"><div class="row">${badge(DECISION[s.decision]?.t || s.decision, DECISION[s.decision]?.c || "gray")}<b>${esc(s.reviewer)}</b><span class="spacer"></span><span class="muted small">${fmtTime(s.signed_at)}</span></div>${s.comment ? `<div style="margin:6px 0">${esc(s.comment)}</div>` : ""}<div class="hash">Draft v${esc(s.draft_version)} · SHA-256 ${esc(s.draft_sha256)}</div></div>`).join("");
    return `<div class="card sign"><div class="card-h"><h3>${icon("pen")}Physician review</h3>${last ? badge(`Signed · ${DECISION[last.decision]?.t}`, DECISION[last.decision]?.c) : badge("Awaiting sign-off", "gray")}</div><div class="card-b stack" style="gap:12px">
      <div class="decisions" id="decisions">${Object.entries(DECISION).map(([k, v]) => `<button class="decision ${k} ${dec === k ? "on" : ""}" data-action="decision" data-d="${k}">${icon(v.i)}${v.t}</button>`).join("")}</div>
      <div class="field"><label for="sign-name">Reviewer</label><input class="input" id="sign-name" value="${esc(localStorage.getItem("vte.reviewer") || "")}" placeholder="Name or staff ID"></div>
      <div class="field"><label for="sign-comment">Review note</label><textarea class="textarea" id="sign-comment" placeholder="Required for changes or rejection: explain your decision"></textarea></div>
      <button class="btn primary" data-action="sign">${icon("lock")}Save review</button>
      <div class="muted small">Recorded against draft v${r.version} using a SHA-256 draft fingerprint.</div>
      ${hist ? `<div class="hr" style="margin:4px 0"></div><div class="muted small">Review history</div>${hist}` : ""}
    </div></div>`;
  }

  /* ---------- versions ---------- */
  function versionsHTML(d) {
    const st = derive(d.events);
    if (!st.drafts.length) return `<div class="card"><div class="empty">${icon("git")}<div>No draft yet</div></div></div>`;
    const reviews = {};
    for (const c of st.calls) if (c.task === "review" && c.output) (reviews[c.version] ||= []).push(c);
    const parts = [["shared_plan", "Shared plan"], ...ROLES.map((r) => [r, `${r} · ${ROLE[r].short}`])];
    const textOf = (dr, k) => (k === "shared_plan" ? dr.shared_plan : dr.sections[k].text);
    const metaOf = (dr, k) => (k === "shared_plan" ? "" : JSON.stringify([dr.sections[k].evidence_ids, dr.sections[k].depends_on]));
    return `<div class="stack">${st.drafts.map((dv, i) => {
      const prev = st.drafts[i - 1];
      const changed = prev ? parts.filter(([k]) => textOf(prev.draft, k) !== textOf(dv.draft, k) || metaOf(prev.draft, k) !== metaOf(dv.draft, k)) : parts;
      const same = prev ? parts.filter((p) => !changed.includes(p)) : [];
      const rv = (reviews[dv.version] || []).sort((a, b) => a.role.localeCompare(b.role));
      return `<div class="card"><div class="card-h"><h3>${badge(`v${dv.version}`, "run", "nodot")}${dv.initial ? "Initial draft by D" : "D revises"}</h3>
          <div class="row">${dv.initial ? "" : `<span class="muted small">Review again</span>${dv.roles.map((r) => roleTag(r, 22)).join("")}`}</div></div>
        <div class="card-b stack" style="gap:14px">
          ${dv.reason ? `<div class="notice info">${icon("pen")}<div><b>Revision rationale: </b>${esc(dv.reason)}</div></div>` : ""}
          ${changed.map(([k, label]) => `<div><div class="row" style="margin-bottom:6px">${k === "shared_plan" ? `<span class="chip">${icon("target")}${label}</span>` : `${roleTag(k, 22)}<b class="small">${esc(label)}</b>`}${prev ? badge("Modified", "warn", "nodot") : ""}${prev && metaOf(prev.draft, k) !== metaOf(dv.draft, k) ? badge("Citations / dependencies changed", "gray", "nodot") : ""}</div>
            <div class="diff" style="padding:12px 14px;background:var(--panel-2);border-radius:10px;border:1px solid var(--line-2)">${prev ? diffHTML(textOf(prev.draft, k), textOf(dv.draft, k)) : esc(textOf(dv.draft, k))}</div></div>`).join("")}
          ${same.length ? `<div class="muted small row">${icon("check")}Unchanged: ${same.map(([, l]) => esc(l)).join(", ")}</div>` : ""}
          ${rv.length ? `<div class="hr" style="margin:2px 0"></div><div class="muted small">v${dv.version} Review results</div>
            ${rv.map((c) => { const vv = VERDICT[c.output.verdict] || {}; return `<div class="row" style="align-items:flex-start">${roleTag(c.role, 26)}<div style="flex:1"><div class="row">${badge(vv.t || c.output.verdict, vv.c || "gray")}<span class="small">${esc(c.output.note)}</span></div>${(c.output.issues || []).map((is) => `<div class="issue" style="margin-top:8px"><div class="ih"><span class="mono small">${esc(is.id)}</span>${esc(is.problem)}</div><div class="req">Requested change: ${esc(is.requested_change)}</div></div>`).join("")}</div></div>`; }).join("")}` : ""}
        </div></div>`;
    }).join("")}</div>`;
  }

  /* ---------- audit ---------- */
  function auditHTML(d) {
    const r = d.result, m = r?.metrics || {};
    const stat = (v, l, ic, c) => `<div class="card stat"><div class="stat-ic" style="background:var(--${c}-soft);color:var(--${c})">${icon(ic)}</div><div><div class="stat-v" style="font-size:20px">${v}</div><div class="stat-l">${l}</div></div></div>`;
    const label = (e) => `${e.event}${e.task ? ` · ${e.task}` : ""}${e.role ? ` · ${e.role}` : ""}${e.version ? ` · v${e.version}` : ""}`;
    const tone = (e) => (e.event === "call_failed" ? "bad" : e.event === "finished" ? (e.status === "approved" ? "ok" : "warn") : e.event.startsWith("draft") ? "run" : "gray");
    return `<div class="stack">${workspaceAuditHTML(d)}
      <div class="grid g-4">${stat(fmtSec(m.elapsed_s), "Elapsed time", "clock", "brand")}${stat(`${m.calls ?? "—"} <span class="muted small">/ Review ${m.review_calls ?? "—"}</span>`, "Model calls", "cpu", "ok")}${stat(m.usage_reported_calls ? m.reported_total_tokens : "Not reported", "Reported tokens", "zap", "warn")}${stat(d.events.length, "Events", "activity", "run")}</div>
      <div class="grid g-2">
        <div class="card"><div class="card-h"><h3>${icon("settings")}Run configuration</h3></div><div class="card-b"><pre class="json">${jsonHTML({ mode: r?.mode || d.mode, prompt_version: r?.prompt_version, settings: r?.settings, meta: d.meta })}</pre></div></div>
        <div class="card"><div class="card-h"><h3>${icon("file")}Case data</h3></div><div class="card-b"><pre class="json">${jsonHTML(d.case)}</pre></div></div>
      </div>
      <div class="card"><div class="card-h"><h3>${icon("database")}Event log</h3><span class="muted small">Full payloads are available in the run directory</span></div><div class="card-b">
        ${d.events.map((e) => `<details class="ev"><summary><span class="mono muted">#${e.seq ?? "—"}</span><span class="mono muted">+${(e.elapsed_s ?? 0).toFixed(3)}s</span>${badge(label(e), tone(e), "nodot")}${e.duration_s != null ? `<span class="muted small">${e.duration_s}s</span>` : ""}</summary><div class="body"><pre class="json">${jsonHTML(e)}</pre></div></details>`).join("")}
      </div></div></div>`;
  }

  /* ================= settings ================= */
  async function viewSettings() {
    const route = routeVersion;
    try { const info = await api("/api/info"); if (route !== routeVersion) return; S.info = info; }
    catch (e) { if (route !== routeVersion) return; toast(e.message, "bad"); }
    const i = S.info || {}, env = i.env || {}, w = S.w;
    const row = (k, v) => `<dt>${esc(k)}</dt><dd>${v}</dd>`;
    setView(`<div class="page-h"><div><h1 class="h1">Settings</h1><p class="lead">Configure model access and role assignments.</p></div>${badge(env.api_key_set || apiKey ? "Credentials available" : "Demo ready", env.api_key_set || apiKey ? "ok" : "gray")}</div>
      <div class="grid g-side"><div class="stack"><section class="card"><div class="card-h"><h3>${icon("cpu")}Model connection</h3><span class="muted small">Structured output & tools</span></div><div class="card-b stack">${apiStyleHTML()}<div class="profile-fields">
      <div class="field"><label>Base URL</label><input class="input" data-input="llm" data-k="base_url" value="${esc(w.llm.base_url)}" placeholder="${esc(env.base_url || "https://api.openai.com/v1")}"></div>
      <div class="field"><label>Default model</label><input class="input" data-input="llm" data-k="model" value="${esc(w.llm.model)}" placeholder="${esc(env.model || "Model identifier from your provider")}"></div>
      <div class="field wide"><label>API Key</label><input class="input" type="password" autocomplete="off" data-input="apikey" value="${esc(apiKey)}" placeholder="${env.api_key_set ? "Server credentials are available" : "Model service API key"}"><span class="hint">API key stays in memory. Endpoint and model names are saved locally.</span></div></div>
      <div class="row wrap"><button class="btn primary" data-action="profile-save">${icon("check")}Save configuration</button><button class="btn ghost" data-action="clear-key">Clear session key</button><a class="btn ghost" href="#/new">New review${icon("chevron")}</a></div></div></section>
      <section class="card"><div class="card-h"><h3>${icon("users")}Role assignments</h3><span class="muted small">Optional · inherits the default model</span></div><div class="card-b profile-fields">${[...ROLES,"D"].map((r) => `<div class="field"><label>${r} · ${ROLE[r].short}</label><input class="input" data-input="llm-role" data-r="${r}" value="${esc(w.llm.role_models?.[r] || "")}" placeholder="${esc(env.role_models?.[r] || "Use default model")}"></div>`).join("")}</div></section>
      <div class="notice info">${icon("info")}<div>Choose Model mode in a new review to use this connection.</div></div></div>
      <div class="stack"><section class="card"><div class="card-h"><h3>${icon("activity")}Environment</h3></div><div class="card-b"><dl class="facts">${row("App version",`v${esc(i.version)}`)}${row("Prompt version",esc(i.prompt_version))}${row("Model adapter",i.httpx ? badge("httpx installed","ok") : badge("Not installed","warn"))}${row("Database", "SQLite + FTS5")}${row("Library", `${i.knowledge?.documents || 0} documents`)}${row("Default retrieval",`Top-${i.defaults?.top_k}`)}${row("Concurrency / revisions",`${i.defaults?.max_concurrency} concurrent / ${i.defaults?.max_revisions} max revisions`)}${row("Timeout",`${i.defaults?.call_timeout} s`)}</dl></div></section>
      <section class="card"><div class="card-h"><h3>${icon("folder")}Local storage</h3></div><div class="card-b"><p class="small muted" style="margin-top:0">Run records are stored in:</p><div class="mono" style="overflow-wrap:anywhere;font-size:11px">${esc(i.runs_dir)}</div><div class="hr"></div><p class="small muted">API keys are not stored in run records.</p><a href="#/guide" class="btn sm">Quick start${icon("chevron")}</a></div></section></div></div>`,crumb("Settings"));
  }
  function viewGuide() {
    const steps = [["Case","Enter a de-identified case, a decision question and verified facts."],["Knowledge","Add source documents to the library. Search passages and select documents for the review."],["Run","Use the offline demo or configure a model connection in Settings."],["Collaboration","A, B and C assess independently. D combines their findings into a draft."],["Revision","Specialists review their sections. D revises issues; affected specialists review again."],["Review & export","Inspect sources and version changes, record a physician decision and export the report."]];
    setView(`<div class="page-h"><h1 class="h1">Quick start</h1><button class="btn primary" data-action="quick-demo" data-s="targeted">${icon("play")}Run demo</button></div><div class="guide-grid">${steps.map(([title,text],n) => `<section class="card guide-step"><span class="number">0${n+1}</span><h3>${title}</h3><p>${text}</p></section>`).join("")}</div>`,crumb("Quick start"));
  }

  /* ================= actions ================= */
  const actions = {
    reload: () => onRoute(),
    "profile-save": () => { saveWizard(); toast("Configuration saved. API key is session-only.", "ok"); viewSettings(); },
    "clear-key": () => { apiKey = ""; viewSettings(); toast("Session key cleared"); },
    "open-run": (el) => { location.hash = `#/run/${encodeURIComponent(el.dataset.id)}`; },
    "close-drawer": closeDrawer,
    evidence: (el) => openEvidence(el.dataset.id),
    "quick-demo": async (el) => {
      el.disabled = true;
      try { const { id } = await api("/api/runs", { body: { mode: "demo", scenario: el.dataset.s || "targeted", pace: 0.8 } }); location.hash = `#/run/${id}`; }
      catch (e) { toast(e.message, "bad"); el.disabled = false; }
    },
    "hist-f": (el) => { S.hist.f = el.dataset.f; $$("[data-action=hist-f]").forEach((b) => b.classList.toggle("on", b === el)); $("#hist-body").innerHTML = runRows(filterRuns()); },
    tab: (el) => { S.runTab = el.dataset.t; history.replaceState(null, "", `#/run/${encodeURIComponent(S.run.id)}?tab=${S.runTab}`); $$(".tabs button").forEach((b) => b.classList.toggle("on", b.dataset.t === S.runTab)); renderRunBody(); $("#view").scrollTop = 0; },
    print: () => { if (S.runTab !== "report") { S.runTab = "report"; renderRunShell(); } setTimeout(() => window.print(), 200); },
    "reuse-case": () => { S.w = S.w || loadWizard(); S.w.case = caseFromJSON(S.run.case || {}); S.w.sources=[];S.w.labels=[];S.w.extractionIssues=[];delete S.w.jsonDraft; S.w.jsonError = false; S.w.step = 0; S.w.caseMode = "form"; S.w.useDemoData = false; saveWizard(); location.hash = "#/new"; toast("Case loaded for a new review", "ok"); },
    decision: (el) => { S.signDecision = el.dataset.d; $$("#decisions .decision").forEach((b) => b.classList.toggle("on", b === el)); },
    sign: async (el) => {
      const reviewer = $("#sign-name").value.trim(), comment = $("#sign-comment").value.trim();
      if (!S.signDecision) return toast("Select a decision", "bad");
      if (!reviewer) return toast("Enter the reviewer name", "bad");
      if (S.signDecision !== "accept" && !comment) return toast("Enter a review note", "bad");
      el.disabled = true;
      try {
        await api(`/api/runs/${encodeURIComponent(S.run.id)}/signoff`, { body: { decision: S.signDecision, reviewer, comment } });
        localStorage.setItem("vte.reviewer", reviewer);
        S.run = await api(`/api/runs/${encodeURIComponent(S.run.id)}`); S.signDecision = "";
        renderRunBody(); toast("Review saved", "ok");
      } catch (e) { toast(e.message, "bad"); el.disabled = false; }
    },
    // wizard
    "w-step": (el) => { S.w.step = +el.dataset.i; saveWizard(); renderWizard(); },
    "w-prev": () => { S.w.step = Math.max(0, S.w.step - 1); saveWizard(); renderWizard(); },
    "w-next": () => { S.w.step = Math.min(2, S.w.step + 1); saveWizard(); renderWizard(); },
    "w-reset": () => { if (!confirm("Reset the case, evidence and settings?")) return; S.w = defaultWizard(); S.w.settings = defaultsToSettings(); apiKey = ""; saveWizard(); renderWizard(); },
    "case-mode": (el) => { if (S.w.jsonError && el.dataset.m === "form") return toast("Correct the JSON before switching to the form", "bad"); S.w.caseMode = el.dataset.m; saveWizard(); renderWizard(); },
    "fact-add": () => { S.w.case.facts.push(["", ""]); saveWizard(); renderWizard(); const ins = $$("[data-input=fact-k]"); ins[ins.length - 1]?.focus(); },
    "fact-del": (el) => { S.w.case.facts.splice(+el.dataset.i, 1); if (!S.w.case.facts.length) S.w.case.facts.push(["", ""]); saveWizard(); renderWizard(); },
    "fact-quick": (el) => {
      const k = el.dataset.k, f = S.w.case.facts;
      let i = f.findIndex(([x]) => x === k);
      if (i < 0) { i = f.findIndex(([x, v]) => !x && !v); if (i < 0) { f.push([k, ""]); i = f.length - 1; } else f[i][0] = k; }
      saveWizard(); renderWizard(); $(`[data-input=fact-v][data-i="${i}"]`)?.focus();
    },
    "miss-del": (el) => { S.w.case.missing.splice(+el.dataset.i, 1); saveWizard(); renderWizard(); },
    "case-demo": async () => { try { const d = await api("/api/demo"); S.w.case = caseFromJSON(d.case); S.w.sources=[];S.w.labels=[];S.w.extractionIssues=[];delete S.w.jsonDraft; S.w.jsonError = false; saveWizard(); renderWizard(); toast("Synthetic case loaded", "ok"); } catch (e) { toast(e.message, "bad"); } },
    "case-clear": () => { S.w.case = blankCase(); S.w.sources=[];S.w.labels=[];S.w.extractionIssues=[];delete S.w.jsonDraft; S.w.jsonError = false; saveWizard(); renderWizard(); },
    "ev-demo": async () => { try { const d = await api("/api/demo"); await setEvidence(d.evidence, "Synthetic demo evidence"); } catch (e) { toast(e.message, "bad"); } },
    "ev-clear": () => { S.w.knowledgeIds = null; S.w.evidence = null; S.w.evidenceName = ""; S.w.evidenceCheck = null; S.evMap = {}; saveWizard(); renderWizard(); },
    "w-mode": (el) => { S.w.mode = el.dataset.m; saveWizard(); renderWizard(); },
    "w-scenario": (el) => { S.w.scenario = el.dataset.s; saveWizard(); $$("[data-action=w-scenario]").forEach((b) => b.classList.toggle("on", b === el)); },
    start: async (el) => {
      const w = S.w;
      if (!startChecks().ok) return toast("Resolve the preflight checks first", "bad");
      const body = { mode: w.mode, settings: w.settings };
      if (w.mode === "demo") {
        body.scenario = w.scenario; body.pace = w.pace;
        if (!w.useDemoData) { body.case = buildCase(); if (w.evidence) body.evidence = w.evidence; }
      } else {
        body.case = buildCase(); body.evidence = w.evidence;
        body.llm = connection();
      }
      if (w.knowledgeIds?.length && (w.mode === "llm" || !w.useDemoData)) body.knowledge_ids = w.knowledgeIds;
      if (w.mode === "llm" || !w.useDemoData) body.research_labels = w.labels || [];
      el.disabled = true; el.innerHTML = `<span class="spinner" style="border-color:rgba(255,255,255,.4);border-top-color:#fff"></span>Starting…`;
      try { const { id } = await api("/api/runs", { body }); location.hash = `#/run/${id}`; }
      catch (e) { toast(e.message, "bad"); renderWizard(); }
    },
  };
  async function setEvidence(arr, name) {
    const res = await api("/api/validate", { body: { evidence: arr } });
    if (!res.evidence?.ok) { toast(`Invalid evidence: ${res.evidence?.error}`, "bad"); return; }
    S.w.knowledgeIds = null;
    S.w.evidence = arr; S.w.evidenceName = name; S.w.evidenceCheck = res.evidence;
    S.evMap = Object.fromEntries(arr.map((d) => [d.id, d]));
    saveWizard(); renderWizard(); toast(`Imported ${res.evidence.count} passages`, "ok");
  }
  const readFile = (file) => new Promise((ok, bad) => { const fr = new FileReader(); fr.onload = () => ok(String(fr.result).replace(/^\uFEFF/, "")); fr.onerror = bad; fr.readAsText(file, "utf-8"); });
  async function importEvidenceFile(file) {
    if (!file) return;
    try { const data = JSON.parse(await readFile(file)); if (!Array.isArray(data)) throw new Error("Evidence must be a JSON array"); await setEvidence(data, file.name); }
    catch (e) { toast(e.message, "bad"); }
  }


  /* ================= persistent knowledge library ================= */
  const K = {documents:[], stats:{}, q:"", role:"", results:null, archived:false, selected:new Set(), searchVersion:0, form:null};
  async function viewKnowledge() {
    const route = routeVersion;
    const search = ++K.searchVersion;
    setView(loading(), crumb("Knowledge base"));
    try {
      const data = await api(`/api/knowledge${K.archived ? "?archived=1" : ""}`);
      if (route !== routeVersion || search !== K.searchVersion) return;
      K.documents = data.documents; K.stats = data.stats;
      K.results = null; K.q = "";
      renderKnowledge();
    } catch(e) { if (route === routeVersion && search === K.searchVersion) { setView(`<div class="empty"><p>${esc(e.message)}</p><button class="btn" data-action="reload">Try again</button></div>`); } }
  }
  function libraryRows() {
    const list = K.results === null ? K.documents.filter(d => !K.role || d.roles.includes(K.role)) : K.results;
    if (!list.length) return `<div class="library-empty">${icon(K.q ? "search" : "book")}<h3>${K.q ? "No matching passages" : K.archived ? "No archived documents" : "Your library is ready"}</h3><p>${K.q ? "Try a different term or specialist filter." : K.archived ? "Archived documents appear here." : "Add guidelines, references or local documents."}</p>${!K.q && !K.archived ? `<button class="btn primary" data-action="kb-add">${icon("plus")}Add document</button>` : ""}</div>`;
    return list.map(d => { const id = d.document_id || d.id; return `<article class="knowledge-item"><div class="knowledge-main">${K.archived ? "" : `<input type="checkbox" aria-label="Select ${esc(d.title)}" data-change="kb-select" data-id="${esc(id)}" ${K.selected.has(id) ? "checked" : ""}>`}<div class="knowledge-content"><div class="row wrap"><button class="text-link" data-action="kb-detail" data-id="${esc(id)}">${esc(d.title)}</button>${d.synthetic ? badge("Synthetic","warn","nodot") : ""}</div><div class="knowledge-meta">${esc(d.source)}<span>Version ${esc(d.version)}</span></div>${d.text ? `<p class="search-excerpt">${esc(d.text.length > 480 ? d.text.slice(0,480)+"…" : d.text)}</p>` : ""}<div class="row wrap" style="margin-top:10px">${d.roles.map(r=>roleTag(r,20)).join("")}<span class="muted small">${d.ordinal ? `Passage ${d.ordinal}` : `Passages: ${d.chunks} · Characters: ${Number(d.characters).toLocaleString()}`}</span></div></div><button class="btn ghost sm" data-action="kb-archive" data-id="${esc(id)}" data-value="${K.archived ? "false" : "true"}" title="${K.archived ? "Restore document" : "Archive document"}">${icon(K.archived ? "refresh" : "folder")}${K.archived ? "Restore" : "Archive"}</button></div></article>`; }).join("");
  }
  function renderKnowledge() {
    setView(`<div class="page-h"><div><h1 class="h1">Knowledge base</h1><p class="lead">Documents: ${K.stats.documents || 0} · Indexed passages: ${K.stats.chunks || 0}</p></div><button class="btn primary" data-action="kb-add">${icon("plus")}Add document</button></div>
      <section class="card"><div class="knowledge-toolbar"><div class="knowledge-search">${icon("search")}<input class="input" aria-label="Search knowledge base" data-input="kb-q" data-key="kb-search" placeholder="Search guidelines, drugs or clinical terms" value="${esc(K.q)}"><button class="btn primary" data-action="kb-search">Search</button></div><select class="select" aria-label="Specialist filter" data-change="kb-role"><option value="">All specialists</option>${ROLES.map(r=>`<option value="${r}" ${K.role === r ? "selected" : ""}>${r} · ${ROLE[r].short}</option>`).join("")}</select></div>
      <div class="knowledge-controls"><div class="seg"><button data-action="kb-view" data-mode="active" class="${K.archived ? "" : "on"}">Documents</button><button data-action="kb-view" data-mode="archived" class="${K.archived ? "on" : ""}">Archived</button></div><div class="row"><span id="kb-selected-count" class="muted small">${K.selected.size} selected</span><button class="btn sm" id="kb-use" data-action="kb-use" ${K.selected.size ? "" : "disabled"}>Use in review${icon("chevron")}</button></div></div>
      <div id="kb-results">${libraryRows()}</div><div class="knowledge-foot"><span>${icon("database")}Indexed locally</span><span id="kb-result-count">${K.results ? `Matching passages: ${K.results.length}` : "Source text stays on this device"}</span></div></section>`,crumb("Knowledge base"));
  }
  async function searchKnowledge() {
    const route = routeVersion, search = ++K.searchVersion;
    if (!K.q.trim()) { await viewKnowledge(); return; }
    if (K.archived) { K.archived = false; K.selected.clear(); }
    const button = $("[data-action=kb-search]"); if (button) button.disabled = true;
    try {
      const data = await api(`/api/knowledge/search?q=${encodeURIComponent(K.q)}&role=${encodeURIComponent(K.role)}`);
      if (route !== routeVersion || search !== K.searchVersion) return;
      K.results = data.results; renderKnowledge();
    } catch (e) { if (route === routeVersion && search === K.searchVersion) { toast(e.message,"bad"); if (button) button.disabled = false; } }
  }
  function showDocumentForm() {
    const f = K.form;
    openDrawer(`<div class="dh"><div style="flex:1"><h3 style="margin:0">Add document</h3><span class="muted small">PDF, TXT, Markdown or evidence JSON</span></div><button class="btn ghost sm" data-action="close-drawer" aria-label="Close">${icon("x")}</button></div><div class="db stack">
      <label class="dropzone" tabindex="0" role="button">${icon("upload")}<b>Choose a file</b><span class="small">Up to 5 MB · or paste text below</span><input type="file" accept=".pdf,.txt,.md,.json" data-change="kb-file" hidden></label><div id="kb-file-status" class="muted small" role="status">${esc(f.filename || "")}</div>
      ${f.batch ? `<div class="notice info">${icon("file")}<div>${f.batch.length} evidence entries ready to import.<ul>${f.batch.slice(0,5).map(d=>`<li>${esc(d.title)}</li>`).join("")}</ul></div></div>` : `<div class="field"><label for="kb-title">Title</label><input id="kb-title" class="input" data-input="kb-field" data-k="title" value="${esc(f.title)}" placeholder="Document title"></div><div class="profile-fields"><div class="field"><label for="kb-source">Source</label><input id="kb-source" class="input" data-input="kb-field" data-k="source" value="${esc(f.source)}" placeholder="Publisher, URL or reference"></div><div class="field"><label for="kb-version">Version</label><input id="kb-version" class="input" data-input="kb-field" data-k="version" value="${esc(f.version)}" placeholder="Edition or publication date"></div></div><fieldset class="knowledge-roles"><legend>Specialists</legend>${ROLES.map(r=>`<label><input type="checkbox" data-change="kb-form-role" data-r="${r}" ${f.roles.includes(r) ? "checked" : ""}>${roleTag(r,22)}${ROLE[r].short}</label>`).join("")}</fieldset><label class="row small"><input type="checkbox" data-change="kb-synthetic" ${f.synthetic ? "checked" : ""}>Synthetic test material</label><div class="field"><label for="kb-text">Source text</label><textarea id="kb-text" class="textarea" style="min-height:240px" data-input="kb-field" data-k="text" placeholder="Paste the source text or extract it from a file">${esc(f.text)}</textarea></div>`}
      <div id="kb-form-error" class="form-error" role="alert"></div><button class="btn primary" data-action="kb-save">${icon("plus")}${f.batch ? `Import ${f.batch.length} entries` : "Save to knowledge base"}</button></div>`);
  }
  async function importKnowledgeFile(file) {
    if (!file) return;
    if (file.size > 5 * 1024 * 1024) return toast("File must be smaller than 5 MB","bad");
    const form = K.form;
    $("#kb-file-status").textContent = "Reading file…";
    try {
      let content;
      if (/\.pdf$/i.test(file.name)) {
        const data = await new Promise((resolve,reject)=>{const r=new FileReader();r.onload=()=>resolve(r.result);r.onerror=reject;r.readAsDataURL(file);});
        const result = await api("/api/knowledge/extract",{body:{filename:file.name,content_base64:String(data).split(",")[1]}});
        content = result.text;
      } else if (/\.(txt|md|json)$/i.test(file.name)) content = await readFile(file);
      else throw new Error("Choose a PDF, TXT, Markdown or JSON file");
      if (K.form !== form || !$("#kb-title") && !$("#kb-file-status")) return;
      if (/\.json$/i.test(file.name)) {
        const batch = JSON.parse(content);
        const check = await api("/api/validate",{body:{evidence:batch}});
        if (!check.evidence?.ok) throw new Error(check.evidence?.error || "Invalid evidence JSON");
        form.batch = batch;
      } else { form.batch = null; form.text = content; form.title ||= file.name.replace(/\.[^.]+$/,""); form.source ||= file.name; }
      form.filename = file.name; showDocumentForm();
    } catch(e) { if (K.form === form && $("#kb-file-status")) $("#kb-file-status").textContent = e.message; }
  }
  Object.assign(actions, {
    "agent-profile": (el) => {
      const r=el.dataset.r;
      const detail={A:"Assesses anticoagulation benefit, treatment stage and duration.",B:"Checks drug eligibility, dose-related factors and interactions.",C:"Assesses bleeding risk, patient constraints and monitoring.",D:"Combines specialist findings and revises the draft. Affected specialists review the changes."}[r];
      openDrawer(`<div class="dh"><h3 style="flex:1;margin:0">Agent ${r}</h3><button class="btn ghost sm" data-action="close-drawer" aria-label="Close">${icon("x")}</button></div><div class="db"><img src="/static/agent-${r.toLowerCase()}.svg" alt="Agent ${r} in a white coat" class="profile-robot"><h2>${ROLE[r].short}</h2><p class="lead">${detail}</p></div>`);
    },
    "kb-add": () => { K.form={title:"",source:"",version:"",text:"",roles:[...ROLES],synthetic:false,batch:null,filename:""}; showDocumentForm(); },
    "kb-search": searchKnowledge,
    "kb-view": (el) => { K.archived=el.dataset.mode==="archived"; K.selected.clear(); viewKnowledge(); },
    "kb-detail": async (el) => { try { const route=routeVersion, d=await api(`/api/knowledge/${encodeURIComponent(el.dataset.id)}`); if(route!==routeVersion) return; openDrawer(`<div class="dh"><div style="flex:1"><h3 style="margin:0">${esc(d.title)}</h3><span class="muted small">${esc(d.version)} · Passages: ${d.chunks.length}</span></div><button class="btn ghost sm" data-action="close-drawer" aria-label="Close">${icon("x")}</button></div><div class="db stack"><div class="small muted">${esc(d.source)}</div><div class="row">${d.roles.map(r=>roleTag(r)).join("")}${d.synthetic ? badge("Synthetic","warn") : ""}</div><div class="quote">${esc(d.text)}</div></div>`); } catch(e){toast(e.message,"bad");} },
    "kb-archive": async (el) => { el.disabled=true; try {await api(`/api/knowledge/${encodeURIComponent(el.dataset.id)}/archive`,{body:{archived:el.dataset.value==="true"}}); K.selected.delete(el.dataset.id); await viewKnowledge(); toast(el.dataset.value==="true" ? "Document archived. Restore it from Archived." : "Document restored","ok");}catch(e){el.disabled=false;toast(e.message,"bad");} },
    "kb-save": async (el) => {
      const f=K.form, docs=f.batch || [{title:f.title,source:f.source,version:f.version,text:f.text,roles:f.roles,synthetic:f.synthetic}];
      el.disabled=true; $("#kb-form-error").textContent="";
      try {const out=await api("/api/knowledge",{body:{documents:docs}}); closeDrawer(); K.form=null; K.archived=false; await viewKnowledge(); toast(`${out.created} added · ${out.duplicates} already in library${out.restored ? ` · ${out.restored} restored` : ""}`,"ok");}
      catch(e){el.disabled=false;if($("#kb-form-error")) $("#kb-form-error").textContent=e.message;}
    },
    "kb-use": async (el) => {
      el.disabled=true;
      try { const ids=[...K.selected], data=await api("/api/knowledge/snapshot",{body:{ids}}), checked=await api("/api/validate",{body:{evidence:data.evidence}});
        if (!checked.evidence?.ok) throw new Error("Selected evidence is invalid");
        S.w.evidence=data.evidence; S.w.evidenceName=`Knowledge base · Documents: ${ids.length}`; S.w.evidenceCheck=checked.evidence; S.w.knowledgeIds=ids; S.w.useDemoData=false; S.w.step=1; S.w.settings ||= defaultsToSettings(); saveWizard(); location.hash="#/new"; toast("Knowledge documents attached to review","ok");
      }catch(e){el.disabled=false;toast(e.message,"bad");}
    }
  });

  const inputs = {
    "kb-q": (el) => { K.q=el.value; },
    "kb-field": (el) => { K.form[el.dataset.k]=el.value; },
    "hist-q": (el) => { S.hist.q = el.value; $("#hist-body").innerHTML = runRows(filterRuns()); },
    case: (el) => { delete S.w.jsonDraft; S.w.case[el.dataset.k] = el.value; saveWizard(); refreshCaseSide(); },
    "fact-k": (el) => { delete S.w.jsonDraft; S.w.case.facts[+el.dataset.i][0] = el.value; saveWizard(); refreshCaseSide(); },
    "fact-v": (el) => { delete S.w.jsonDraft; S.w.case.facts[+el.dataset.i][1] = el.value; saveWizard(); refreshCaseSide(); },
    "case-json": (el) => {
      const err = $("#json-err");
      S.w.jsonDraft = el.value;
      try {
        const o = JSON.parse(el.value);
        if (!o || typeof o !== "object" || Array.isArray(o)) throw new Error("Expected a JSON object");
        S.w.case = caseFromJSON(o); S.w.jsonError = false; saveWizard(); refreshCaseSide();
        err.textContent = "Valid JSON. Form updated."; err.style.color = "var(--ok)";
      } catch (e) { S.w.jsonError = true; saveWizard(); refreshCaseSide(); err.textContent = `JSON error: ${e.message}`; err.style.color = "var(--bad)"; }
    },
    pace: (el) => { S.w.pace = +el.value; $("#pace-v").textContent = S.w.pace.toFixed(1); saveWizard(); },
    setting: (el) => { S.w.settings[el.dataset.k] = el.value; saveWizard(); refreshStartChecks(); },
    llm: (el) => { S.w.llm[el.dataset.k] = el.value.trim(); saveWizard(); refreshStartChecks(); },
    "llm-role": (el) => { S.w.llm.role_models = S.w.llm.role_models || {}; S.w.llm.role_models[el.dataset.r] = el.value.trim(); saveWizard(); },
    apikey: (el) => { apiKey = el.value.trim(); refreshStartChecks(); },
  };
  function refreshStartChecks() {
    const btn = $("[data-action=start]"); if (!btn) return;
    const { items, ok } = startChecks();
    const list = btn.previousElementSibling; if (list) list.outerHTML = checkList(items);
    btn.disabled = !ok;
  }
  const changes = {
    "kb-file": (el) => importKnowledgeFile(el.files[0]),
    "kb-synthetic": (el) => { K.form.synthetic=el.checked; },
    "kb-form-role": (el) => { K.form.roles=el.checked ? [...new Set([...K.form.roles,el.dataset.r])] : K.form.roles.filter(r=>r!==el.dataset.r); },
    "kb-role": (el) => { K.role=el.value; if(K.q.trim()) searchKnowledge(); else renderKnowledge(); },
    "kb-select": (el) => { if(el.checked) K.selected.add(el.dataset.id); else K.selected.delete(el.dataset.id); $$("[data-change=kb-select]").forEach(input=>input.checked=K.selected.has(input.dataset.id)); $("#kb-selected-count").textContent=`${K.selected.size} selected`; $("#kb-use").disabled=!K.selected.size; },
    "case-file": async (el) => {
      const f = el.files[0]; if (!f) return;
      try { const o = JSON.parse(await readFile(f)); S.w.case = caseFromJSON(o); S.w.sources=[];S.w.labels=[];S.w.extractionIssues=[];await hydrateCaseSources();delete S.w.jsonDraft; S.w.jsonError = false; S.w.useDemoData = false; saveWizard(); renderWizard(); toast("Case imported", "ok"); }
      catch (e) { toast(`Unable to read case: ${e.message}`, "bad"); }
    },
    "evidence-file": (el) => importEvidenceFile(el.files[0]),
    "use-demo": (el) => { S.w.useDemoData = el.checked; saveWizard(); renderWizard(); },
  };

  /* ================= longitudinal workspace ================= */
  const connection = () => ({...S.w.llm, api_key:apiKey, api_style:S.w.llm.api_style || S.info?.env?.api_style || "chat_completions"});
  const extraCase = () => (S.w.case.extra ||= {});
  const utcNow = () => new Date().toISOString();
  function apiStyleHTML(){const style=S.w.llm.api_style||S.info?.env?.api_style||"chat_completions";return `<div class="field"><label>API protocol</label><select class="select" data-change="api-style"><option value="chat_completions" ${style==='chat_completions'?'selected':''}>Chat Completions</option><option value="responses" ${style==='responses'?'selected':''}>Responses</option></select><span class="hint">Choose the protocol supported by your model endpoint, including tool calls and image inputs.</span></div>`;}
  function workspaceAuditHTML(d){const r=d.result;return `<section class="card"><div class="card-h"><h3>${icon("shield")}Clinical context & tools</h3><span class="muted small">${r?.metrics?.tool_calls||0} tool calls · ${r?.metrics?.model_requests||0} completed model requests</span></div><div class="card-b"><details class="ev"><summary>Clinical checklist and calculations</summary><pre class="json">${jsonHTML(r?.clinical_checks||{})}</pre></details><details class="ev"><summary>Frozen patient memory</summary><pre class="json">${jsonHTML(r?.memory_snapshot||{})}</pre></details><details class="ev"><summary>Proposed memory updates</summary><pre class="json">${jsonHTML(d.memory_updates||r?.memory_proposals||[])}</pre></details></div></section><section class="card"><div class="card-h"><h3>${icon("lock")}Research labels · excluded from model inputs</h3><button class="btn sm" data-action="run-label-add">Add label</button></div><div class="card-b">${labelsHTML(d.research_labels||[])}</div></section>`;}
  function patientContextHTML() {
    const e=extraCase(), p=e.patient || {};
    return `<div class="context-box"><div class="row"><b>${icon("users")}Decision context</b><a href="#/patients" class="btn ghost sm">Patient timeline${icon("chevron")}</a></div>
      <div class="grid g-2"><div class="field"><label>Patient ID</label><input class="input" data-input="patient-context" data-k="patient_id" value="${esc(p.patient_id)}" placeholder="DEID-P001"></div><div class="field"><label>Encounter ID</label><input class="input" data-input="patient-context" data-k="encounter_id" value="${esc(p.encounter_id)}" placeholder="VISIT-001"></div></div>
      <div class="field"><label>Decision time (ISO + timezone)</label><input class="input" data-input="patient-context" data-k="decision_at" value="${esc(p.decision_at)}" placeholder="2026-10-04T09:00:00+08:00"></div>
      <div class="field"><label>Task</label><select class="select" data-change="task-type"><option value="generate_plan" ${e.task_type!=="review_plan"?"selected":""}>Generate an independent plan</option><option value="review_plan" ${e.task_type==="review_plan"?"selected":""}>Review an existing prescription</option></select></div>
      ${e.task_type==="review_plan"?`<div class="field"><label>Plan to review (model input)</label><textarea class="textarea" data-input="candidate-plan">${esc(e.candidate_plan)}</textarea></div>`:""}
      <button class="btn sm" data-action="case-memory">${icon("clock")}Preview memory at this time</button></div>`;
  }
  function intakeHTML() {
    const e=extraCase(), rows=e.observations || [], sources=(S.w.sources || []).filter(s=>(e.source_ids||[]).includes(s.id));
    const input=(i,k,v,placeholder="")=>`<input class="input" data-input="observation" data-i="${i}" data-k="${k}" value="${esc(v)}" placeholder="${placeholder}">`;
    return `<section class="card" style="margin-top:20px"><div class="card-h"><h3>${icon("upload")}Source documents & images</h3><label class="btn sm" tabindex="0" role="button">${icon("plus")}Add files<input type="file" accept=".docx,.png,.jpg,.jpeg,.webp,.txt,.md" data-change="source-upload" multiple hidden></label></div>
      <div class="card-b stack"><p class="muted small" style="margin:0">Word, report screenshots or text · 6 MB per file. Select records available at the decision time. Keep future outcomes and held-out physician plans in Research labels.</p>
      ${sources.map(s=>`<div class="source-row"><div><b>${esc(s.name)}</b><div class="small muted">${esc(s.id)} · ${s.images?.length || (s.mime.startsWith("image/")?1:0)} images</div><div class="source-thumbs">${(s.mime.startsWith("image/")?[s.id]:(s.images||[])).map(id=>`<button class="source-thumb" data-action="source-open" data-id="${esc(id)}" title="View source"><img src="/api/sources/${encodeURIComponent(id)}/image" alt="Uploaded report"></button>`).join("")}</div></div>
        <div class="stack"><input class="input" aria-label="Source available time" data-input="source-context" data-id="${esc(s.id)}" data-k="available_at" value="${esc(e.source_context?.[s.id]?.available_at)}" placeholder="Source available at (ISO + timezone)"><input class="input" aria-label="Source reviewer" data-input="source-context" data-id="${esc(s.id)}" data-k="reviewer" value="${esc(e.source_context?.[s.id]?.reviewer)}" placeholder="Verified by (whole source fits this decision time)"></div><button class="btn ghost sm" data-action="source-remove" data-id="${esc(s.id)}" title="Detach source">${icon("x")}</button></div>`).join("")}
      <div class="row wrap"><button class="btn" data-action="source-extract" ${e.source_ids?.length?"":"disabled"}>${icon("sparkles")}Extract with model</button><button class="btn ghost" data-action="obs-add">${icon("plus")}Add sourced observation</button><a class="btn ghost" href="#/settings">Model settings</a></div><span class="hint">Extraction uses your configured model service. Confirm each reading and date before review. Raw CT interpretation is not supported.</span>
      ${S.w.extractionIssues?.length?`<div class="notice warn">${icon("info")}<div>${S.w.extractionIssues.map(esc).join("<br>")}</div></div>`:""}
      <div class="observation-list">${rows.map((o,i)=>`<div class="observation-card"><div class="row"><b>Observation ${i+1}</b><span class="spacer"></span><select class="select" data-change="observation-status" data-i="${i}">${["unverified","confirmed","excluded"].map(s=>`<option value="${s}" ${o.status===s?"selected":""}>${s}</option>`).join("")}</select><button class="btn ghost sm" data-action="obs-remove" data-i="${i}" title="Remove observation">${icon("x")}</button></div>
        <div class="grid g-3"><div class="field"><label>Field</label>${input(i,"key",o.key,"serum_creatinine")}</div><div class="field"><label>Value</label>${input(i,"value",typeof o.value==="object"?JSON.stringify(o.value):o.value,"null if unreadable")}</div><div class="field"><label>Unit</label>${input(i,"unit",o.unit,"umol/L")}</div></div>
        <div class="grid g-2"><div class="field"><label>Clinical date</label>${input(i,"observed_at",o.observed_at,"ISO + timezone")}</div><div class="field"><label>Known by</label>${input(i,"available_at",o.available_at,"ISO + timezone")}</div><div class="field"><label>Source ID</label>${input(i,"source_id",o.source_id,"SRC-…")}</div><div class="field"><label>Location in source</label>${input(i,"location",o.location,"Page / row / image region")}</div></div></div>`).join("")}</div>
      <div class="row"><button class="btn primary" data-action="clinical-check">${icon("shield")}Check clinical data</button></div><div id="clinical-result"></div></div></section>
      <section class="card" style="margin-top:20px"><div class="card-h"><h3>${icon("lock")}Research labels</h3><button class="btn sm" data-action="label-add">${icon("plus")}Add label</button></div><div class="card-b"><p class="small muted">Stored separately from model inputs: physician plan, expert audit or outcome.</p>${labelsHTML(S.w.labels || [],true)}</div></section>`;
  }
  function labelsHTML(labels,editable=false){return labels.length?labels.map((v,i)=>`<div class="memory-entry"><div class="row"><b>${esc(v.kind)}</b><span class="muted small">${esc(v.occurred_at)}</span>${editable?`<button class="btn ghost sm" data-action="label-remove" data-i="${i}">${icon("x")}</button>`:""}</div><p>${esc(v.content)}</p><div class="small muted">${esc(v.source)} · ${esc(v.recorded_by)}</div></div>`).join(""):'<span class="muted small">No labels added.</span>';}
  function showLabelForm(runId="") {
    openDrawer(`<div class="dh"><h3>Add research label</h3><button class="btn ghost sm" data-action="close-drawer">${icon("x")}</button></div><div class="db stack"><div class="field"><label>Type</label><select class="select" id="label-kind"><option value="physician_plan">Physician plan</option><option value="expert_audit">Expert audit</option><option value="outcome">Outcome</option></select></div><div class="field"><label>Content</label><textarea class="textarea" id="label-content"></textarea></div><div class="field"><label>Clinical date (ISO + timezone)</label><input class="input" id="label-date" value="${esc(extraCase().patient?.decision_at || "")}"></div><div class="field"><label>Source</label><input class="input" id="label-source"></div><div class="field"><label>Recorded by</label><input class="input" id="label-actor"></div><button class="btn primary" data-action="label-save" data-run="${esc(runId)}">Save separately</button></div>`);
  }
  async function viewPatients(selected="") {
    const route=routeVersion, data=await api("/api/patients"); if(route!==routeVersion)return;
    setView(`<div class="page-h"><div><h1 class="h1">Patient timeline</h1><p class="lead">Sourced history, treatment and preferences across encounters.</p></div></div><div class="grid g-side"><div class="stack"><div class="card"><div class="card-b row"><input class="input" id="patient-lookup" value="${esc(selected)}" placeholder="De-identified patient ID"><button class="btn primary" data-action="patient-load">Open</button></div></div><div id="patient-detail"></div></div><aside class="card"><div class="card-h"><h3>Patients</h3></div><div class="card-b stack">${data.patients.map(p=>`<button class="btn" data-action="patient-select" data-id="${esc(p.patient_id)}">${icon("user")}${esc(p.patient_id)}<span class="spacer"></span><span class="muted small">${p.entries} records</span></button>`).join("") || '<p class="muted small">Open a patient ID to add the first record.</p>'}</div></aside></div>`,crumb("Patients"));
    if(selected)await loadPatient(selected);
  }
  async function loadPatient(id) {
    const data=await api(`/api/patients/${encodeURIComponent(id)}`); S.patient=id;
    const node=$("#patient-detail"); if(!node)return;
    node.innerHTML=`<div class="card"><div class="card-h"><h3>${icon("user")}${esc(id)}</h3><button class="btn sm" data-action="memory-add">${icon("plus")}Add record</button></div><div class="card-b stack"><span class="small muted">Model suggestions require review and remain distinct from confirmed clinical facts. Corrections append a new record.</span>${data.entries.slice().reverse().map(v=>`<div class="memory-entry"><div class="row wrap">${badge(v.kind,"gray")}${badge(v.resolution?.action || v.status,v.status==="confirmed"?"ok":"warn")}<b>${esc(v.topic)}</b></div><p>${esc(v.content)}</p><div class="small muted">Clinical: ${esc(v.occurred_at)}<br>Available: ${esc(v.available_at)}<br>${esc(v.source)} · ${esc(v.actor)}${v.supersedes?'<br>Corrects '+esc(v.supersedes):''}</div>${v.status==="proposed"&&!v.resolution?`<div class="row" style="margin-top:10px"><button class="btn sm" data-action="memory-resolve" data-id="${esc(v.id)}" data-result="accept">Accept suggestion</button><button class="btn ghost sm" data-action="memory-resolve" data-id="${esc(v.id)}" data-result="reject">Reject</button></div>`:`<button class="btn ghost sm" data-action="memory-correct" data-id="${esc(v.id)}">Add correction / verified record</button>`}</div>`).join("") || '<div class="empty">No records yet</div>'}</div></div>`;
  }
  function memoryForm(supersedes="") {
    openDrawer(`<div class="dh"><h3>Add patient record</h3><button class="btn ghost sm" data-action="close-drawer">${icon("x")}</button></div><div class="db stack"><div class="field"><label>Record type</label><select class="select" id="mem-kind"><option value="fact">Clinical fact / measurement</option><option value="preference">Preference / execution constraint</option><option value="clinician_decision">Physician decision</option><option value="actual_treatment">Treatment actually received</option></select></div><div class="field"><label>Topic</label><input class="input" id="mem-topic" placeholder="Medication / renal function / bleeding…"></div><div class="field"><label>Content</label><textarea class="textarea" id="mem-content"></textarea></div><div class="grid g-2"><div class="field"><label>Clinical date</label><input class="input" id="mem-occurred" placeholder="ISO + timezone"></div><div class="field"><label>Known by</label><input class="input" id="mem-available" placeholder="ISO + timezone"></div></div><div class="field"><label>Encounter ID</label><input class="input" id="mem-encounter"></div><div class="field"><label>Source</label><input class="input" id="mem-source"></div><div class="field"><label>Recorded / verified by</label><input class="input" id="mem-actor"></div><div class="field"><label>Corrects record (optional)</label><input class="input" id="mem-supersedes" value="${esc(supersedes)}"></div><span class="small muted">Use the actual historical dates. New entries preserve earlier records.</span><button class="btn primary" data-action="memory-save">Save confirmed record</button></div>`);
  }
  Object.assign(actions, {
    "case-clinical":async()=>{try{const d=await api("/api/demo/clinical");S.w.case=caseFromJSON(d.case);S.w.sources=[];S.w.labels=[];S.w.extractionIssues=[];S.w.jsonError=false;delete S.w.jsonDraft;S.w.useDemoData=false;saveWizard();renderWizard();toast("Fictitious clinical example loaded","ok");}catch(e){toast(e.message,"bad");}},
    "case-memory":async()=>{try{const p=extraCase().patient||{};const data=await api(`/api/patients/${encodeURIComponent(p.patient_id||"")}/snapshot`,{body:{as_of:p.decision_at,encounter_id:p.encounter_id,task_type:extraCase().task_type||"generate_plan"}});openDrawer(`<div class="dh"><h3>Memory at decision time</h3><button class="btn ghost sm" data-action="close-drawer">${icon("x")}</button></div><div class="db"><pre class="json">${jsonHTML(data)}</pre></div>`);}catch(e){toast(e.message,"bad");}},
    "source-open":el=>openDrawer(`<div class="dh"><h3>Original source</h3><button class="btn ghost sm" data-action="close-drawer">${icon("x")}</button></div><div class="db"><p class="mono small">${esc(el.dataset.id)}</p><img class="source-full" src="/api/sources/${encodeURIComponent(el.dataset.id)}/image" alt="Original source image"></div>`),
    "source-remove":el=>{const id=el.dataset.id,e=extraCase(),src=(S.w.sources||[]).find(s=>s.id===id);e.source_ids=(e.source_ids||[]).filter(i=>i!==id);delete e.source_context?.[id];S.w.sources=(S.w.sources||[]).filter(s=>s.id!==id);e.observations=(e.observations||[]).filter(o=>o.source_id!==id&&!src?.images?.includes(o.source_id));saveWizard();renderWizard();},
    "source-extract":async el=>{el.disabled=true;el.textContent="Extracting…";try{const data=await api("/api/intake/extract",{body:{source_ids:extraCase().source_ids,llm:connection()}});extraCase().observations=[...(extraCase().observations||[]),...data.output.observations];S.w.extractionIssues=data.output.issues;saveWizard();if(location.hash.startsWith("#/new"))renderWizard();toast("Extraction ready for verification","ok");}catch(e){toast(e.message,"bad");el.disabled=false;el.textContent="Extract with model";}},
    "obs-add":()=>{const e=extraCase();(e.observations||=[]).push({key:"",value:null,unit:"",observed_at:"",available_at:"",source_id:e.source_ids?.[0]||"",location:"",status:"unverified"});saveWizard();renderWizard();},
    "obs-remove":el=>{extraCase().observations.splice(+el.dataset.i,1);saveWizard();renderWizard();},
    "clinical-check":async el=>{el.disabled=true;try{const c=await api("/api/clinical/check",{body:{case:buildCase()}});$("#clinical-result").innerHTML=`<div class="notice ${c.blocking?'warn':'info'}">${icon("shield")}<div>${c.input_blocked?'Verify source records before model review.':c.blocking?'Review can assess available facts; dependent decisions need more information.':'Core checks complete; specialist assessment still applies.'}</div></div>${checkList(c.issues.map(i=>[i.severity==='blocking'?'warn':'info',i.roles.join('/')+': '+i.message]))}<details class="ev"><summary>Checklist and calculations</summary><pre class="json">${jsonHTML(c)}</pre></details>`;}catch(e){toast(e.message,"bad");}finally{el.disabled=false;}},
    "label-add":()=>showLabelForm(),"run-label-add":()=>showLabelForm(S.run.id),
    "label-remove":el=>{S.w.labels.splice(+el.dataset.i,1);saveWizard();renderWizard();},
    "label-save":async el=>{try{const value={kind:$("#label-kind").value,content:$("#label-content").value,occurred_at:$("#label-date").value,source:$("#label-source").value,recorded_by:$("#label-actor").value};if(!value.content.trim()||!value.source.trim()||!value.recorded_by.trim()||!Number.isFinite(Date.parse(value.occurred_at)))throw Error("Complete all label fields with an ISO date and timezone");if(el.dataset.run){await api(`/api/runs/${encodeURIComponent(el.dataset.run)}/labels`,{body:{labels:[value]}});S.run=await api(`/api/runs/${encodeURIComponent(el.dataset.run)}`);renderRunBody();}else{(S.w.labels||=[]).push(value);saveWizard();renderWizard();}closeDrawer();toast("Label saved outside model context","ok");}catch(e){toast(e.message,"bad");}},
    "patient-load":()=>loadPatient($("#patient-lookup").value.trim()).catch(e=>toast(e.message,"bad")),
    "patient-select":el=>{ $("#patient-lookup").value=el.dataset.id;loadPatient(el.dataset.id).catch(e=>toast(e.message,"bad"));},
    "memory-add":()=>memoryForm(),"memory-correct":el=>memoryForm(el.dataset.id),
    "memory-save":async()=>{try{const entry={kind:$("#mem-kind").value,topic:$("#mem-topic").value,content:$("#mem-content").value,occurred_at:$("#mem-occurred").value,available_at:$("#mem-available").value,source:$("#mem-source").value,roles:["A","B","C","D"]};if($("#mem-encounter").value)entry.encounter_id=$("#mem-encounter").value;if($("#mem-supersedes").value)entry.supersedes=$("#mem-supersedes").value;await api(`/api/patients/${encodeURIComponent(S.patient)}/entries`,{body:{entry,actor:$("#mem-actor").value}});closeDrawer();await viewPatients(S.patient);toast("Patient record saved","ok");}catch(e){toast(e.message,"bad");}},
    "memory-resolve":el=>{S.pendingResolution={entry_id:el.dataset.id,action:el.dataset.result};openDrawer(`<div class="dh"><h3>Review memory suggestion</h3><button class="btn ghost sm" data-action="close-drawer">${icon("x")}</button></div><div class="db stack"><p>Accepting retains this as a reviewed model suggestion. Add a separately sourced clinical record to confirm a fact.</p><div class="field"><label>Reviewer</label><input class="input" id="resolution-actor"></div><div class="field"><label>Note</label><textarea class="textarea" id="resolution-note"></textarea></div><button class="btn primary" data-action="memory-resolve-save">${esc(el.dataset.result)} suggestion</button></div>`);},
    "memory-resolve-save":async()=>{try{await api(`/api/patients/${encodeURIComponent(S.patient)}/resolve`,{body:{...S.pendingResolution,actor:$("#resolution-actor").value,note:$("#resolution-note").value}});closeDrawer();await loadPatient(S.patient);}catch(e){toast(e.message,"bad");}},
  });
  Object.assign(inputs,{
    "patient-context":el=>{const e=extraCase();(e.patient||={patient_id:"",encounter_id:"",decision_at:""})[el.dataset.k]=el.value.trim();saveWizard();refreshCaseSide();},
    "candidate-plan":el=>{extraCase().candidate_plan=el.value;saveWizard();},
    "observation":el=>{extraCase().observations[+el.dataset.i][el.dataset.k]=el.dataset.k==='value'?(el.value.trim()==='null'?null:parseVal(el.value)):el.value;saveWizard();},
    "source-context":el=>{const e=extraCase();e.source_context||={};(e.source_context[el.dataset.id]||={available_at:"",reviewer:""})[el.dataset.k]=el.value;saveWizard();},
  });
  Object.assign(changes,{
    "task-type":el=>{extraCase().task_type=el.value;if(el.value!=="review_plan")delete extraCase().candidate_plan;saveWizard();renderWizard();},
    "observation-status":el=>{extraCase().observations[+el.dataset.i].status=el.value;saveWizard();},
    "api-style":el=>{S.w.llm.api_style=el.value;saveWizard();},
    "source-upload":async el=>{try{for(const file of el.files){if(file.size>6*1024*1024)throw Error("File exceeds 6 MB");const encoded=await new Promise((resolve,reject)=>{const r=new FileReader();r.onload=()=>resolve(String(r.result).split(',')[1]);r.onerror=reject;r.readAsDataURL(file);});const source=await api("/api/sources",{body:{filename:file.name,content_base64:encoded}});S.w.sources||=[];if(!S.w.sources.some(s=>s.id===source.id))S.w.sources.push(source);const e=extraCase();e.source_ids=[...new Set([...(e.source_ids||[]),source.id])];e.source_context||={};e.source_context[source.id]||={available_at:"",reviewer:""};saveWizard();}renderWizard();toast("Sources uploaded locally","ok");}catch(e){toast(e.message,"bad");}},
  });

  document.addEventListener("click", (e) => {
    const el = e.target.closest("[data-action]");
    if (!el || el.disabled) return;
    const fn = actions[el.dataset.action];
    if (fn) { e.preventDefault(); fn(el, e); }
  });
  document.addEventListener("input", (e) => { const el = e.target.closest("[data-input]"); if (el) inputs[el.dataset.input]?.(el, e); });
  document.addEventListener("change", (e) => { const el = e.target.closest("[data-change]"); if (el) changes[el.dataset.change]?.(el, e); });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeDrawer();
    const t = e.target;
    if (e.key === "Tab" && $("#drawer").classList.contains("on")) {
      const nodes = $$("button,a[href],input,textarea,select,[tabindex='0']", $("#drawer"));
      if (!nodes.length) { e.preventDefault(); return; }
      if (e.shiftKey && t === nodes[0]) { e.preventDefault(); nodes.at(-1).focus(); }
      else if (!e.shiftKey && t === nodes.at(-1)) { e.preventDefault(); nodes[0].focus(); }
    }
    if (e.key === "Enter" && !e.isComposing && t.dataset?.key === "kb-search") { e.preventDefault(); searchKnowledge(); }
    if (e.key === "Enter" && !e.isComposing && t.dataset?.key === "global-search") {
      S.hist.q = t.value; S.hist.f = "all";
      if (location.hash === "#/history") viewHistory(); else location.hash = "#/history";
    }
    if ((e.key === "Enter" || e.key === " ") && t.matches("label[role=button]")) { e.preventDefault(); $("input[type=file]", t)?.click(); }
    if ((e.key === "Enter" || e.key === " ") && t.matches("tr[data-action]")) { e.preventDefault(); actions[t.dataset.action]?.(t); }
    if (t.dataset?.key === "miss-add") {
      if (e.key === "Enter" && !e.isComposing) {
        e.preventDefault();
        const v = t.value.trim();
        if (v && !S.w.case.missing.includes(v)) S.w.case.missing.push(v);
        saveWizard(); renderWizard(); $("[data-key=miss-add]")?.focus();
      } else if (e.key === "Backspace" && !t.value && S.w.case.missing.length) {
        S.w.case.missing.pop(); saveWizard(); renderWizard(); $("[data-key=miss-add]")?.focus();
      }
    }
  });
  document.addEventListener("dragover", (e) => { const z = e.target.closest?.(".dropzone"); if (z || e.dataTransfer?.types?.includes("Files")) e.preventDefault(); if (z) z.classList.add("over"); });
  document.addEventListener("dragleave", (e) => { e.target.closest?.(".dropzone")?.classList.remove("over"); });
  document.addEventListener("drop", (e) => {
    e.preventDefault();
    const z = e.target.closest?.(".dropzone");
    if (z) {
      z.classList.remove("over");
      if ($("[data-change=kb-file]", z)) importKnowledgeFile(e.dataTransfer.files[0]);
      else importEvidenceFile(e.dataTransfer.files[0]);
    }
  });
  $("#drawer-mask").addEventListener("click", closeDrawer);
  window.addEventListener("resize", () => { if (S.runTab === "live") drawWires(); });

  /* ================= router & boot ================= */
  function onRoute() {
    routeVersion++;
    cleanup.forEach((f) => f()); cleanup = [];
    closeDrawer();
    const h = location.hash.replace(/^#/, "") || "/";
    const [path, query] = h.split("?");
    const parts = path.split("/").filter(Boolean);
    const nav = parts[0] === "run" ? "history" : parts[0] || "dashboard";
    $$(".nav a").forEach((a) => (a.classList.toggle("active", a.dataset.nav === nav), a.dataset.nav === nav ? a.setAttribute("aria-current", "page") : a.removeAttribute("aria-current")));
    $("#view").scrollTop = 0;
    if (!parts.length) return viewDashboard();
    if (parts[0] === "new") return viewNew();
    if (parts[0] === "history") return viewHistory();
    if (parts[0] === "knowledge") return viewKnowledge();
    if (parts[0] === "patients") return viewPatients();
    if (parts[0] === "settings") return viewSettings();
    if (parts[0] === "guide") return viewGuide();
    if (parts[0] === "run" && parts[1]) return viewRun(decodeURIComponent(parts[1]), new URLSearchParams(query || "").get("tab"));
    location.hash = "#/";
  }
  async function heartbeat() {
    try { await fetch("/api/info", { cache: "no-store" }).then((r) => { if (!r.ok) throw 0; }); $("#server-state").classList.remove("off"); $("#server-state").lastChild.textContent = "Local service online"; }
    catch { $("#server-state").classList.add("off"); $("#server-state").lastChild.textContent = "Local service offline"; }
  }
  async function boot() {
    $$("i[data-icon]").forEach((i) => { i.outerHTML = icon(i.dataset.icon); });
    try { S.info = await api("/api/info"); $("#app-version").textContent = `v${S.info.version} · Prompt ${S.info.prompt_version}`; }
    catch (e) { toast("Unable to connect: " + e.message, "bad"); }
    S.w = loadWizard();
    window.addEventListener("hashchange", onRoute);
    onRoute();
    setInterval(heartbeat, 10000);
  }
  boot();
})();
