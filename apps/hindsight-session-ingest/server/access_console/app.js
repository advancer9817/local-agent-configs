"use strict";
const S = {me: null, data: null, tab: "users", query: "", drawerUser: null};
const LEVELS = [["read", "只读"], ["write", "读写"], ["manage", "管理"]];
const LEVEL_NAME = Object.fromEntries(LEVELS);
const $ = (selector, root = document) => root.querySelector(selector);
const tooltip = document.createElement("div");
tooltip.id = "control-tooltip";
tooltip.className = "control-tooltip";
tooltip.setAttribute("role", "tooltip");
tooltip.hidden = true;
document.body.append(tooltip);
let tooltipAnchor = null;
function hideTooltip() {
  if (tooltipAnchor) tooltipAnchor.removeAttribute("aria-describedby");
  tooltipAnchor = null;
  tooltip.hidden = true;
}
function showTooltip(anchor) {
  hideTooltip();
  if (!anchor || anchor.closest(".drawer-backdrop, .modal-backdrop")) return;
  tooltipAnchor = anchor;
  tooltip.textContent = anchor.dataset.tip;
  tooltip.hidden = false;
  anchor.setAttribute("aria-describedby", tooltip.id);
  const rect = anchor.getBoundingClientRect();
  const box = tooltip.getBoundingClientRect();
  const left = Math.max(8, Math.min(innerWidth - box.width - 8, rect.left + (rect.width - box.width) / 2));
  const top = rect.bottom + box.height + 14 <= innerHeight ? rect.bottom + 6 : rect.top - box.height - 6;
  tooltip.style.left = left + "px";
  tooltip.style.top = Math.max(8, top) + "px";
}
document.addEventListener("pointerover", (event) => {
  const anchor = event.target.closest("[data-tip]");
  if (anchor && !anchor.contains(event.relatedTarget)) showTooltip(anchor);
});
document.addEventListener("pointerout", (event) => {
  if (tooltipAnchor && !tooltipAnchor.contains(event.relatedTarget)) hideTooltip();
});
document.addEventListener("focusin", (event) => showTooltip(event.target.closest("[data-tip]")));
document.addEventListener("focusout", hideTooltip);
document.addEventListener("pointerdown", hideTooltip);
document.addEventListener("keydown", hideTooltip);
document.addEventListener("scroll", hideTooltip, true);
window.addEventListener("resize", hideTooltip);
const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (c) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
const icons = () => lucide.createIcons();
const fmt = (seconds) => seconds ? new Intl.DateTimeFormat("zh-CN", {timeZone: "Asia/Shanghai", year: "numeric", month: "2-digit",
  day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false}).format(new Date(seconds * 1000)) : "—";
const iso = (value) => value ? Date.parse(value) / 1000 : null;
const compact = (n) => n >= 1000 ? (n / 1000).toFixed(n >= 10000 ? 0 : 1).replace(/\.0$/, "") + "k" : String(n ?? 0);
function ago(seconds) {
  if (!seconds) return "从未";
  const diff = Date.now() / 1000 - seconds;
  if (diff < 60) return "刚刚";
  if (diff < 3600) return Math.floor(diff / 60) + " 分钟前";
  if (diff < 86400) return Math.floor(diff / 3600) + " 小时前";
  if (diff < 86400 * 30) return Math.floor(diff / 86400) + " 天前";
  return fmt(seconds).slice(0, 10);
}
// Native palette: chart-1 blue, brand teal, chart-4 amber, chart-3 violet.
const LEVEL_COLOR = {read: "#2c82f5", write: "#009296", manage: "#f59e0b", admin: "#8b5cf6"};

function head(title, subtitle, actions = "") {
  return `<div class="page-head"><div class="titles"><h1>${esc(title)}</h1>${subtitle ? `<p>${subtitle}</p>` : ""}</div>${actions}</div>`;
}
function stat(icon, label, value, small = false) {
  return `<div class="stat"><span class="ic"><i data-lucide="${icon}"></i></span><div style="min-width:0">
    <div class="label">${esc(label)}</div><div class="value ${small ? "small" : ""}">${value}</div></div></div>`;
}
function composition(title, parts) {
  const total = parts.reduce((sum, p) => sum + p.n, 0);
  const pct = (n) => total ? Math.round(n * 100 / total) : 0;
  return `<div class="composition"><div class="head"><h4>${esc(title)}</h4><span class="total">${total}</span></div>
    <div class="bar">${parts.filter((p) => p.n).map((p) => `<span title="${esc(p.label)}: ${p.n}" style="width:${p.n * 100 / total}%;background:${p.color}"></span>`).join("")}</div>
    <div class="legend">${parts.map((p) => `<div><div class="key"><span class="sq" style="background:${p.color}"></span>${esc(p.label)}</div>
      <div><span class="n">${p.n}</span><span class="pct">${pct(p.n)}%</span></div></div>`).join("")}</div></div>`;
}
function meter(value, max) {
  if (!value) return `<span class="muted">空</span>`;
  return `<div class="meter"><div class="track"><div class="fill" style="width:${Math.max(4, value * 100 / Math.max(max, 1))}%"></div></div><span class="val">${value}</span></div>`;
}
const emptyRow = (cols, icon, text) => `<tr><td colspan="${cols}" class="empty"><i data-lucide="${icon}"></i>${esc(text)}</td></tr>`;

