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
    A: { name: "抗凝获益与疗程", short: "疗程专家" },
    B: { name: "药物适用性与用药安全", short: "药学专家" },
    C: { name: "出血风险与患者约束", short: "出血风险专家" },
    D: { name: "整合草案与定向修订", short: "协调员" },
  };
  const STATUS = {
    approved: { t: "审核通过", c: "ok" }, needs_human_review: { t: "需人工复核", c: "warn" },
    failed: { t: "运行失败", c: "bad" }, running: { t: "进行中", c: "run" }, interrupted: { t: "已中断", c: "gray" },
  };
  const TASK = { assess: "独立初判", synthesize: "汇总草案", review: "审核", revise: "定向修订" };
  const TASK_SHORT = { assess: "初判", synthesize: "汇总", review: "审核", revise: "修订" };
  const VERDICT = { approve: { t: "通过", c: "ok" }, revise: { t: "需修改", c: "warn" }, needs_information: { t: "需补充信息", c: "bad" } };
  const DECISION = { accept: { t: "采纳", c: "ok", i: "check" }, accept_with_changes: { t: "修改后采纳", c: "warn", i: "pen" }, reject: { t: "不采纳", c: "bad", i: "x" } };
  const QUICK = ["年龄", "性别", "体重", "VTE 类型与部位", "确诊时间", "血肌酐", "eGFR / CrCl", "血小板", "肝功能", "出血史", "合并用药", "妊娠 / 哺乳", "活动性肿瘤", "近期手术计划"];

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
  const fmtTime = (iso) => { if (!iso) return "—"; const d = new Date(iso); return isNaN(d) ? iso : d.toLocaleString("zh-CN", { hour12: false, year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" }); };
  const fmtSec = (s) => (s == null ? "—" : s < 60 ? `${Number(s).toFixed(1)} 秒` : `${Math.floor(s / 60)} 分 ${Math.round(s % 60)} 秒`);
  const badge = (t, c, extra = "") => `<span class="badge ${c} ${extra}">${esc(t)}</span>`;
  const statusBadge = (s) => { const x = STATUS[s] || { t: s || "未知", c: "gray" }; return badge(x.t, x.c); };
  const roleTag = (r, size) => `<span class="role-tag ${r}"${size ? ` style="width:${size}px;height:${size}px;font-size:${Math.round(size * .48)}px;border-radius:${Math.round(size / 3.4)}px"` : ""}>${r}</span>`;
  const crumb = (...xs) => [`<span>VTE Review</span>`, ...xs.map((x, i) => (i === xs.length - 1 ? `<b>${esc(x)}</b>` : `<span>${esc(x)}</span>`))].join(`<span class="sep">/</span>`);
  const fmtVal = (v) => (typeof v === "boolean" ? (v ? "是" : "否") : typeof v === "string" ? v : JSON.stringify(v));
  function reasonText(r) {
    if (!r) return "";
    const map = {
      all_required_reviews_passed: "全部专家已审核通过当前草案",
      missing_information: "有专家判定需补充患者资料或外部证据后才能继续",
      revision_limit: "已达到最大修订次数，仍有专家未通过",
      no_change_after_revision: "协调员 D 修订后草案无实际变化，循环已停止",
    };
    if (map[r]) return map[r];
    if (r.startsWith("no_retrieved_evidence:")) return `证据库中未检索到以下角色的相关证据：${r.split(":")[1]}`;
    return `运行异常：${r}`;
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
  const loading = () => `<div class="empty"><div class="spinner" style="margin:0 auto 10px;width:22px;height:22px"></div>加载中…</div>`;
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
    for (const r of [...ROLES, "D"]) st.agents[r] = { state: "idle", label: "等待启动", note: "" };
    const open = {};
    const phase = (label, sub = "") => { const last = st.phases[st.phases.length - 1]; if (last && last.state === "active") last.state = "done"; st.phases.push({ label, sub, state: "active" }); };
    for (const e of events) {
      st.now = Math.max(st.now, e.elapsed_s || 0);
      if (e.event === "started") { st.started = e; phase("证据检索"); }
      else if (e.event === "call_started") {
        const c = { task: e.task, role: e.role, version: e.version, start: e.elapsed_s, end: null, status: "running" };
        st.calls.push(c); open[`${e.task}|${e.role}`] = c;
        st.agents[e.role] = { state: "working", label: `正在${TASK[e.task] || e.task}${e.task === "review" ? ` v${e.version}` : ""}…`, note: "" };
        const last = st.phases[st.phases.length - 1];
        if (e.task === "assess" && (!last || last.label !== "并行初判")) phase("并行初判", "A · B · C");
        if (e.task === "synthesize") phase("D 汇总草案");
        if (e.task === "revise") phase("D 定向修订");
      } else if (e.event === "call_completed" || e.event === "call_failed") {
        const c = open[`${e.task}|${e.role}`] || {};
        c.end = e.elapsed_s; c.status = e.event === "call_failed" ? "failed" : "done";
        c.output = e.output; c.duration = e.duration_s; c.usage = e.usage; c.model = e.model; c.error = e.error;
        const a = st.agents[e.role];
        if (e.event === "call_failed") { Object.assign(a, { state: "bad", label: "调用失败", note: e.error || "" }); const last = st.phases[st.phases.length - 1]; if (last) last.state = "fail"; }
        else if (e.task === "assess") Object.assign(a, { state: "ok", label: "独立初判完成", note: e.output?.summary || "" });
        else if (e.task === "review") {
          const v = e.output?.verdict;
          const n = e.output?.issues?.length || 0;
          st.approvals[e.role] = v === "approve" ? e.version : null;
          Object.assign(a, { state: v === "approve" ? "ok" : v === "revise" ? "warn" : "bad", label: v === "approve" ? `v${e.version} 审核通过` : v === "revise" ? `v${e.version} 需修改 · ${n} 个问题` : `需补充信息 · ${n} 个问题`, note: e.output?.note || "" });
        } else Object.assign(a, { state: "ok", label: e.task === "revise" ? "修订完成" : "草案已生成", note: e.output?.reason || "" });
      } else if (e.event === "draft_created") {
        st.version = e.version; st.drafts.push({ version: e.version, draft: e.draft, reason: "", roles: [...ROLES], initial: true });
        st.agents.D = { state: "ok", label: `已生成草案 v${e.version}`, note: "" };
      } else if (e.event === "draft_revised") {
        st.version = e.version; st.drafts.push({ version: e.version, draft: e.draft, reason: e.reason, roles: e.roles || [] });
        for (const r of e.roles || []) st.approvals[r] = null;
        st.agents.D = { state: "ok", label: `已修订至 v${e.version}`, note: e.reason || "" };
      } else if (e.event === "review_round") {
        st.rounds.push({ version: e.version, roles: e.roles });
        phase(`专家审核 v${e.version}`, (e.roles || []).join(" · "));
        for (const r of ROLES) if (!(e.roles || []).includes(r) && st.approvals[r] != null) st.agents[r] = { state: "ok", label: `保持通过（v${st.approvals[r]} 起未受影响）`, note: "本轮无需复核" };
      } else if (e.event === "finished") {
        st.finished = e;
        const last = st.phases[st.phases.length - 1];
        if (last && last.state === "active") last.state = e.status === "failed" ? "fail" : "done";
        st.phases.push({ label: e.status === "approved" ? "审核通过" : e.status === "failed" ? "运行失败" : "转人工复核", sub: "", state: e.status === "approved" ? "done" : e.status === "failed" ? "fail" : "stop" });
        if (st.agents.D.state === "idle" || st.agents.D.state === "working") st.agents.D = { state: e.status === "failed" ? "bad" : "ok", label: STATUS[e.status]?.t || e.status, note: "" };
      }
    }
    if (!st.finished) {
      if (!st.rounds.length) st.phases.push({ label: "专家审核", sub: "", state: "pending" });
      st.phases.push({ label: "输出结果", sub: "", state: "pending" });
    }
    return st;
  }

  /* ================= drawer ================= */
  function openDrawer(html) {
    drawerFocus = document.activeElement;
    const drawer = $("#drawer"); drawer.innerHTML = html; drawer.inert = false;
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
    if (!doc) return toast("未找到该证据条目", "bad");
    openDrawer(`<div class="dh"><div class="stat-ic" style="background:var(--brand-soft);color:var(--brand)">${icon("book")}</div>
      <div style="flex:1;min-width:0"><div class="muted small mono">${esc(doc.id)}</div><h3 style="margin:2px 0 0;font-size:16px">${esc(doc.title)}</h3></div>
      <button class="btn ghost sm" data-action="close-drawer" title="关闭">${icon("x")}</button></div>
      <div class="db stack">
        ${doc.synthetic ? `<div class="notice warn">${icon("flask")}<div>合成条目：仅用于测试流程，不是临床证据。</div></div>` : ""}
        <dl class="facts"><dt>来源</dt><dd>${esc(doc.source)}</dd><dt>版本</dt><dd>${esc(doc.version)}</dd>
        <dt>适用角色</dt><dd>${(doc.roles || []).map((r) => roleTag(r, 20)).join(" ")}</dd><dt>来源声明</dt><dd>${doc.synthetic ? "synthetic = true（合成）" : "synthetic = false（提供者声明，程序未验证）"}</dd></dl>
        <div><div class="muted small" style="margin-bottom:6px">原文片段</div><div class="quote">${esc(doc.text)}</div></div>
      </div>`);
  }

  /* ================= dashboard ================= */
  function runRows(runs) {
    if (!runs.length) return `<tr><td colspan="6"><div class="empty">${icon("folder")}<div>暂无审核记录</div></div></td></tr>`;
    return runs.map((r) => `<tr class="click" tabindex="0" role="link" aria-label="打开病例 ${esc(r.case_id || r.id)}" data-action="open-run" data-id="${esc(r.id)}">
      <td><div style="font-weight:600">${esc(r.case_id || "—")}</div><div class="muted small trunc">${esc(r.question || "")}</div></td>
      <td>${statusBadge(r.status)}</td>
      <td>${r.mode === "llm" ? `<span class="chip">${icon("cpu")}${esc(r.model || "LLM")}</span>` : `<span class="chip">${icon("flask")}演示${r.scenario ? " · " + esc(S.info?.scenarios?.[r.scenario]?.title || r.scenario) : ""}</span>`}</td>
      <td>${r.version != null ? `v${r.version} · 修订 ${r.revisions ?? 0}` : "—"}</td>
      <td>${r.signoff ? badge(DECISION[r.signoff.decision]?.t || r.signoff.decision, DECISION[r.signoff.decision]?.c || "gray") + `<div class="muted small">${esc(r.signoff.reviewer)}</div>` : r.status === "approved" || r.status === "needs_human_review" ? badge("待签署", "gray") : "—"}</td>
      <td class="muted small" style="white-space:nowrap">${fmtTime(r.created_at)}</td></tr>`).join("");
  }
  const runTable = (runs, id = "") => `<div class="table-wrap"><table class="table"><thead><tr><th>病例 / 决策问题</th><th>工作流状态</th><th>模式</th><th>版本</th><th>医师签署</th><th>时间</th></tr></thead><tbody ${id ? `id="${id}"` : ""}>${runRows(runs)}</tbody></table></div>`;

  async function viewDashboard() {
    const route = routeVersion;
    setView(loading(), crumb("工作台"));
    let runs;
    try { runs = (await api("/api/runs")).runs; }
    catch (e) { if (route !== routeVersion) return; setView(`<div class="empty">${icon("alert")}<p>暂时无法读取审核记录</p><button class="btn" data-action="reload">重新加载</button></div>`); toast(e.message, "bad"); return; }
    if (route !== routeVersion) return;
    const count = (status) => runs.filter((r) => r.status === status).length;
    const pending = runs.filter((r) => ["approved", "needs_human_review"].includes(r.status) && !r.signoff).length;
    const metric = (value, label, ic, note) => `<div class="metric-card"><div class="metric-top">${label}${icon(ic)}</div><div class="metric-value">${value}<small>例</small></div><div class="metric-bottom">${note}</div></div>`;
    const date = new Date().toLocaleDateString("zh-CN", {year:"numeric",month:"long",day:"numeric",weekday:"long"});
    const recent = runs.length ? runTable(runs.slice(0, 5)) : `<div class="recent-empty"><div class="empty-file">${icon("file")}</div><b>从第一份病例开始</b><p>导入病例，开启一次可追溯的多专家协作。</p><a href="#/new" class="btn sm">${icon("plus")}创建首份审核</a></div>`;
    setView(`<div class="dashboard-stack">
      <div class="dashboard-head"><div><h1>工作台</h1><p>在这里，开启每一次有依据的判断。</p></div><div class="today">${icon("clock")}${date}</div></div>
      <section class="workspace-hero"><div class="hero-copy"><div class="hero-kicker">VTE CLINICAL WORKSPACE</div><h2>多专家协作，<br><em>让决策更清晰。</em></h2><p>聚合抗凝获益、用药安全与出血风险判断，<br>以循证检索与定向复核，形成可追溯的诊疗建议。</p><div class="row"><a class="btn primary lg" href="#/new">${icon("plus")}新建病例审核</a><button class="btn lg" data-action="quick-demo" data-s="targeted">${icon("play")}体验协作演示</button></div></div>
      <div class="hero-diagram" aria-label="A、B、C 并行评估，D 汇总并定向返修"><div class="hero-orbit"><div class="orbit-ring"></div><svg class="orbit-connector" viewBox="0 0 315 236" aria-hidden="true"><path d="M48 112 Q48 130 157 147 M157 89 V147 M267 112 Q267 130 157 147"/><path d="M157 196 V210" stroke-dasharray="3 4"/></svg><div class="orbit-specialists">${ROLES.map((r) => `<div class="orbit-role">${roleTag(r)}<b>${({A:"抗凝获益与疗程",B:"药物选择与安全",C:"出血风险与约束"})[r]}</b><small>SPECIALIST ${r}</small></div>`).join("")}</div><div class="orbit-d">${roleTag("D",30)}<div><b>协调 · 整合 · 修订</b><small>有分歧，定向再审核</small></div></div><div class="diagram-label">并行判断 · 按需复核</div></div></div></section>
      <div class="dashboard-stats">${metric(runs.length,"累计审核","folder","本地保存的全部记录")}${metric(count("approved"),"审核通过","shield","各领域 Agent 审核完成")}${metric(count("needs_human_review"),"待人工复核","alert","保留未决问题，交由医师")}${metric(pending,"待医师签署","pen","等待最终审阅与确认")}</div>
      <div class="dashboard-bottom"><section class="card recent-card"><div class="card-h"><div><h3>最近审核</h3><div class="section-label">RECENT REVIEWS</div></div><a href="#/history" class="btn ghost sm">查看全部${icon("chevron")}</a></div>${recent}</section><section class="card team-card"><div class="card-h"><div><h3>你的多专家协作组</h3><div class="section-label">FOUR AGENTS · ONE WORKFLOW</div></div></div><div class="card-b">${ROLES.map((r) => `<div class="team-member">${roleTag(r)}<div><b>${ROLE[r].short}</b><small>${ROLE[r].name}</small></div><span class="member-dot"></span></div>`).join("")}<div class="team-coordinator">${roleTag("D",28)}<div><b>D · 协调员</b><small>汇总判断，处理分歧与定向修订</small></div></div></div></section></div>
      <div class="dashboard-footer"><span>${icon("lock")}运行记录保存在本机 · 模型连接由你配置</span><span>VTE Review · 研究辅助，最终决策由医师作出</span></div>
    </div>`);
  }

  /* ================= history ================= */
  async function viewHistory() {
    const route = routeVersion;
    setView(loading(), crumb("审核记录"));
    try { S.runs = (await api("/api/runs")).runs; } catch (e) { toast(e.message, "bad"); S.runs = []; }
    if (route !== routeVersion) return;
    const filters = [["all", "全部"], ["approved", "审核通过"], ["needs_human_review", "需人工复核"], ["failed", "失败"], ["running", "进行中"], ["unsigned", "待签署"]];
    setView(`<div class="page-h"><div><h1 class="h1">审核记录</h1><p class="lead">所有运行均保存在本机 <span class="mono">${esc(S.info?.runs_dir || "runs/")}</span></p></div>
      <a class="btn primary" href="#/new">${icon("plus")}新建审核</a></div>
      <div class="card"><div class="card-h history-tools"><div class="seg">${filters.map(([k, t]) => `<button data-action="hist-f" data-f="${k}" class="${S.hist.f === k ? "on" : ""}">${t}</button>`).join("")}</div>
      <div class="row" style="width:300px;position:relative"><input class="input" data-input="hist-q" placeholder="搜索病例编号、问题或运行 ID" value="${esc(S.hist.q)}"></div></div>
      ${runTable(filterRuns(), "hist-body")}</div>`, crumb("审核记录"));
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
    if (!o || typeof o !== "object" || Array.isArray(o) || typeof o.case_id !== "string" || typeof o.question !== "string" || !o.facts || typeof o.facts !== "object" || Array.isArray(o.facts) || !Array.isArray(o.missing_information) || o.missing_information.some((v) => typeof v !== "string")) throw new Error("病例需包含 case_id、question、facts 对象和 missing_information 字符串数组");
    const facts = Object.entries(o.facts || {}).map(([k, v]) => [k, typeof v === "string" ? v : JSON.stringify(v)]);
    return { case_id: String(o.case_id || ""), question: String(o.question || ""), facts: facts.length ? facts : [["", ""]], missing: [...new Set((o.missing_information || []).map(String))] };
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
    return { case_id: c.case_id.trim(), question: c.question.trim(), facts, missing_information: c.missing.filter((x) => x.trim()) };
  }
  function caseChecks() {
    const c = buildCase(), out = [];
    if (S.w.jsonError) out.push(["bad", "病例 JSON 尚未修正，请返回病例页完成修改"]);
    out.push(c.case_id ? ["ok", `病例编号：${c.case_id}`] : ["bad", "填写病例编号（建议使用脱敏编号）"]);
    out.push(c.question ? ["ok", "已填写决策问题"] : ["bad", "填写本次需要解决的决策问题"]);
    const n = Object.keys(c.facts).length;
    out.push(n ? ["ok", `已录入患者事实 ${n} 项`] : ["bad", "至少录入 1 项已核对的患者事实"]);
    const keys = S.w.case.facts.map(([k]) => String(k).trim()).filter(Boolean);
    if (new Set(keys).size !== keys.length) out.push(["bad", "存在重复字段，请合并后再开始审核"]);
    out.push(c.missing_information.length ? ["warn", `已声明缺失信息 ${c.missing_information.length} 项（专家可据此判定需补充资料）`] : ["info", "未声明缺失信息"]);
    return out;
  }
  const checkList = (items) => `<div class="check-list">${items.map(([s, t]) => `<div class="check-item ${s}">${icon(s === "ok" ? "check" : s === "bad" ? "x" : s === "warn" ? "alert" : "info")}<span>${esc(t)}</span></div>`).join("")}</div>`;
  function defaultsToSettings() { const d = S.info?.defaults || { max_revisions: 3, max_concurrency: 3, call_timeout: 60, top_k: 4 }; return { max_revisions: d.max_revisions, concurrency: d.max_concurrency, timeout: d.call_timeout, top_k: d.top_k }; }

  function viewNew() { S.w = S.w || loadWizard(); if (!S.w.settings) S.w.settings = defaultsToSettings(); S.evMap = Object.fromEntries((S.w.evidence || []).map((d) => [d.id, d])); renderWizard(); }
  function renderWizard() {
    const w = S.w;
    const steps = [["病例信息", "结构化、脱敏的患者事实"], ["证据库", "指南 / 说明书原文片段"], ["运行配置", "演示模式或真实模型"]];
    const body = [stepCase, stepEvidence, stepRun][w.step]();
    setView(`<div class="page-h"><div><h1 class="h1">新建多专家审核</h1><p class="lead">录入病例与证据后，A/B/C 三位专家 Agent 并行评估，D 汇总并按审核意见定向返修。</p></div>
      <button class="btn ghost" data-action="w-reset">${icon("refresh")}重置表单</button></div>
      <div class="steps">${steps.map(([t, s], i) => `<button class="step ${i === w.step ? "on" : ""} ${i < w.step ? "done" : ""}" data-action="w-step" data-i="${i}"><span class="n">${i < w.step ? icon("check") : i + 1}</span><span><b>${t}</b><span class="s">${s}</span></span></button>`).join("")}</div>
      ${body}
      <div class="row" style="margin-top:20px">${w.step > 0 ? `<button class="btn" data-action="w-prev">${icon("arrowLeft")}上一步</button>` : ""}<span class="spacer"></span>${w.step < 2 ? `<button class="btn primary" data-action="w-next">下一步${icon("chevron")}</button>` : ""}</div>`, crumb("新建审核"));
    if (w.step === 0) refreshCaseSide();
  }
  const factRow = ([k, v], i) => `<div class="kv"><input class="input" data-input="fact-k" data-i="${i}" value="${esc(k)}" placeholder="字段，如 eGFR"><input class="input" data-input="fact-v" data-i="${i}" value="${esc(v)}" placeholder="取值，如 52 mL/min/1.73m²"><button class="btn ghost sm" data-action="fact-del" data-i="${i}" title="删除">${icon("x")}</button></div>`;
  function stepCase() {
    const w = S.w, c = w.case;
    const form = `
      <div class="notice warn">${icon("lock")}<div>请仅录入<b>脱敏后</b>的结构化事实：不要填写姓名、身份证号、住院号、联系方式等可识别个人身份的信息。</div></div>
      <div class="field" style="margin-top:16px"><label>病例编号</label><input class="input" data-input="case" data-k="case_id" value="${esc(c.case_id)}" placeholder="如 DEID-2026-001"></div>
      <div class="field" style="margin-top:14px"><label>决策问题</label><textarea class="textarea" data-input="case" data-k="question" placeholder="例如：确诊近端 DVT 后第 3 天，评估抗凝药物选择、疗程及出血风险监测方案">${esc(c.question)}</textarea><span class="hint">写清本次需要解决的决策问题及时间点</span></div>
      <div class="field" style="margin-top:14px"><label>已核对的患者事实</label>
        <div id="facts">${c.facts.map(factRow).join("")}</div>
        <div class="row wrap" style="margin-top:8px"><button class="btn sm" data-action="fact-add">${icon("plus")}添加一项</button><span class="muted small">常用：</span>${QUICK.map((q) => `<button class="chip" data-action="fact-quick" data-k="${esc(q)}">${esc(q)}</button>`).join("")}</div>
        <span class="hint">纯数字、true / false 会自动识别类型；缺失的数据请勿猜测填写。</span></div>
      <div class="field" style="margin-top:14px"><label>尚缺失的必要信息</label>
        <div class="tags-input">${c.missing.map((m, i) => `<span class="tag-x">${esc(m)}<button data-action="miss-del" data-i="${i}" title="移除">${icon("x")}</button></span>`).join("")}<input data-key="miss-add" placeholder="输入后按回车添加，如：近 3 个月血红蛋白"></div></div>`;
    const json = `<textarea class="textarea code" data-input="case-json" spellcheck="false">${esc(w.jsonError ? w.jsonDraft : JSON.stringify(buildCase(), null, 2))}</textarea><div id="json-err" class="small muted" style="margin-top:6px">直接编辑 JSON，合法时自动同步到表单。</div>`;
    return `<div class="grid g-side">
      <div class="card"><div class="card-h"><h3>${icon("file")}病例信息</h3>
        <div class="row"><div class="seg"><button data-action="case-mode" data-m="form" class="${w.caseMode === "form" ? "on" : ""}">${icon("pen")}表单</button><button data-action="case-mode" data-m="json" class="${w.caseMode === "json" ? "on" : ""}">${icon("code")}JSON</button></div></div></div>
        <div class="card-b">${w.caseMode === "form" ? form : json}</div>
        <div class="card-h" style="border-top:1px solid var(--line-2);border-bottom:0">
          <div class="row"><button class="btn sm" data-action="case-demo">${icon("flask")}载入演示病例</button>
          <label class="btn sm" tabindex="0" role="button">${icon("upload")}导入 JSON 文件<input type="file" accept=".json,application/json" data-change="case-file" hidden></label></div>
          <button class="btn ghost sm danger" data-action="case-clear">${icon("trash")}清空</button></div>
      </div>
      <div class="stack">
        <div class="card"><div class="card-h"><h3>${icon("shield")}录入检查</h3></div><div class="card-b" id="case-check"></div></div>
        <details class="card preview-details"><summary>查看结构化病例数据</summary><pre class="json" id="case-preview"></pre></details>
      </div></div>`;
  }
  function refreshCaseSide() {
    const el = $("#case-check"); if (el) el.innerHTML = checkList(caseChecks());
    const pv = $("#case-preview"); if (pv) pv.innerHTML = jsonHTML(buildCase());
  }
  function stepEvidence() {
    const w = S.w, ev = w.evidence, ck = w.evidenceCheck;
    const left = ev ? `
      <div class="card-h"><h3>${icon("database")}${esc(w.evidenceName || "证据库")}</h3><div class="row">
        <label class="btn sm" tabindex="0" role="button">${icon("upload")}更换<input type="file" accept=".json,application/json" data-change="evidence-file" hidden></label>
        <button class="btn ghost sm danger" data-action="ev-clear">${icon("trash")}移除</button></div></div>
      <div class="table-wrap"><table class="table"><thead><tr><th>ID / 标题</th><th>版本</th><th>适用角色</th><th>来源</th></tr></thead><tbody>
      ${ev.map((d) => `<tr class="click" data-action="evidence" data-id="${esc(d.id)}"><td><div class="mono small muted">${esc(d.id)}</div><div style="font-weight:600">${esc(d.title)}</div></td><td class="small">${esc(d.version)}</td><td>${(d.roles || []).map((r) => roleTag(r, 20)).join(" ")}</td><td>${d.synthetic ? badge("合成", "warn") : badge("已声明真实", "ok")}</td></tr>`).join("")}
      </tbody></table></div>` : `
      <div class="card-h"><h3>${icon("database")}证据库</h3></div>
      <div class="card-b">
        <label tabindex="0" role="button" class="dropzone" style="display:block">${icon("upload")}<div style="font-weight:600;color:var(--text-2)">拖入或点击选择证据库 JSON 文件</div><div class="small">JSON 数组，每条包含 id / title / source / version / text / roles / synthetic</div><input type="file" accept=".json,application/json" data-change="evidence-file" hidden></label>
        <div class="row" style="margin-top:14px"><button class="btn sm" data-action="ev-demo">${icon("flask")}使用内置演示证据（合成，仅限演示模式）</button></div>
        <details style="margin-top:16px"><summary class="muted small" style="cursor:pointer">查看证据条目格式</summary><pre class="json" style="margin-top:10px">${jsonHTML([{ id: "SOURCE-SECTION-001", title: "实际来源标题", source: "文献/说明书地址与章节位置", version: "版本或日期", text: "依法可使用、人工核对后的原文片段", roles: ["A", "B", "C"], synthetic: false }])}</pre></details>
      </div>`;
    const right = ck && ck.ok ? `<div class="grid g-2" style="gap:10px">
        <div class="card stat" style="box-shadow:none"><div><div class="stat-v">${ck.count}</div><div class="stat-l">证据条目</div></div></div>
        <div class="card stat" style="box-shadow:none"><div><div class="stat-v" style="color:${ck.synthetic ? "var(--warn)" : "var(--ok)"}">${ck.synthetic}</div><div class="stat-l">合成条目</div></div></div></div>
        <div class="muted small" style="margin:14px 0 8px">各角色可检索条目</div>
        <div class="appr">${ROLES.map((r) => `<div class="appr-cell ${ck.roles[r] ? "ok" : "no"}">${roleTag(r)}<div><div class="lbl">${ROLE[r].short}</div><b>${ck.roles[r]} 条</b></div></div>`).join("")}</div>
        ${ROLES.some((r) => !ck.roles[r]) ? `<div class="notice warn" style="margin-top:12px">${icon("alert")}<div>有角色没有可用证据，工作流将在检索阶段停止并转人工。</div></div>` : ""}
        ${ck.synthetic ? `<div class="notice warn" style="margin-top:12px">${icon("flask")}<div>含合成条目：只能用于演示模式，真实模型模式会拒绝。</div></div>` : ""}`
      : `<div class="muted">尚未导入证据库。演示模式可不导入（将使用内置合成证据）；真实模型模式必须导入。</div>`;
    return `<div class="grid g-side"><div class="card">${left}</div>
      <div class="stack"><div class="card"><div class="card-h"><h3>${icon("shield")}证据检查</h3></div><div class="card-b">${right}</div></div>
      <div class="notice info">${icon("info")}<div>检索按角色过滤并按词重合排序；引用只能来自本次实际检索到的条目。<b>synthetic=false 仅为提供者声明</b>，程序不验证来源真实性。</div></div></div></div>`;
  }
  function startChecks() {
    const w = S.w, items = [];
    const env = S.info?.env || {};
    if (w.mode === "demo") {
      items.push(["ok", "离线演示：确定性响应，不调用任何模型，不产生真实建议"]);
      if (w.useDemoData) items.push(["ok", "使用内置合成病例与合成证据"]);
      else {
        items.push(...caseChecks().filter(([s]) => s !== "info"));
        items.push(w.evidence ? ["ok", `证据库 ${w.evidence.length} 条`] : ["warn", "未导入证据库，将使用内置合成证据"]);
      }
    } else {
      items.push(...caseChecks().filter(([s]) => s !== "info"));
      const ck = w.evidenceCheck;
      if (!w.evidence) items.push(["bad", "真实模型模式需要导入证据库"]);
      else if (ck?.synthetic) items.push(["bad", `证据库含 ${ck.synthetic} 条合成条目，真实模式不接受`]);
      else items.push(["ok", `证据库 ${w.evidence.length} 条`]);
      if (ck?.ok) for (const r of ROLES) if (!ck.roles[r]) items.push(["warn", `${r} 角色无可用证据，运行将在检索阶段停止`]);
      items.push(w.llm.model || env.model ? ["ok", `模型：${w.llm.model || env.model}`] : ["bad", "填写模型名称"]);
      items.push(apiKey || env.api_key_set ? ["ok", apiKey ? "API Key 已填写（仅保存在内存）" : "使用环境变量中的 API Key"] : ["bad", "填写 API Key"]);
      if (S.info && !S.info.httpx) items.push(["bad", '未安装 HTTP 适配器：python -m pip install -e ".[llm]"']);
      items.push(["warn", "病例与证据将发送到所配置的模型端点"]);
    }
    const limits = [["max_revisions", "最大修订次数", 0], ["concurrency", "并发上限", 1], ["timeout", "单次超时", 1], ["top_k", "检索条数", 1]];
    for (const [key, label, min] of limits) {
      const n = Number(w.settings?.[key]);
      if (!Number.isFinite(n) || !Number.isInteger(n) || n < min || String(w.settings?.[key]).trim() === "") items.push(["bad", `${label}需为不小于 ${min} 的整数`]);
    }
    return { items, ok: !items.some(([s]) => s === "bad") };
  }
  function stepRun() {
    const w = S.w, env = S.info?.env || {}, sc = S.info?.scenarios || {};
    const modeCard = (m, ic, c, t, d) => `<button class="mode-card ${w.mode === m ? "on" : ""}" data-action="w-mode" data-m="${m}"><div class="stat-ic" style="background:var(--${c}-soft);color:var(--${c})">${icon(ic)}</div><div><b>${t}</b><p>${d}</p></div></button>`;
    const demo = `<div class="card"><div class="card-h"><h3>${icon("flask")}演示场景</h3><span class="muted small">用于展示不同的审核路径</span></div><div class="card-b">
        <div class="grid g-3" style="gap:10px">${Object.entries(sc).map(([k, v]) => `<button class="scenario ${w.scenario === k ? "on" : ""}" data-action="w-scenario" data-s="${k}"><b>${esc(v.title)} ${v.expect === "approved" ? badge("通过", "ok", "nodot") : badge("转人工", "warn", "nodot")}</b><p>${esc(v.desc)}</p></button>`).join("")}</div>
        <div class="hr"></div>
        <div class="grid g-2"><div class="field"><label>演示节奏：每次调用约 <span id="pace-v">${Number(w.pace).toFixed(1)}</span> 秒</label><input type="range" min="0" max="2" step="0.1" value="${w.pace}" data-input="pace"></div>
        <label class="row" style="gap:8px;cursor:pointer"><input type="checkbox" data-change="use-demo" ${w.useDemoData ? "checked" : ""}> 使用内置合成病例与证据（推荐）</label></div>
      </div></div>`;
    const llm = `<div class="card"><div class="card-h"><h3>${icon("cpu")}模型接口</h3><span class="muted small">OpenAI Chat Completions 兼容端点（需支持 JSON mode）</span></div><div class="card-b stack" style="gap:14px">
        <div class="grid g-2"><div class="field"><label>Base URL</label><input class="input" data-input="llm" data-k="base_url" value="${esc(w.llm.base_url)}" placeholder="${esc(env.base_url || "https://api.openai.com/v1")}"></div>
        <div class="field"><label>模型名称</label><input class="input" data-input="llm" data-k="model" value="${esc(w.llm.model)}" placeholder="${esc(env.model || "例如 gpt-4.1")}"></div></div>
        <div class="field"><label>API Key</label><input class="input" type="password" autocomplete="off" data-input="apikey" value="${esc(apiKey)}" placeholder="${env.api_key_set ? "已检测到环境变量 VTE_API_KEY，可留空" : "sk-…"}"><span class="hint">${icon("lock")} 仅保存在本次会话内存中，不写入磁盘、不写入运行记录。</span></div>
        <details><summary class="muted small" style="cursor:pointer">按角色指定不同模型（可选）</summary><div class="grid g-4" style="margin-top:10px">${[...ROLES, "D"].map((r) => `<div class="field"><label>${r} · ${ROLE[r].short}</label><input class="input" data-input="llm-role" data-r="${r}" value="${esc(w.llm.role_models?.[r] || "")}" placeholder="${esc(env.role_models?.[r] || "默认")}"></div>`).join("")}</div></details>
        <div class="notice warn">${icon("alert")}<div>真实模式会把病例与证据发送到上述端点，请确认符合所在机构的数据合规要求。超时、格式错误、虚构引用均不会被当作通过。</div></div>
      </div></div>`;
    const s = w.settings;
    const num = (k, l, h, min, step = 1) => `<div class="field"><label>${l}</label><input class="input" type="number" min="${min}" step="${step}" data-input="setting" data-k="${k}" value="${esc(s[k])}"><span class="hint">${h}</span></div>`;
    const { items, ok } = startChecks();
    return `<div class="grid g-side"><div class="stack">
      <div class="grid g-2">${modeCard("demo", "flask", "brand", "演示模式", "离线、确定性，展示协作与返修流程")}${modeCard("llm", "cpu", "ok", "真实模型", "接入 OpenAI 兼容接口，对真实病例运行")}</div>
      ${w.mode === "demo" ? demo : llm}
      <div class="card"><div class="card-h"><h3>${icon("settings")}高级参数</h3></div><div class="card-b"><div class="grid g-4">
        ${num("max_revisions", "最大修订次数", "D 最多返修轮数", 0)}${num("concurrency", "并发上限", "同时进行的模型调用", 1)}${num("timeout", "单次超时（秒）", "超时即判定失败", 1)}${num("top_k", "每角色检索条数", "Top-K 证据", 1)}
      </div></div></div>
    </div>
    <div class="card" style="position:sticky;top:0"><div class="card-h"><h3>${icon("target")}启动前检查</h3></div><div class="card-b">
      ${checkList(items)}
      <button class="btn primary lg" style="width:100%;margin-top:18px" data-action="start" ${ok ? "" : "disabled"}>${icon("play")}开始多专家审核</button>
      <div class="muted small" style="margin-top:10px">启动后自动进入实时监控；记录保存在本机运行目录。</div>
    </div></div></div>`;
  }

  /* ================= run detail ================= */
  async function viewRun(id, tab) {
    const route = routeVersion;
    setView(loading(), crumb("审核记录", id));
    let d;
    try { d = await api(`/api/runs/${encodeURIComponent(id)}`); }
    catch (e) { if (route !== routeVersion) return; setView(`<div class="empty">${icon("alert")}<div>${esc(e.message)}</div><a class="btn" href="#/history" style="margin-top:12px">返回记录</a></div>`); return; }
    if (route !== routeVersion) return;
    S.run = d; S.signDecision = "";
    S.runTab = tab || (d.status === "running" ? "live" : "report");
    S.evMap = Object.fromEntries((d.result?.evidence || []).map((x) => [x.id, x]));
    renderRunShell();
    if (d.status === "running") startStream(id);
  }
  function renderRunShell() {
    const d = S.run, done = !!d.result;
    const tabs = [["report", "steth", "医生审阅"], ["live", "activity", "流程监控"], ["versions", "git", "版本与修订"], ["audit", "database", "审计日志"]];
    const mode = d.mode === "llm" ? `<span class="chip">${icon("cpu")}${esc(d.meta?.model || "LLM")}</span>` : `<span class="chip">${icon("flask")}演示${d.scenario ? " · " + esc(S.info?.scenarios?.[d.scenario]?.title || d.scenario) : ""}</span>`;
    setView(`<div class="run-head"><div class="title">
        <div class="row wrap"><a href="#/history" class="btn ghost sm">${icon("arrowLeft")}返回</a><span class="chip mono">${esc(d.id)}</span><span id="run-status">${statusBadge(d.status)}</span>${mode}</div>
        <h1 class="q">${esc(d.case?.question || "")}</h1>
        <div class="muted small">病例 ${esc(d.case_id)} · 创建于 ${fmtTime(d.created_at)}</div></div>
      <div class="row no-print">
        <button class="btn" data-action="reuse-case" title="以此病例新建审核">${icon("refresh")}复用病例</button>
        ${done ? `<a class="btn" href="/api/runs/${encodeURIComponent(d.id)}/report.md">${icon("download")}报告 .md</a><a class="btn" href="/api/runs/${encodeURIComponent(d.id)}/result.json">${icon("code")}数据 .json</a>` : ""}
        <button class="btn primary" data-action="print" ${done ? "" : "disabled"}>${icon("printer")}打印 / PDF</button></div></div>
      <div class="tabs">${tabs.map(([k, ic, t]) => `<button class="${S.runTab === k ? "on" : ""}" data-action="tab" data-t="${k}">${icon(ic)}${t}</button>`).join("")}</div>
      <div id="run-body"></div>`, crumb("审核记录", d.case_id || d.id));
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
    es.onerror = () => { if (route === routeVersion) $("#run-status").innerHTML = badge("连接中断，正在重连", "warn"); };
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
        toast(`审核结束：${s.t || d.status}`, d.status === "approved" ? "ok" : d.status === "failed" ? "bad" : "info");
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
      <div class="ah">${roleTag(r, 34)}<div><div class="an">${r === "D" ? "D · 协调员" : `专家 ${r} · ${ROLE[r].short}`}</div><div class="ar">${ROLE[r].name}</div></div></div>
      <div class="astate" style="color:${color}">${ic}<span>${esc(a.label)}</span></div>
      ${a.note ? `<div class="anote">${esc(a.note)}</div>` : ""}</div>`;
  }
  function ganttHTML(st) {
    const now = liveNow(st), total = Math.max(now, 0.5);
    const rows = [...ROLES, "D"].map((r) => `<div class="g-row"><div class="g-l">${roleTag(r, 20)}${r === "D" ? "协调" : "专家"}</div><div class="g-track">
      ${st.calls.filter((c) => c.role === r).map((c) => {
        const end = c.end ?? now, left = (c.start / total) * 100, width = Math.max(((end - c.start) / total) * 100, 0.8);
        const mark = c.task === "review" && c.output ? (c.output.verdict === "approve" ? " ✓" : " ✗") : "";
        return `<div class="g-bar ${c.status === "running" ? "running" : ""}" style="left:${left}%;width:${width}%;background-color:${c.status === "failed" ? "var(--bad)" : `var(--${r})`}" title="${esc(TASK[c.task])}${c.version ? ` v${c.version}` : ""} · ${(end - c.start).toFixed(2)} 秒">${esc(TASK_SHORT[c.task] || c.task)}${c.version ? ` v${c.version}` : ""}${mark}</div>`;
      }).join("")}</div></div>`).join("");
    return `${rows}<div class="g-axis"><div></div><div>${[0, .25, .5, .75, 1].map((f) => `<span>${(total * f).toFixed(1)}s</span>`).join("")}</div></div>`;
  }
  function timelineItem(e) {
    const R = (r) => `<b>${r === "D" ? "协调员 D" : `专家 ${r}`}</b>`;
    switch (e.event) {
      case "started": return ["var(--brand)", "工作流启动", `最大修订 ${e.settings?.max_revisions} 次 · 并发 ${e.settings?.max_concurrency} · 提示词 ${e.prompt_version}`];
      case "call_completed":
        if (e.task === "assess") return [`var(--${e.role})`, `${R(e.role)} 完成独立初判`, e.output?.summary];
        if (e.task === "synthesize") return ["var(--D)", `${R("D")} 完成草案汇总`, ""];
        if (e.task === "revise") return ["var(--D)", `${R("D")} 完成定向修订`, e.output?.reason];
        if (e.task === "review") { const v = VERDICT[e.output?.verdict] || {}; return [v.c === "ok" ? "var(--ok)" : v.c === "warn" ? "var(--warn)" : "var(--bad)", `${R(e.role)} 审核 v${e.version}：${v.t || e.output?.verdict}`, [e.output?.note, ...(e.output?.issues || []).map((i) => `[${i.id}] ${i.problem}`)].filter(Boolean).join("　")]; }
        return null;
      case "call_failed": return ["var(--bad)", `${R(e.role)} ${TASK[e.task] || e.task}失败`, e.error];
      case "draft_created": return ["var(--D)", `生成草案 <b>v${e.version}</b>`, "进入 A/B/C 并行审核"];
      case "review_round": return ["var(--brand)", `第 ${e.version} 版审核开始`, `参与复核：${(e.roles || []).join("、")}`];
      case "draft_revised": return ["var(--D)", `草案修订至 <b>v${e.version}</b>`, `需复核：${(e.roles || []).join("、")}${e.reason ? " · " + e.reason : ""}`];
      case "finished": return [e.status === "approved" ? "var(--ok)" : e.status === "failed" ? "var(--bad)" : "var(--warn)", `工作流结束：<b>${esc(STATUS[e.status]?.t || e.status)}</b>`, reasonText(e.reason)];
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
      ${fin ? `<div class="notice ${fin.status === "approved" ? "info" : fin.status === "failed" ? "bad" : "warn"}">${icon(fin.status === "approved" ? "check" : "alert")}<div style="flex:1"><b>${esc(STATUS[fin.status]?.t || fin.status)}</b>：${esc(reasonText(fin.reason))}</div>${d.result ? `<button class="btn sm primary" data-action="tab" data-t="report">${icon("steth")}查看医生审阅报告</button>` : ""}</div>` : ""}
      <div class="card"><div class="card-h"><h3>${icon("layers")}流程进度</h3><span class="row muted small">${icon("clock")}<span id="elapsed">${fmtSec(liveNow(st))}</span></span></div>
        <div class="phases">${st.phases.map((p) => `<div class="phase ${p.state}"><div class="dot">${phaseIc(p)}</div><span>${esc(p.label)}</span>${p.sub ? `<span class="small" style="margin-top:-6px">${esc(p.sub)}</span>` : ""}</div>`).join("")}</div></div>
      <div class="grid g-side"><div class="stack">
        <div class="card"><div class="card-h"><h3>${icon("users")}专家协作看板</h3><span class="muted small">${st.version ? `当前草案 v${st.version}` : "草案尚未生成"}</span></div>
          <div class="board" id="board"><svg class="wires"></svg><div class="agents">${ROLES.map((r) => agentCard(r, st.agents[r])).join("")}</div>${agentCard("D", st.agents.D)}</div></div>
        <div class="card"><div class="card-h"><h3>${icon("clock")}并行调用时序</h3><span class="muted small">横条重叠 = 同时进行</span></div><div class="gantt" id="gantt">${ganttHTML(st)}</div></div>
      </div>
      <div class="card"><div class="card-h"><h3>${icon("activity")}实时事件</h3>${badge(`${items.length} 条`, "gray", "nodot")}</div>
        <ul class="timeline">${items.map(([e, [color, m, dd]]) => `<li class="${(e.seq || 0) > seen ? "new" : ""}" style="--tl:${color}"><div class="t">+${(e.elapsed_s ?? 0).toFixed(2)}s</div><div class="m">${m}</div>${dd ? `<div class="d">${esc(dd)}</div>` : ""}</li>`).join("") || `<li><div class="m muted">等待事件…</div></li>`}</ul></div>
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
      if (d.status === "running") return `<div class="card"><div class="empty">${icon("activity")}<div style="font-weight:600;color:var(--text-2)">多专家审核进行中</div><div>完成后将在此生成医生审阅报告</div><button class="btn primary" style="margin-top:14px" data-action="tab" data-t="live">${icon("activity")}查看实时进度</button></div></div>`;
      return `<div class="verdict bad"><div class="big-ic">${icon("x")}</div><div><h3>${d.status === "interrupted" ? "运行已中断" : "运行失败"}</h3><p>${esc(d.reason ? reasonText(d.reason) : "服务在运行完成前停止，未生成结果。")}</p></div></div>`;
    }
    const v = { approved: ["ok", "check", d.signoffs.length ? "多专家审核通过 · 人工审阅已记录" : "多专家审核通过 · 待医师确认", "以下为经各专家审核通过的原样草案（未经二次改写）。"], needs_human_review: ["warn", "alert", "需人工复核", "以下为未全部通过的草案及问题单，仅供参考，不能直接用于决策。"], failed: ["bad", "x", "运行失败", "工作流因错误停止。"] }[r.status] || ["bad", "x", r.status, ""];
    const draft = r.draft, c = d.case || {};
    const m = r.metrics || {};
    const pendingRoles = ROLES.filter((x) => r.approvals?.[x] == null);
    const facts = Object.entries(c.facts || {});
    const sections = draft ? ROLES.map((x) => {
      const s = draft.sections[x], ap = r.approvals?.[x], rev = r.reviews?.[x];
      return `<div class="section-card ${x}"><div class="sh">${roleTag(x, 32)}<div style="flex:1"><div class="name">专家 ${x} · ${ROLE[x].name}</div><div class="sub">${ROLE[x].short}负责部分</div></div>${ap != null ? badge(`v${ap} 审核通过`, "ok") : badge(VERDICT[rev?.verdict]?.t || "未通过", rev?.verdict === "needs_information" ? "bad" : "warn")}</div>
        <div class="sb"><div class="stext">${esc(s.text)}</div>${rev?.note ? `<div class="row muted small" style="margin-top:12px;align-items:flex-start">${icon("message")}<span>专家意见：${esc(rev.note)}</span></div>` : ""}</div>
        <div class="sf"><span>引用证据</span>${evChips(s.evidence_ids)}${s.depends_on?.length ? `<span style="margin-left:10px">依赖</span>${s.depends_on.map((y) => roleTag(y, 20)).join("")}` : ""}</div></div>`;
    }).join("") : "";
    const issues = pendingRoles.flatMap((x) => (r.reviews?.[x]?.issues || []).map((i) => [x, r.reviews[x].verdict, i]));
    const last = d.signoffs.at(-1);
    return `<div class="print-only" style="margin-bottom:14px"><h2 style="margin:0">VTE 多专家协同审核报告</h2><div class="small muted">运行 ${esc(d.id)} · 病例 ${esc(c.case_id)} · 生成于 ${fmtTime(d.created_at)} · 打印于 ${fmtTime(new Date().toISOString())}</div><div class="hr"></div></div>
    <div class="grid g-side"><div class="stack">
      <div class="verdict ${v[0]}"><div class="big-ic">${icon(v[1])}</div><div><h3>${v[2]}</h3><p>${esc(reasonText(r.reason))}。${v[3]}</p></div>
        <div class="verdict-kpis"><div><b>v${r.version}</b><span>草案版本</span></div><div><b>${r.revisions}</b><span>D 修订次数</span></div><div><b>${m.calls ?? "—"}</b><span>模型调用</span></div><div><b>${fmtSec(m.elapsed_s)}</b><span>总用时</span></div></div></div>
      ${r.mode === "synthetic_demo" ? `<div class="notice warn">${icon("flask")}<div>本次为<b>合成演示</b>：使用人工编写的确定性响应与合成协议，内容不构成任何医学建议。</div></div>` : ""}
      <div class="card"><div class="card-h"><h3>${icon("user")}病例摘要</h3><span class="chip mono">${esc(c.case_id)}</span></div><div class="card-b">
        <div style="font-weight:600;margin-bottom:10px">${esc(c.question)}</div>
        <dl class="facts">${facts.map(([k, val]) => `<dt>${esc(k)}</dt><dd>${esc(fmtVal(val))}</dd>`).join("")}</dl>
        ${(c.missing_information || []).length ? `<div style="margin-top:12px"><div class="muted small" style="margin-bottom:6px">尚缺失的必要信息</div><div class="row wrap">${c.missing_information.map((x) => `<span class="tag-x" style="padding-right:10px">${icon("alert")}${esc(x)}</span>`).join("")}</div></div>` : ""}
      </div></div>
      ${draft ? `<div class="plan"><div class="plan-label">${icon("target")}共同决策前提与总体方案 · SHARED PLAN</div><div class="plan-text">${esc(draft.shared_plan)}</div></div>${sections}` : ""}
      ${issues.length ? `<div class="card"><div class="card-h"><h3>${icon("alert")}未决问题单</h3>${badge(`${issues.length} 项`, "warn", "nodot")}</div><div class="card-b">${issues.map(([x, verdict, i]) => `<div class="issue"><div class="ih">${roleTag(x, 22)}<span class="mono">${esc(i.id)}</span>${badge(VERDICT[verdict]?.t || verdict, VERDICT[verdict]?.c || "warn")}</div><div>${esc(i.problem)}</div><div class="req"><b>修改要求：</b>${esc(i.requested_change)}</div>${i.evidence_ids?.length || i.related_roles?.length ? `<div class="row wrap" style="margin-top:8px">${evChips(i.evidence_ids)}${(i.related_roles || []).map((y) => roleTag(y, 20)).join("")}</div>` : ""}</div>`).join("")}</div></div>` : ""}
      <div class="notice">${icon("shield")}<div>本报告由多 Agent 研究工作流生成。程序内“审核通过”仅表示各专家 Agent 未提出异议，<b>不等于临床有效性或安全性已验证</b>；引用检查只验证 ID 存在，不证明引文足以支持结论。最终诊疗决策由执业医师负责。</div></div>
      <div class="print-only" style="margin-top:18px">${last ? `<div>审阅医师：<b>${esc(last.reviewer)}</b>　结论：<b>${esc(DECISION[last.decision]?.t)}</b>　时间：${fmtTime(last.signed_at)}</div>${last.comment ? `<div>意见：${esc(last.comment)}</div>` : ""}<div class="small muted mono">草案指纹 SHA-256：${esc(last.draft_sha256)}</div>` : `<div style="margin-top:28px">审阅医师签名：＿＿＿＿＿＿＿＿　　日期：＿＿＿＿＿＿＿＿</div>`}</div>
    </div>
    <div class="stack no-print">
      <div class="card"><div class="card-h"><h3>${icon("users")}专家审核状态</h3></div><div class="card-b"><div class="appr" style="grid-template-columns:1fr">
        ${ROLES.map((x) => { const ap = r.approvals?.[x]; const rv = r.reviews?.[x]; return `<div class="appr-cell ${ap != null ? "ok" : "no"}">${roleTag(x)}<div style="flex:1"><div class="lbl">${ROLE[x].name}</div><b>${ap != null ? `v${ap} 通过` : VERDICT[rv?.verdict]?.t || "未通过"}</b></div>${ap != null ? icon("check") : icon("alert")}</div>`; }).join("")}
        <div class="appr-cell" style="background:var(--D-soft);border-color:#c6d5fb">${roleTag("D")}<div style="flex:1"><div class="lbl">协调员（不参与通过决定）</div><b>共 ${r.revisions} 次定向修订</b></div></div>
      </div></div></div>
      ${signHTML(d)}
      <div class="card"><div class="card-h"><h3>${icon("book")}引用证据</h3>${badge(`${(r.evidence || []).length} 条`, "gray", "nodot")}</div><div class="card-b" style="padding-top:4px;padding-bottom:4px">
        ${(r.evidence || []).map((e) => `<div class="ev-row"><div><div style="font-weight:600">${esc(e.title)}</div><div class="muted small">${esc(e.id)} · ${esc(e.version)} ${e.synthetic ? "· 合成" : ""}</div></div><button class="btn ghost sm" data-action="evidence" data-id="${esc(e.id)}">原文${icon("chevron")}</button></div>`).join("") || `<div class="muted">无</div>`}
      </div></div>
    </div></div>`;
  }
  function signHTML(d) {
    const r = d.result;
    if (!r || !r.draft) return "";
    const last = d.signoffs.at(-1);
    const dec = S.signDecision;
    const hist = d.signoffs.slice().reverse().map((s) => `<div class="seal"><div class="row">${badge(DECISION[s.decision]?.t || s.decision, DECISION[s.decision]?.c || "gray")}<b>${esc(s.reviewer)}</b><span class="spacer"></span><span class="muted small">${fmtTime(s.signed_at)}</span></div>${s.comment ? `<div style="margin:6px 0">${esc(s.comment)}</div>` : ""}<div class="hash">草案 v${esc(s.draft_version)} · SHA-256 ${esc(s.draft_sha256)}</div></div>`).join("");
    return `<div class="card sign"><div class="card-h"><h3>${icon("pen")}医师审阅签署</h3>${last ? badge(`已签署 · ${DECISION[last.decision]?.t}`, DECISION[last.decision]?.c) : badge("待签署", "gray")}</div><div class="card-b stack" style="gap:12px">
      <div class="decisions" id="decisions">${Object.entries(DECISION).map(([k, v]) => `<button class="decision ${k} ${dec === k ? "on" : ""}" data-action="decision" data-d="${k}">${icon(v.i)}${v.t}</button>`).join("")}</div>
      <div class="field"><label for="sign-name">审阅医师</label><input class="input" id="sign-name" value="${esc(localStorage.getItem("vte.reviewer") || "")}" placeholder="姓名 / 工号"></div>
      <div class="field"><label for="sign-comment">审阅意见</label><textarea class="textarea" id="sign-comment" placeholder="“修改后采纳”或“不采纳”时必填：说明需调整的内容及理由"></textarea></div>
      <button class="btn primary" data-action="sign">${icon("lock")}签署并存档</button>
      <div class="muted small">签署绑定草案 v${r.version} 的 SHA-256 指纹，追加写入本地运行目录，界面中不可修改或删除。</div>
      ${hist ? `<div class="hr" style="margin:4px 0"></div><div class="muted small">签署历史</div>${hist}` : ""}
    </div></div>`;
  }

  /* ---------- versions ---------- */
  function versionsHTML(d) {
    const st = derive(d.events);
    if (!st.drafts.length) return `<div class="card"><div class="empty">${icon("git")}<div>尚未生成草案</div></div></div>`;
    const reviews = {};
    for (const c of st.calls) if (c.task === "review" && c.output) (reviews[c.version] ||= []).push(c);
    const parts = [["shared_plan", "共同方案"], ...ROLES.map((r) => [r, `${r} · ${ROLE[r].short}`])];
    const textOf = (dr, k) => (k === "shared_plan" ? dr.shared_plan : dr.sections[k].text);
    const metaOf = (dr, k) => (k === "shared_plan" ? "" : JSON.stringify([dr.sections[k].evidence_ids, dr.sections[k].depends_on]));
    return `<div class="stack">${st.drafts.map((dv, i) => {
      const prev = st.drafts[i - 1];
      const changed = prev ? parts.filter(([k]) => textOf(prev.draft, k) !== textOf(dv.draft, k) || metaOf(prev.draft, k) !== metaOf(dv.draft, k)) : parts;
      const same = prev ? parts.filter((p) => !changed.includes(p)) : [];
      const rv = (reviews[dv.version] || []).sort((a, b) => a.role.localeCompare(b.role));
      return `<div class="card"><div class="card-h"><h3>${badge(`v${dv.version}`, "run", "nodot")}${dv.initial ? "D 汇总初版草案" : "D 定向修订"}</h3>
          <div class="row">${dv.initial ? "" : `<span class="muted small">需复核</span>${dv.roles.map((r) => roleTag(r, 22)).join("")}`}</div></div>
        <div class="card-b stack" style="gap:14px">
          ${dv.reason ? `<div class="notice info">${icon("pen")}<div><b>修订依据：</b>${esc(dv.reason)}</div></div>` : ""}
          ${changed.map(([k, label]) => `<div><div class="row" style="margin-bottom:6px">${k === "shared_plan" ? `<span class="chip">${icon("target")}${label}</span>` : `${roleTag(k, 22)}<b class="small">${esc(label)}</b>`}${prev ? badge("已修改", "warn", "nodot") : ""}${prev && metaOf(prev.draft, k) !== metaOf(dv.draft, k) ? badge("引用/依赖变更", "gray", "nodot") : ""}</div>
            <div class="diff" style="padding:12px 14px;background:var(--panel-2);border-radius:10px;border:1px solid var(--line-2)">${prev ? diffHTML(textOf(prev.draft, k), textOf(dv.draft, k)) : esc(textOf(dv.draft, k))}</div></div>`).join("")}
          ${same.length ? `<div class="muted small row">${icon("check")}未改动：${same.map(([, l]) => esc(l)).join("、")}</div>` : ""}
          ${rv.length ? `<div class="hr" style="margin:2px 0"></div><div class="muted small">v${dv.version} 审核结果</div>
            ${rv.map((c) => { const vv = VERDICT[c.output.verdict] || {}; return `<div class="row" style="align-items:flex-start">${roleTag(c.role, 26)}<div style="flex:1"><div class="row">${badge(vv.t || c.output.verdict, vv.c || "gray")}<span class="small">${esc(c.output.note)}</span></div>${(c.output.issues || []).map((is) => `<div class="issue" style="margin-top:8px"><div class="ih"><span class="mono small">${esc(is.id)}</span>${esc(is.problem)}</div><div class="req">修改要求：${esc(is.requested_change)}</div></div>`).join("")}</div></div>`; }).join("")}` : ""}
        </div></div>`;
    }).join("")}</div>`;
  }

  /* ---------- audit ---------- */
  function auditHTML(d) {
    const r = d.result, m = r?.metrics || {};
    const stat = (v, l, ic, c) => `<div class="card stat"><div class="stat-ic" style="background:var(--${c}-soft);color:var(--${c})">${icon(ic)}</div><div><div class="stat-v" style="font-size:20px">${v}</div><div class="stat-l">${l}</div></div></div>`;
    const label = (e) => `${e.event}${e.task ? ` · ${e.task}` : ""}${e.role ? ` · ${e.role}` : ""}${e.version ? ` · v${e.version}` : ""}`;
    const tone = (e) => (e.event === "call_failed" ? "bad" : e.event === "finished" ? (e.status === "approved" ? "ok" : "warn") : e.event.startsWith("draft") ? "run" : "gray");
    return `<div class="stack">
      <div class="grid g-4">${stat(fmtSec(m.elapsed_s), "总用时", "clock", "brand")}${stat(`${m.calls ?? "—"} <span class="muted small">/ 审核 ${m.review_calls ?? "—"}</span>`, "模型调用", "cpu", "ok")}${stat(m.usage_reported_calls ? m.reported_total_tokens : "未上报", "Token 用量（供应商上报）", "zap", "warn")}${stat(d.events.length, "事件记录", "activity", "run")}</div>
      <div class="grid g-2">
        <div class="card"><div class="card-h"><h3>${icon("settings")}运行参数与元数据</h3></div><div class="card-b"><pre class="json">${jsonHTML({ mode: r?.mode || d.mode, prompt_version: r?.prompt_version, settings: r?.settings, meta: d.meta })}</pre></div></div>
        <div class="card"><div class="card-h"><h3>${icon("file")}病例原始数据</h3></div><div class="card-b"><pre class="json">${jsonHTML(d.case)}</pre></div></div>
      </div>
      <div class="card"><div class="card-h"><h3>${icon("database")}事件流（events.jsonl）</h3><span class="muted small">模型输入已省略，完整内容见运行目录</span></div><div class="card-b">
        ${d.events.map((e) => `<details class="ev"><summary><span class="mono muted">#${e.seq ?? "—"}</span><span class="mono muted">+${(e.elapsed_s ?? 0).toFixed(3)}s</span>${badge(label(e), tone(e), "nodot")}${e.duration_s != null ? `<span class="muted small">${e.duration_s}s</span>` : ""}</summary><div class="body"><pre class="json">${jsonHTML(e)}</pre></div></details>`).join("")}
      </div></div></div>`;
  }

  /* ================= settings ================= */
  function viewSettings() {
    const i = S.info || {}, env = i.env || {}, w = S.w;
    const row = (k, v) => `<dt>${esc(k)}</dt><dd>${v}</dd>`;
    setView(`<div class="page-h"><div><h1 class="h1">模型与设置</h1><p class="lead">配置你的模型连接，让四位 Agent 开始协作。</p></div>${badge(env.api_key_set || apiKey ? "已配置凭据" : "演示模式可直接使用", env.api_key_set || apiKey ? "ok" : "gray")}</div>
      <div class="grid g-side"><div class="stack"><section class="card"><div class="card-h"><h3>${icon("cpu")}模型连接</h3><span class="muted small">兼容 Chat Completions · JSON mode</span></div><div class="card-b stack"><div class="profile-fields">
      <div class="field"><label>服务地址 Base URL</label><input class="input" data-input="llm" data-k="base_url" value="${esc(w.llm.base_url)}" placeholder="${esc(env.base_url || "https://api.openai.com/v1")}"></div>
      <div class="field"><label>默认模型</label><input class="input" data-input="llm" data-k="model" value="${esc(w.llm.model)}" placeholder="${esc(env.model || "填写服务商提供的模型名称")}"></div>
      <div class="field wide"><label>API Key</label><input class="input" type="password" autocomplete="off" data-input="apikey" value="${esc(apiKey)}" placeholder="${env.api_key_set ? "已配置环境变量，可留空" : "填写模型服务的访问密钥"}"><span class="hint">仅在当前页面会话内存中使用，刷新后需重新填写。地址和模型名称自动保存在此浏览器。</span></div></div>
      <div class="row wrap"><button class="btn primary" data-action="profile-save">${icon("check")}确认配置</button><button class="btn ghost" data-action="clear-key">清除临时密钥</button><a class="btn ghost" href="#/new">新建审核${icon("chevron")}</a></div></div></section>
      <section class="card"><div class="card-h"><h3>${icon("users")}按角色分配模型</h3><span class="muted small">可选 · 留空使用默认模型</span></div><div class="card-b profile-fields">${[...ROLES,"D"].map((r) => `<div class="field"><label>${r} · ${ROLE[r].short}</label><input class="input" data-input="llm-role" data-r="${r}" value="${esc(w.llm.role_models?.[r] || "")}" placeholder="${esc(env.role_models?.[r] || "使用默认模型")}"></div>`).join("")}</div></section>
      <div class="notice info">${icon("info")}<div>配置完成后，在“新建审核 → 运行配置”中选择真实模型。模型模式会向所配置的端点发送病例和证据；演示模式完全离线。</div></div></div>
      <div class="stack"><section class="card"><div class="card-h"><h3>${icon("activity")}本地运行环境</h3></div><div class="card-b"><dl class="facts">${row("软件版本",`v${esc(i.version)}`)}${row("提示词版本",esc(i.prompt_version))}${row("模型适配器",i.httpx ? badge("httpx 已安装","ok") : badge("未安装","warn"))}${row("默认检索",`每角色 Top-${i.defaults?.top_k}`)}${row("并发 / 修订",`${i.defaults?.max_concurrency} 个调用 / 最多 ${i.defaults?.max_revisions} 次`)}${row("单次超时",`${i.defaults?.call_timeout} 秒`)}</dl></div></section>
      <section class="card"><div class="card-h"><h3>${icon("folder")}数据工作区</h3></div><div class="card-b"><p class="small muted" style="margin-top:0">病例、事件、草案与审阅记录保存在：</p><div class="mono" style="overflow-wrap:anywhere;font-size:11px">${esc(i.runs_dir)}</div><div class="hr"></div><p class="small muted">运行目录不纳入 Git。模型密钥不写入运行记录。</p><a href="#/guide" class="btn sm">查看使用指南${icon("chevron")}</a></div></section></div></div>`,crumb("模型与设置"));
  }
  function viewGuide() {
    const steps = [
      ["整理病例信息","使用脱敏编号，填写明确的决策问题和已核对的患者事实。缺失信息单独列出；支持表单录入或导入 JSON 文件。"],
      ["准备可追溯的证据","导入包含来源、版本、原文与适用角色的证据库。点击条目查看原文；合成证据用于体验离线流程。"],
      ["选择模式并开始","无需密钥即可体验六种演示场景。连接模型时填写服务地址、模型与密钥，并按需调整并发、检索条数和修订上限。"],
      ["观察专家协作","A、B、C 分别独立判断，D 整合草案。实时监控展示每次调用、并行耗时和审核结论。"],
      ["追踪分歧与修订","各专家审核其负责部分。出现异议时，由 D 汇总修改，受影响的专家再审；共同方案变化会触发全部专家复核。"],
      ["审阅结果并留档","查看最终建议、证据引用与版本差异，记录人工审阅意见。支持导出 Markdown、JSON，以及打印报告。"]
    ];
    setView(`<div class="page-h"><div><h1 class="h1">从病例到有依据的判断</h1><p class="lead">六个步骤，了解你的 VTE 多专家工作台。</p></div><button class="btn primary" data-action="quick-demo" data-s="targeted">${icon("play")}体验协作演示</button></div><div class="guide-flow"><b>病例 + 证据</b>${icon("chevron")}<b>A / B / C 并行初判</b>${icon("chevron")}<b>D 汇总</b>${icon("refresh")}<b>分工审核与定向修订</b>${icon("chevron")}<b>医师审阅</b></div><div class="guide-grid">${steps.map(([title,text],n) => `<section class="card guide-step"><span class="number">0${n+1}</span><h3>${title}</h3><p>${text}</p></section>`).join("")}</div><div class="notice" style="margin-top:22px">${icon("info")}<div>演示中的判断与证据均为合成内容，用于展示软件流程。工作流审核通过表示 Agent 对当前草案无待处理异议，最终决定由医师作出。</div></div>`,crumb("使用指南"));
  }

  /* ================= actions ================= */
  const actions = {
    reload: () => onRoute(),
    "profile-save": () => { saveWizard(); toast("模型配置已保存；临时密钥仅在本页面会话有效", "ok"); viewSettings(); },
    "clear-key": () => { apiKey = ""; viewSettings(); toast("临时密钥已清除"); },
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
    "reuse-case": () => { S.w = S.w || loadWizard(); S.w.case = caseFromJSON(S.run.case || {}); delete S.w.jsonDraft; S.w.jsonError = false; S.w.step = 0; S.w.caseMode = "form"; S.w.useDemoData = false; saveWizard(); location.hash = "#/new"; toast("已载入病例，可修改后重新审核", "ok"); },
    decision: (el) => { S.signDecision = el.dataset.d; $$("#decisions .decision").forEach((b) => b.classList.toggle("on", b === el)); },
    sign: async (el) => {
      const reviewer = $("#sign-name").value.trim(), comment = $("#sign-comment").value.trim();
      if (!S.signDecision) return toast("请选择审阅结论", "bad");
      if (!reviewer) return toast("请填写审阅医师", "bad");
      if (S.signDecision !== "accept" && !comment) return toast("请填写审阅意见", "bad");
      el.disabled = true;
      try {
        await api(`/api/runs/${encodeURIComponent(S.run.id)}/signoff`, { body: { decision: S.signDecision, reviewer, comment } });
        localStorage.setItem("vte.reviewer", reviewer);
        S.run = await api(`/api/runs/${encodeURIComponent(S.run.id)}`); S.signDecision = "";
        renderRunBody(); toast("签署已存档", "ok");
      } catch (e) { toast(e.message, "bad"); el.disabled = false; }
    },
    // wizard
    "w-step": (el) => { S.w.step = +el.dataset.i; saveWizard(); renderWizard(); },
    "w-prev": () => { S.w.step = Math.max(0, S.w.step - 1); saveWizard(); renderWizard(); },
    "w-next": () => { S.w.step = Math.min(2, S.w.step + 1); saveWizard(); renderWizard(); },
    "w-reset": () => { if (!confirm("清空当前录入的病例、证据与配置？")) return; S.w = defaultWizard(); S.w.settings = defaultsToSettings(); apiKey = ""; saveWizard(); renderWizard(); },
    "case-mode": (el) => { if (S.w.jsonError && el.dataset.m === "form") return toast("请先修正 JSON，避免丢失正在编辑的内容", "bad"); S.w.caseMode = el.dataset.m; saveWizard(); renderWizard(); },
    "fact-add": () => { S.w.case.facts.push(["", ""]); saveWizard(); renderWizard(); const ins = $$("[data-input=fact-k]"); ins[ins.length - 1]?.focus(); },
    "fact-del": (el) => { S.w.case.facts.splice(+el.dataset.i, 1); if (!S.w.case.facts.length) S.w.case.facts.push(["", ""]); saveWizard(); renderWizard(); },
    "fact-quick": (el) => {
      const k = el.dataset.k, f = S.w.case.facts;
      let i = f.findIndex(([x]) => x === k);
      if (i < 0) { i = f.findIndex(([x, v]) => !x && !v); if (i < 0) { f.push([k, ""]); i = f.length - 1; } else f[i][0] = k; }
      saveWizard(); renderWizard(); $(`[data-input=fact-v][data-i="${i}"]`)?.focus();
    },
    "miss-del": (el) => { S.w.case.missing.splice(+el.dataset.i, 1); saveWizard(); renderWizard(); },
    "case-demo": async () => { try { const d = await api("/api/demo"); S.w.case = caseFromJSON(d.case); delete S.w.jsonDraft; S.w.jsonError = false; saveWizard(); renderWizard(); toast("已载入演示病例（合成）", "ok"); } catch (e) { toast(e.message, "bad"); } },
    "case-clear": () => { S.w.case = blankCase(); delete S.w.jsonDraft; S.w.jsonError = false; saveWizard(); renderWizard(); },
    "ev-demo": async () => { try { const d = await api("/api/demo"); await setEvidence(d.evidence, "内置演示证据（合成）"); } catch (e) { toast(e.message, "bad"); } },
    "ev-clear": () => { S.w.evidence = null; S.w.evidenceName = ""; S.w.evidenceCheck = null; S.evMap = {}; saveWizard(); renderWizard(); },
    "w-mode": (el) => { S.w.mode = el.dataset.m; saveWizard(); renderWizard(); },
    "w-scenario": (el) => { S.w.scenario = el.dataset.s; saveWizard(); $$("[data-action=w-scenario]").forEach((b) => b.classList.toggle("on", b === el)); },
    start: async (el) => {
      const w = S.w;
      if (!startChecks().ok) return toast("请先完成启动前检查", "bad");
      const body = { mode: w.mode, settings: w.settings };
      if (w.mode === "demo") {
        body.scenario = w.scenario; body.pace = w.pace;
        if (!w.useDemoData) { body.case = buildCase(); if (w.evidence) body.evidence = w.evidence; }
      } else {
        body.case = buildCase(); body.evidence = w.evidence;
        body.llm = { base_url: w.llm.base_url, model: w.llm.model, api_key: apiKey, role_models: w.llm.role_models };
      }
      el.disabled = true; el.innerHTML = `<span class="spinner" style="border-color:rgba(255,255,255,.4);border-top-color:#fff"></span>正在启动…`;
      try { const { id } = await api("/api/runs", { body }); location.hash = `#/run/${id}`; }
      catch (e) { toast(e.message, "bad"); renderWizard(); }
    },
  };
  async function setEvidence(arr, name) {
    const res = await api("/api/validate", { body: { evidence: arr } });
    if (!res.evidence?.ok) { toast(`证据库格式错误：${res.evidence?.error}`, "bad"); return; }
    S.w.evidence = arr; S.w.evidenceName = name; S.w.evidenceCheck = res.evidence;
    S.evMap = Object.fromEntries(arr.map((d) => [d.id, d]));
    saveWizard(); renderWizard(); toast(`已导入 ${res.evidence.count} 条证据`, "ok");
  }
  const readFile = (file) => new Promise((ok, bad) => { const fr = new FileReader(); fr.onload = () => ok(String(fr.result).replace(/^\uFEFF/, "")); fr.onerror = bad; fr.readAsText(file, "utf-8"); });
  async function importEvidenceFile(file) {
    if (!file) return;
    try { const data = JSON.parse(await readFile(file)); if (!Array.isArray(data)) throw new Error("证据库应为 JSON 数组"); await setEvidence(data, file.name); }
    catch (e) { toast(e.message, "bad"); }
  }

  const inputs = {
    "hist-q": (el) => { S.hist.q = el.value; $("#hist-body").innerHTML = runRows(filterRuns()); },
    case: (el) => { delete S.w.jsonDraft; S.w.case[el.dataset.k] = el.value; saveWizard(); refreshCaseSide(); },
    "fact-k": (el) => { delete S.w.jsonDraft; S.w.case.facts[+el.dataset.i][0] = el.value; saveWizard(); refreshCaseSide(); },
    "fact-v": (el) => { delete S.w.jsonDraft; S.w.case.facts[+el.dataset.i][1] = el.value; saveWizard(); refreshCaseSide(); },
    "case-json": (el) => {
      const err = $("#json-err");
      S.w.jsonDraft = el.value;
      try {
        const o = JSON.parse(el.value);
        if (!o || typeof o !== "object" || Array.isArray(o)) throw new Error("应为 JSON 对象");
        S.w.case = caseFromJSON(o); S.w.jsonError = false; saveWizard(); refreshCaseSide();
        err.textContent = "JSON 合法，已同步。"; err.style.color = "var(--ok)";
      } catch (e) { S.w.jsonError = true; saveWizard(); refreshCaseSide(); err.textContent = `JSON 错误：${e.message}`; err.style.color = "var(--bad)"; }
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
    "case-file": async (el) => {
      const f = el.files[0]; if (!f) return;
      try { const o = JSON.parse(await readFile(f)); S.w.case = caseFromJSON(o); delete S.w.jsonDraft; S.w.jsonError = false; S.w.useDemoData = false; saveWizard(); renderWizard(); toast("病例已导入", "ok"); }
      catch (e) { toast(`无法读取病例：${e.message}`, "bad"); }
    },
    "evidence-file": (el) => importEvidenceFile(el.files[0]),
    "use-demo": (el) => { S.w.useDemoData = el.checked; saveWizard(); renderWizard(); },
  };

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
    if (z) { z.classList.remove("over"); importEvidenceFile(e.dataTransfer.files[0]); }
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
    if (parts[0] === "settings") return viewSettings();
    if (parts[0] === "guide") return viewGuide();
    if (parts[0] === "run" && parts[1]) return viewRun(decodeURIComponent(parts[1]), new URLSearchParams(query || "").get("tab"));
    location.hash = "#/";
  }
  async function heartbeat() {
    try { await fetch("/api/info", { cache: "no-store" }).then((r) => { if (!r.ok) throw 0; }); $("#server-state").classList.remove("off"); $("#server-state").lastChild.textContent = "本地服务运行中"; }
    catch { $("#server-state").classList.add("off"); $("#server-state").lastChild.textContent = "本地服务已断开"; }
  }
  async function boot() {
    $$("i[data-icon]").forEach((i) => { i.outerHTML = icon(i.dataset.icon); });
    try { S.info = await api("/api/info"); $("#app-version").textContent = `v${S.info.version} · 提示词 ${S.info.prompt_version}`; }
    catch (e) { toast("无法连接本地服务：" + e.message, "bad"); }
    S.w = loadWizard();
    window.addEventListener("hashchange", onRoute);
    onRoute();
    setInterval(heartbeat, 10000);
  }
  boot();
})();