async function api(path, options = {}) {
  const init = {method: options.method || "GET", headers: {"Content-Type": "application/json"}};
  if (init.method !== "GET") init.headers["X-CSRF-Token"] = S.me?.csrf || "";
  if (options.body !== undefined) init.body = JSON.stringify(options.body);
  const response = await fetch("/access/api" + path, init);
  if (response.status === 401) { location.replace("/access/login?next=/access/"); throw new Error("请先登录"); }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || ("请求失败 " + response.status));
  return data;
}

function toast(message, error = false) {
  const node = document.createElement("div");
  node.className = "toast" + (error ? " error" : "");
  node.innerHTML = `<i data-lucide="${error ? "circle-alert" : "check"}"></i><span>${esc(message)}</span>`;
  $("#toasts").append(node); icons();
  setTimeout(() => node.remove(), error ? 5000 : 2600);
}

async function act(work, message) {
  try { const result = await work(); if (message) toast(message); await refresh(); return result; }
  catch (e) { toast(e.message, true); return null; }
}

function modal({title, body, confirm = "确定", danger = false, onConfirm, cancel = "取消"}) {
  hideTooltip();
  closeBankPicker();
  const overlay = $("#overlay");
  overlay.innerHTML = `<div class="modal-backdrop"></div><div class="modal" role="dialog" aria-modal="true">
    <header><h2>${esc(title)}</h2><button class="icon-btn" data-close data-tip="关闭" aria-label="关闭"><i data-lucide="x"></i></button></header>
    <div class="body">${body}</div>
    <footer>${cancel ? `<button class="btn" data-close>${esc(cancel)}</button>` : ""}
      ${onConfirm ? `<button class="btn ${danger ? "danger solid" : "primary"}" data-ok>${esc(confirm)}</button>` : ""}</footer></div>`;
  icons();
  const close = () => { hideTooltip(); closeBankPicker(); overlay.innerHTML = ""; };
  overlay.querySelectorAll("[data-close], .modal-backdrop").forEach((node) => node.onclick = close);
  const ok = $("[data-ok]", overlay);
  if (ok) ok.onclick = async () => {
    ok.disabled = true;
    const keep = await onConfirm($(".modal", overlay));
    if (keep !== false) close(); else ok.disabled = false;
  };
  const first = $(".modal input, .modal select", overlay); if (first) first.focus();
  bindCopy(); bindSegments(overlay); bindBankPickers(overlay);
  return overlay;
}

function segmented(name, value, options = LEVELS) {
  return `<div class="segmented" data-seg="${esc(name)}">${options.map(([key, label]) =>
    `<button type="button" data-value="${key}" class="${key === value ? "on" : ""}">${esc(label)}</button>`).join("")}</div>`;
}
function bindSegments(root, onChange) {
  root.querySelectorAll(".segmented").forEach((seg) => seg.querySelectorAll("button").forEach((button) => button.onclick = () => {
    seg.querySelectorAll("button").forEach((b) => b.classList.toggle("on", b === button));
    seg.dataset.current = button.dataset.value;
    if (onChange) onChange(seg.dataset.seg, button.dataset.value);
  }));
}
const segValue = (root, name) => {
  const seg = $(`[data-seg="${name}"]`, root);
  return seg.dataset.current || $("button.on", seg)?.dataset.value || "";
};
const chip = (bank, level) => `<span class="chip ${level}" title="${esc(LEVEL_NAME[level] || level)}">${esc(bank)} · ${esc(LEVEL_NAME[level] || level)}</span>`;
const randomPassword = () => Array.from(crypto.getRandomValues(new Uint8Array(12)), (b) => "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"[b % 56]).join("");

async function refresh() {
  S.me = await api("/me");
  if (S.me.role === "admin") S.data = await api("/state");
  render();
}

function render() {
  hideTooltip();
  closeBankPicker();
  const admin = S.me.role === "admin";
  const tabs = admin ? [["users", "users", "账号"], ["banks", "database", "数据仓"], ["tokens", "key-round", "令牌"], ["settings", "settings-2", "设置与审计"]]
    : [["mine", "user-round", "我的权限"]];
  if (!tabs.some(([key]) => key === S.tab)) S.tab = tabs[0][0];
  $("#tabs").innerHTML = tabs.map(([key, icon, label]) =>
    `<button class="tab ${key === S.tab ? "active" : ""}" data-tab="${key}" title="${label}" ${key === S.tab ? 'aria-current="page"' : ""}><i data-lucide="${icon}"></i><span class="label">${label}</span></button>`).join("");
  $("#tabs").querySelectorAll("[data-tab]").forEach((button) => button.onclick = () => { S.tab = button.dataset.tab; render(); });
  const on = S.me.auth_enabled;
  $("#auth-chip").className = "auth-pill " + (on ? "on" : "off");
  $("#auth-chip").innerHTML = `<i data-lucide="${on ? "lock" : "lock-open"}"></i><span class="label">API 鉴权${on ? "已开启" : "已关闭"}</span>`;
  $("#auth-chip").title = on ? "API 鉴权已开启" : "API 鉴权已关闭";
  $("#who").textContent = S.me.username + (admin ? "（管理员）" : "");
  const views = {users: viewUsers, banks: viewBanks, tokens: viewTokens, settings: viewSettings, mine: viewMine};
  const denied = new URLSearchParams(location.search).get("denied");
  $("#main").innerHTML = `<div class="page">${denied ? `<div class="alert"><i data-lucide="shield-alert"></i><span>${esc(denied)}</span></div>` : ""}${views[S.tab]()}</div>`;
  bindView();
  icons();
}

function activeTokens(tokens) {
  return tokens.filter((t) => !t.revoked && !(t.expires && t.expires * 1000 < Date.now()));
}

function viewUsers() {
  const q = S.query.toLowerCase();
  const users = S.data.users.filter((u) => !q || u.username.toLowerCase().includes(q) || (u.note || "").toLowerCase().includes(q)
    || u.grants.some((g) => g.bank_id.toLowerCase().includes(q)));
  const rows = users.map((u) => `<tr class="clickable" data-user="${u.id}">
    <td><span class="cell-title">${esc(u.username)}</span>${u.note ? `<span class="cell-sub">${esc(u.note)}</span>` : ""}</td>
    <td>${u.role === "admin" ? `<span class="chip admin">管理员</span>` : `<span class="chip">普通账号</span>`}</td>
    <td><span class="status"><span class="dot ${u.disabled ? "off" : ""}"></span>${u.disabled ? "已停用" : "正常"}</span></td>
    <td>${u.role === "admin" ? `<span class="muted">全部数据仓</span>` : (u.grants.map((g) => chip(g.bank_id, g.permission)).join("") || `<span class="muted">无</span>`)}</td>
    <td class="num">${u.active_tokens}</td>
    <td class="muted nowrap" title="${fmt(u.last_login)}">${ago(u.last_login)}</td>
    <td class="actions">
      <button class="icon-btn sm" data-issue="${u.id}" data-tip="发放令牌" aria-label="发放令牌"><i data-lucide="key-round"></i></button>
      <button class="icon-btn sm" data-open="${u.id}" data-tip="权限与设置" aria-label="权限与设置"><i data-lucide="sliders-horizontal"></i></button>
      <button class="icon-btn sm danger" data-delete="${u.id}" data-tip="删除账号" aria-label="删除账号"><i data-lucide="trash-2"></i></button>
    </td></tr>`).join("");
  const all = S.data.users, grants = all.flatMap((u) => u.role === "admin" ? [] : u.grants);
  const level = (key) => grants.filter((g) => g.permission === key).length;
  const overview = `<div class="panel"><div class="stats">
      ${stat("users", "账号", all.length)}
      ${stat("database", "数据仓", bankIndex().size)}
      ${stat("key-round", "有效令牌", activeTokens(S.data.tokens).length)}
      ${stat(S.data.auth_enabled ? "lock" : "lock-open", "API 鉴权", S.data.auth_enabled ? "已开启" : "已关闭", true)}</div>
    <div class="compositions">
      ${composition("账号构成", [{label: "管理员", n: all.filter((u) => u.role === "admin" && !u.disabled).length, color: LEVEL_COLOR.admin},
        {label: "普通账号", n: all.filter((u) => u.role !== "admin" && !u.disabled).length, color: LEVEL_COLOR.write},
        {label: "已停用", n: all.filter((u) => u.disabled).length, color: "#6c7586"}])}
      ${composition("授权级别", [{label: "只读", n: level("read"), color: LEVEL_COLOR.read},
        {label: "读写", n: level("write"), color: LEVEL_COLOR.write}, {label: "管理", n: level("manage"), color: LEVEL_COLOR.manage}])}
    </div></div>`;
  return head("账号", `${all.length} 个账号 · ${grants.length} 条数据仓授权`, `<button class="btn primary" id="new-user"><i data-lucide="user-plus"></i>新建账号</button>`)
    + overview
    + `<div class="toolbar"><label class="search"><i data-lucide="search"></i><input class="input" id="search" placeholder="搜索用户名、备注或数据仓" value="${esc(S.query)}" aria-label="搜索账号"></label></div>
    <div class="table-wrap"><table><thead><tr><th>用户名</th><th>角色</th><th>状态</th><th>数据仓权限</th><th>有效令牌</th><th>最近登录</th><th></th></tr></thead>
    <tbody>${rows || emptyRow(7, "search-x", "没有匹配的账号")}</tbody></table></div>`;
}

const bankMenu = document.createElement("div");
bankMenu.id = "bank-options";
bankMenu.className = "bank-menu";
bankMenu.setAttribute("role", "listbox");
bankMenu.setAttribute("aria-label", "数据仓");
bankMenu.hidden = true;
document.body.append(bankMenu);
let currentBankPicker = null;

function bankPicker(id, placeholder) {
  return `<div class="bank-picker"><input class="input" id="${id}" role="combobox" autocomplete="off"
    aria-label="数据仓 ID" aria-autocomplete="list" aria-expanded="false" aria-controls="bank-options" placeholder="${esc(placeholder)}">
    <button type="button" class="icon-btn bank-toggle" aria-label="展开数据仓选项" aria-expanded="false" aria-controls="bank-options">
      <i data-lucide="chevron-down"></i></button></div>`;
}
function closeBankPicker() {
  if (currentBankPicker) {
    currentBankPicker.input.setAttribute("aria-expanded", "false");
    currentBankPicker.input.removeAttribute("aria-activedescendant");
    currentBankPicker.toggle.setAttribute("aria-expanded", "false");
  }
  currentBankPicker = null;
  bankMenu.hidden = true;
}
function paintBankOptions() {
  const picker = currentBankPicker;
  const query = picker.input.value.trim().toLocaleLowerCase();
  picker.options = (S.data?.banks || []).filter(bank =>
    [bank.bank_id, bank.name].some(value => String(value || "").toLocaleLowerCase().includes(query)));
  picker.active = Math.min(picker.active, picker.options.length - 1);
  bankMenu.innerHTML = picker.options.map((bank, index) => `<div class="bank-option ${index === picker.active ? "active" : ""}"
    role="option" aria-selected="${index === picker.active}" id="bank-option-${index}" data-bank-option="${index}">
    <span>${esc(bank.bank_id)}</span>${bank.name && bank.name !== bank.bank_id ? `<small>${esc(bank.name)}</small>` : ""}</div>`).join("")
    || `<div class="bank-empty">没有匹配的数据仓</div>`;
  if (picker.active >= 0) picker.input.setAttribute("aria-activedescendant", "bank-option-" + picker.active);
  else picker.input.removeAttribute("aria-activedescendant");
  const rect = picker.input.closest(".bank-picker").getBoundingClientRect();
  const below = innerHeight - rect.bottom - 12;
  const above = rect.top - 12;
  const upwards = below < 160 && above > below;
  bankMenu.style.width = Math.min(rect.width, innerWidth - 16) + "px";
  bankMenu.style.left = Math.max(8, Math.min(rect.left, innerWidth - rect.width - 8)) + "px";
  bankMenu.style.maxHeight = Math.max(0, Math.min(240, upwards ? above : below)) + "px";
  bankMenu.style.top = (upwards ? rect.top - bankMenu.getBoundingClientRect().height - 4 : rect.bottom + 4) + "px";
  bankMenu.querySelector(".active")?.scrollIntoView({block: "nearest"});
}
function openBankPicker(input, toggle) {
  if (currentBankPicker?.input !== input) closeBankPicker();
  currentBankPicker = {input, toggle, options: [], active: -1};
  hideTooltip();
  bankMenu.hidden = false;
  input.setAttribute("aria-expanded", "true");
  toggle.setAttribute("aria-expanded", "true");
  paintBankOptions();
}
function chooseBank(index) {
  const picker = currentBankPicker;
  const bank = picker?.options[index];
  if (!bank) return;
  picker.input.value = bank.bank_id;
  picker.input.focus();
  closeBankPicker();
}
function bindBankPickers(root) {
  root.querySelectorAll(".bank-picker").forEach(element => {
    const input = $("input", element), toggle = $("button", element);
    input.addEventListener("focus", () => openBankPicker(input, toggle));
    input.addEventListener("click", () => { if (!currentBankPicker) openBankPicker(input, toggle); });
    input.addEventListener("input", () => openBankPicker(input, toggle));
    input.addEventListener("keydown", event => {
      if (event.key === "Escape" || event.key === "Tab") {
        closeBankPicker();
        return;
      }
      if (event.key === "ArrowDown" || event.key === "ArrowUp") {
        event.preventDefault();
        if (!currentBankPicker) openBankPicker(input, toggle);
        const count = currentBankPicker.options.length;
        currentBankPicker.active = !count ? -1 : currentBankPicker.active < 0
          ? (event.key === "ArrowDown" ? 0 : count - 1)
          : (currentBankPicker.active + (event.key === "ArrowDown" ? 1 : -1) + count) % count;
        paintBankOptions();
      } else if (event.key === "Enter" && currentBankPicker) {
        event.preventDefault();
        chooseBank(currentBankPicker.active);
      }
    });
    toggle.addEventListener("pointerdown", event => event.preventDefault());
    toggle.addEventListener("click", () => {
      const wasOpen = currentBankPicker?.input === input;
      input.focus();
      if (wasOpen) closeBankPicker(); else openBankPicker(input, toggle);
    });
  });
}
bankMenu.addEventListener("pointerdown", event => event.preventDefault());
bankMenu.addEventListener("click", event => {
  const option = event.target.closest("[data-bank-option]");
  if (option) chooseBank(Number(option.dataset.bankOption));
});
document.addEventListener("pointerdown", event => {
  if (!event.target.closest(".bank-picker, .bank-menu")) closeBankPicker();
});
document.addEventListener("focusin", event => {
  if (!event.target.closest(".bank-picker")) closeBankPicker();
});
document.addEventListener("scroll", event => {
  if (event.target !== bankMenu && !bankMenu.contains(event.target)) closeBankPicker();
}, true);
window.addEventListener("resize", closeBankPicker);

function newUser() {
  const password = randomPassword();
  modal({title: "新建账号", confirm: "创建", body: `<div class="grid-form">
      <label for="nu-name">用户名</label><input class="input" id="nu-name" autocomplete="off">
      <label for="nu-pass">初始密码</label><div class="row"><input class="input" id="nu-pass" value="${password}" style="flex:1">
        <button class="icon-btn" id="nu-gen" data-tip="重新生成" aria-label="重新生成"><i data-lucide="refresh-cw"></i></button></div>
      <label>角色</label>${segmented("role", "user", [["user", "普通账号"], ["admin", "管理员"]])}
      <label for="nu-bank">数据仓</label>${bankPicker("nu-bank", "可留空，稍后授权")}
      <label>权限</label>${segmented("perm", "write")}
      <label for="nu-note">备注</label><input class="input" id="nu-note" maxlength="200"></div>`,
    onConfirm: async (root) => {
      const body = {username: $("#nu-name", root).value.trim(), password: $("#nu-pass", root).value, role: segValue(root, "role"),
        note: $("#nu-note", root).value.trim(), bank_id: $("#nu-bank", root).value.trim(), permission: segValue(root, "perm")};
      const created = await act(() => api("/users", {method: "POST", body}), "已创建账号 " + body.username);
      if (!created) return false;
      setTimeout(() => modal({title: "账号已创建", cancel: "关闭", body: `<p>请把初始密码安全地交给 ${esc(body.username)}，此处只显示一次。</p>
        <div class="secret"><code>${esc(body.password)}</code><button class="icon-btn sm" data-copy="${esc(body.password)}" data-tip="复制" aria-label="复制"><i data-lucide="copy"></i></button></div>`}), 0);
    }});
  $("#nu-gen").onclick = () => { $("#nu-pass").value = randomPassword(); };
}

function bindCopy() {
  document.querySelectorAll("[data-copy]").forEach((button) => button.onclick = async () => {
    try { await navigator.clipboard.writeText(button.dataset.copy); toast("已复制"); }
    catch (e) { toast("浏览器不允许复制，请手动选中", true); }
  });
}

function issueToken(userId) {
  const user = S.data.users.find((u) => u.id === userId);
  modal({title: "给 " + user.username + " 发放令牌", confirm: "发放", body: `<div class="grid-form">
      <label for="tk-name">名称</label><input class="input" id="tk-name" placeholder="例如 办公室 Windows / Codex">
      <label for="tk-days">有效期</label><select class="input" id="tk-days"><option value="30">30 天</option><option value="90" selected>90 天</option>
        <option value="365">1 年</option><option value="">永不过期</option></select>
      <label>权限上限</label>${segmented("cap", "", [["", "跟随账号"], ["read", "只读"], ["write", "读写"]])}</div>`,
    onConfirm: async (root) => {
      const body = {name: $("#tk-name", root).value.trim(), days: Number($("#tk-days", root).value) || null, cap: segValue(root, "cap") || null};
      const issued = await act(() => api(`/users/${userId}/tokens`, {method: "POST", body}), "令牌已发放");
      if (!issued) return false;
      setTimeout(() => showToken(issued), 0);
    }});
}

function showToken(issued) {
  modal({title: "令牌已发放", cancel: "我已保存", body: `<p>令牌只显示这一次，关闭后无法再查看。</p>
    <div class="secret"><code>${esc(issued.token)}</code><button class="icon-btn sm" data-copy="${esc(issued.token)}" data-tip="复制" aria-label="复制"><i data-lucide="copy"></i></button></div>
    <p class="note">客户端写入 connection.json 的 <span class="mono">mcp_token</span> 字段。</p>`});
}

function tokenStatus(t) {
  if (t.revoked) return `<span class="status"><span class="dot off"></span>已吊销</span>`;
  if (t.expires && t.expires * 1000 < Date.now()) return `<span class="status"><span class="dot bad"></span>已过期</span>`;
  return `<span class="status"><span class="dot"></span>有效</span>`;
}

function openDrawer(userId) {
  hideTooltip();
  closeBankPicker();
  const user = S.data.users.find((u) => u.id === userId);
  const root = $("#drawer");
  if (!user) { S.drawerUser = null; root.innerHTML = ""; return; }
  S.drawerUser = userId;
  const tokens = S.data.tokens.filter((t) => t.user_id === userId);
  const grants = user.grants.map((g) => `<div class="list-item"><i data-lucide="database"></i><span class="grow mono">${esc(g.bank_id)}</span>
      ${segmented("grant:" + g.bank_id, g.permission)}
      <button class="icon-btn sm danger" data-revoke-grant="${esc(g.bank_id)}" data-tip="移除权限" aria-label="移除权限"><i data-lucide="x"></i></button></div>`).join("");
  const tokenRows = tokens.map((t) => `<div class="list-item"><i data-lucide="key-round"></i><span class="grow"><strong>${esc(t.name)}</strong>
      <span class="mono muted">${esc(t.prefix)}…</span><br><span class="muted">${t.cap ? "上限 " + esc(LEVEL_NAME[t.cap]) + " · " : ""}到期 ${t.expires ? fmt(t.expires) : "永不"} · 最近使用 ${fmt(t.last_used)}</span></span>
      ${tokenStatus(t)}${t.revoked ? "" : `<button class="icon-btn sm danger" data-revoke-token="${t.id}" data-tip="吊销" aria-label="吊销"><i data-lucide="ban"></i></button>`}</div>`).join("");
  root.innerHTML = `<div class="drawer-backdrop" data-close-drawer></div><aside class="drawer" role="dialog" aria-label="账号设置">
    <header><h2>${esc(user.username)}</h2>${user.role === "admin" ? `<span class="chip admin">管理员</span>` : ""}
      <button class="icon-btn" data-close-drawer data-tip="关闭" aria-label="关闭"><i data-lucide="x"></i></button></header>
    <div class="body">
      <div class="section"><h3><i data-lucide="user-round-cog"></i>基本信息</h3><div class="grid-form">
        <label>角色</label>${segmented("role", user.role, [["user", "普通账号"], ["admin", "管理员"]])}
        <label>账号状态</label><label class="row"><span class="switch"><input type="checkbox" id="dr-enabled" ${user.disabled ? "" : "checked"}><span></span></span>${user.disabled ? "已停用" : "可登录、令牌有效"}</label>
        <label for="dr-note">备注</label><div class="row"><input class="input" id="dr-note" value="${esc(user.note)}" maxlength="200" style="flex:1">
          <button class="icon-btn" id="dr-save-note" data-tip="保存备注" aria-label="保存备注"><i data-lucide="save"></i></button></div>
        <label>密码</label><div>${userId === S.me.id
          ? `<button class="btn" id="dr-own-password"><i data-lucide="key-round"></i>修改密码</button>`
          : `<button class="btn" id="dr-reset"><i data-lucide="rotate-ccw"></i>重置密码</button>`}</div></div></div>
      <div class="section"><h3><i data-lucide="database"></i>数据仓权限</h3>
        ${user.role === "admin" ? `<p class="muted">管理员可以访问全部数据仓。</p>` : (grants || `<p class="muted">尚未授权任何数据仓，此账号看不到任何数据。</p>`)}
        <div class="grant-form">${bankPicker("dr-bank", "数据仓 ID")}
          <div class="grant-actions">${segmented("new-grant", "write")}<button class="btn" id="dr-add-grant"><i data-lucide="plus"></i>授权</button></div></div></div>
      <div class="section"><h3><i data-lucide="key-round"></i>访问令牌</h3>${tokenRows || `<p class="muted">没有令牌。</p>`}
        <div class="row" style="margin-top:10px"><button class="btn primary" id="dr-issue"><i data-lucide="key-round"></i>发放令牌</button></div></div>
    </div></aside>`;
  root.querySelectorAll("[data-close-drawer]").forEach((node) => node.onclick = () => {
    hideTooltip(); closeBankPicker(); S.drawerUser = null; root.innerHTML = "";
  });
  bindBankPickers(root);
  bindSegments(root, (name, value) => {
    if (name === "role") act(() => api(`/users/${userId}`, {method: "PATCH", body: {role: value}}), "角色已更新");
    else if (name.startsWith("grant:")) act(() => api(`/users/${userId}/grants`, {method: "PUT", body: {bank_id: name.slice(6), permission: value}}), "权限已更新");
  });
  $("#dr-enabled").onchange = (e) => act(() => api(`/users/${userId}`, {method: "PATCH", body: {disabled: !e.target.checked}}), e.target.checked ? "账号已启用" : "账号已停用");
  $("#dr-save-note").onclick = () => act(() => api(`/users/${userId}`, {method: "PATCH", body: {note: $("#dr-note").value.trim()}}), "备注已保存");
  $("#dr-add-grant").onclick = () => {
    const bank = $("#dr-bank").value.trim();
    if (!bank) { toast("请填写数据仓 ID", true); return; }
    act(() => api(`/users/${userId}/grants`, {method: "PUT", body: {bank_id: bank, permission: segValue(root, "new-grant")}}), "已授权 " + bank);
  };
  root.querySelectorAll("[data-revoke-grant]").forEach((b) => b.onclick = () => act(() =>
    api(`/users/${userId}/grants/${encodeURIComponent(b.dataset.revokeGrant)}`, {method: "DELETE"}), "已移除权限"));
  root.querySelectorAll("[data-revoke-token]").forEach((b) => b.onclick = () => revokeToken(Number(b.dataset.revokeToken)));
  $("#dr-issue").onclick = () => issueToken(userId);
  if (userId === S.me.id) $("#dr-own-password").onclick = changeOwnPassword;
  else $("#dr-reset").onclick = () => {
    const password = randomPassword();
    modal({title: "重置 " + user.username + " 的密码", confirm: "重置", danger: true, body: `<p>重置后该账号的登录会话全部失效。新密码：</p>
      <div class="secret"><code>${password}</code><button class="icon-btn sm" data-copy="${password}" data-tip="复制" aria-label="复制"><i data-lucide="copy"></i></button></div>`,
      onConfirm: () => act(() => api(`/users/${userId}`, {method: "PATCH", body: {password}}), "密码已重置")});
  };
  icons();
}

function revokeToken(id) {
  modal({title: "吊销令牌", confirm: "吊销", danger: true, body: `<p>使用该令牌的客户端会立即失去访问权限，此操作不能撤销。</p>`,
    onConfirm: () => act(() => api(`/tokens/${id}`, {method: "DELETE"}), "令牌已吊销")});
}

function bankIndex() {
  const known = new Map(S.data.banks.map((b) => [b.bank_id, b]));
  S.data.users.forEach((u) => u.grants.forEach((g) => { if (!known.has(g.bank_id)) known.set(g.bank_id, {bank_id: g.bank_id, name: "", pending: true}); }));
  return known;
}

function bankName(bank) {
  const named = bank.name && bank.name !== bank.bank_id;
  return `<span class="cell-title">${esc(named ? bank.name : bank.bank_id)}</span>${named ? `<span class="cell-sub">${esc(bank.bank_id)}</span>` : ""}`;
}

function viewBanks() {
  const known = bankIndex();
  const admins = S.data.users.filter((u) => u.role === "admin" && !u.disabled).map((u) => u.username);
  const max = Math.max(0, ...[...known.values()].map((b) => b.fact_count || 0));
  const rows = [...known.values()].sort((a, b) => (b.fact_count || 0) - (a.fact_count || 0) || a.bank_id.localeCompare(b.bank_id)).map((bank) => {
    const holders = S.data.users.filter((u) => u.role !== "admin").flatMap((u) => u.grants.filter((g) => g.bank_id === bank.bank_id)
      .map((g) => `<span class="chip ${g.permission}">${esc(u.username)} · ${esc(LEVEL_NAME[g.permission])}</span>`));
    return `<tr><td>${bankName(bank)}</td>
      <td>${bank.pending ? `<span class="muted">尚未创建</span>` : meter(bank.fact_count || 0, max)}</td>
      <td class="muted nowrap" title="${fmt(iso(bank.last_write_at))}">${bank.pending ? "—" : ago(iso(bank.last_write_at))}</td>
      <td>${holders.join("") || `<span class="muted">仅管理员</span>`}</td></tr>`;
  }).join("");
  return head("数据仓", `${known.size} 个数据仓 · 管理员 ${admins.map(esc).join("、") || "—"} 可访问全部`)
    + `<div class="table-wrap"><table><thead><tr><th>数据仓</th><th>记忆</th><th>最近活动</th><th>已授权账号</th></tr></thead>
    <tbody>${rows || emptyRow(4, "database", "没有数据仓")}</tbody></table></div>`;
}

function tokenTable(tokens, showUser) {
  const rows = tokens.map((t) => `<tr>${showUser ? `<td class="cell-title">${esc(t.username)}</td>` : ""}<td>${esc(t.name)}</td><td class="mono nowrap">${esc(t.prefix)}…</td>
    <td>${t.cap ? `<span class="chip ${t.cap}">${esc(LEVEL_NAME[t.cap])}</span>` : `<span class="muted">跟随账号</span>`}</td>
    <td class="muted nowrap">${fmt(t.created)}</td><td class="muted nowrap">${t.expires ? fmt(t.expires) : "永不"}</td>
    <td class="muted nowrap" title="${fmt(t.last_used)}">${ago(t.last_used)}</td>
    <td>${tokenStatus(t)}</td><td class="actions">${t.revoked ? "" : `<button class="icon-btn sm danger" data-revoke-token="${t.id}" data-tip="吊销" aria-label="吊销"><i data-lucide="ban"></i></button>`}</td></tr>`).join("");
  return `<div class="table-wrap"><table><thead><tr>${showUser ? "<th>账号</th>" : ""}<th>名称</th><th>前缀</th><th>权限上限</th><th>创建</th><th>到期</th><th>最近使用</th><th>状态</th><th></th></tr></thead>
    <tbody>${rows || emptyRow(9, "key-round", "没有令牌")}</tbody></table></div>`;
}

function viewTokens() {
  const all = S.data.tokens, active = activeTokens(all).length;
  const revoked = all.filter((t) => t.revoked).length;
  const week = Date.now() / 1000 - 7 * 86400;
  const panel = `<div class="panel"><div class="stats">
      ${stat("key-round", "有效令牌", active)}${stat("activity", "7 天内使用", activeTokens(all).filter((t) => t.last_used > week).length)}
      ${stat("clock", "已过期", all.length - active - revoked)}${stat("ban", "已吊销", revoked)}</div>
    <div class="compositions">
      ${composition("权限上限", [{label: "跟随账号", n: activeTokens(all).filter((t) => !t.cap).length, color: "#6c7586"},
        {label: "只读", n: activeTokens(all).filter((t) => t.cap === "read").length, color: LEVEL_COLOR.read},
        {label: "读写", n: activeTokens(all).filter((t) => t.cap === "write").length, color: LEVEL_COLOR.write}])}
      ${composition("状态", [{label: "有效", n: active, color: "#00bc7d"}, {label: "已过期", n: all.length - active - revoked, color: LEVEL_COLOR.manage},
        {label: "已吊销", n: revoked, color: "#d4183d"}])}</div></div>`;
  return head("令牌", `${active} 个有效 · 共 ${all.length} 个`) + panel + tokenTable(all, true);
}

const ACTIONS = {login: "登录", login_failed: "登录失败", user_create: "创建账号", user_update: "修改账号", user_delete: "删除账号",
  grant_set: "授权", grant_remove: "移除权限", token_issue: "发放令牌", token_revoke: "吊销令牌", auth_switch: "切换 API 鉴权"};

function viewSettings() {
  const on = S.data.auth_enabled;
  const rows = S.data.audit.map((a) => `<tr><td class="muted nowrap">${fmt(a.time)}</td><td class="cell-title">${esc(a.actor)}</td><td class="nowrap">${esc(ACTIONS[a.action] || a.action)}</td>
    <td class="mono">${esc(a.target)}</td><td class="muted">${esc(a.detail)}</td></tr>`).join("");
  return head("设置与审计", `API 鉴权${on ? "已开启" : "已关闭"} · 最近 ${S.data.audit.length} 条操作记录`)
    + `<div class="panel"><div class="setting"><span class="ic ${on ? "on" : "off"}"><i data-lucide="${on ? "lock" : "lock-open"}"></i></span><div class="grow"><strong>API 鉴权</strong>
      <span class="muted">${on ? "API、MCP 与入库请求必须携带有效令牌，并按数据仓权限放行。" : "已关闭：API、MCP 与入库请求无需令牌，所有数据仓对外开放。控制台仍需登录。"}</span></div>
      <label class="switch" title="${on ? "关闭鉴权" : "开启鉴权"}"><input type="checkbox" id="auth-switch" ${on ? "checked" : ""} aria-label="API 鉴权"><span></span></label></div></div>
    <div class="toolbar"><h2>审计记录</h2><span class="count">${S.data.audit.length}</span></div>
    <div class="table-wrap"><table><thead><tr><th>时间</th><th>操作人</th><th>操作</th><th>对象</th><th>详情</th></tr></thead>
    <tbody>${rows || emptyRow(5, "scroll-text", "没有记录")}</tbody></table></div>`;
}

function viewMine() {
  const grants = Object.entries(S.me.grants);
  const info = new Map((S.me.banks || []).map((b) => [b.bank_id, b]));
  const max = Math.max(0, ...[...info.values()].map((b) => b.fact_count || 0));
  const rows = grants.map(([bank, level]) => {
    const b = info.get(bank) || {bank_id: bank, pending: true};
    return `<tr><td>${bankName(b)}</td><td><span class="chip ${level}">${esc(LEVEL_NAME[level])}</span></td>
      <td>${b.pending ? `<span class="muted">尚未创建</span>` : meter(b.fact_count || 0, max)}</td>
      <td class="muted nowrap">${b.pending ? "—" : ago(iso(b.last_write_at))}</td>
      <td class="actions"><a class="icon-btn sm" href="/banks/${encodeURIComponent(bank)}" data-tip="打开数据仓" aria-label="打开数据仓"><i data-lucide="external-link"></i></a></td></tr>`;
  }).join("");
  return head("我的权限", `${grants.length} 个数据仓 · ${activeTokens(S.me.tokens).length} 个有效令牌`)
    + `<div class="block"><div class="table-wrap"><table><thead><tr><th>数据仓</th><th>权限</th><th>记忆</th><th>最近活动</th><th></th></tr></thead><tbody>
    ${rows || emptyRow(5, "database", "管理员尚未给你授权任何数据仓")}</tbody></table></div></div>
    <div class="block"><div class="toolbar"><h2>我的令牌</h2><span class="count">由管理员发放</span></div>${tokenTable(S.me.tokens, false)}</div>`;
}

function bindView() {
  const main = $("#main");
  const search = $("#search");
  if (search) search.oninput = () => { S.query = search.value; const pos = search.selectionStart; render(); const again = $("#search"); again.focus(); again.setSelectionRange(pos, pos); };
  const create = $("#new-user");
  if (create) create.onclick = newUser;
  main.querySelectorAll("[data-user]").forEach((row) => row.onclick = (e) => { if (!e.target.closest("button")) openDrawer(Number(row.dataset.user)); });
  main.querySelectorAll("[data-open]").forEach((b) => b.onclick = () => openDrawer(Number(b.dataset.open)));
  main.querySelectorAll("[data-issue]").forEach((b) => b.onclick = () => issueToken(Number(b.dataset.issue)));
  main.querySelectorAll("[data-delete]").forEach((b) => b.onclick = () => {
    const user = S.data.users.find((u) => u.id === Number(b.dataset.delete));
    modal({title: "删除账号 " + user.username, confirm: "删除", danger: true,
      body: `<p>账号的令牌与授权会一并删除，数据仓中的记忆不受影响。</p>`,
      onConfirm: () => act(() => api(`/users/${user.id}`, {method: "DELETE"}), "账号已删除")});
  });
  main.querySelectorAll("[data-revoke-token]").forEach((b) => b.onclick = () => revokeToken(Number(b.dataset.revokeToken)));
  const toggle = $("#auth-switch");
  if (toggle) toggle.onchange = () => {
    const enabled = toggle.checked;
    toggle.checked = !enabled;
    modal({title: enabled ? "开启 API 鉴权" : "关闭 API 鉴权", confirm: enabled ? "开启" : "关闭", danger: !enabled,
      body: enabled ? `<p>开启后，没有有效令牌的客户端会立即被拒绝。</p>` : `<p>关闭后任何能访问 API 端口的人都可以读写全部数据仓。</p>`,
      onConfirm: () => act(() => api("/settings", {method: "PUT", body: {auth_enabled: enabled}}), enabled ? "API 鉴权已开启" : "API 鉴权已关闭")});
  };
  if (S.drawerUser && S.data) openDrawer(S.drawerUser);
}

bindThemeButton($("#theme-btn"));
$("#logout-btn").onclick = async () => {
  await fetch("/access/logout", {method: "POST"}).catch(() => null);
  location.replace("/access/login");
};
function changeOwnPassword() {
  modal({title: "修改密码", confirm: "保存", body: `<div class="grid-form">
    <label for="pw-old">当前密码</label><input class="input" id="pw-old" type="password" autocomplete="current-password">
    <label for="pw-new">新密码</label><input class="input" id="pw-new" type="password" autocomplete="new-password" placeholder="至少 10 位"></div>`,
  onConfirm: async (root) => {
    const done = await act(() => api("/password", {method: "POST", body: {current: $("#pw-old", root).value, password: $("#pw-new", root).value}}), "密码已修改，请重新登录");
    if (!done) return false;
    setTimeout(() => location.replace("/access/login"), 900);
  }});
}
$("#password-btn").onclick = changeOwnPassword;

refresh().catch((e) => { $("#main").innerHTML = `<div class="empty">${esc(e.message)}</div>`; });
