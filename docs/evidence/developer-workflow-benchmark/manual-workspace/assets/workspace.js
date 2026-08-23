const CASES = [
  { id: "billing-a", label: "BILL-A - Billing dispute" },
  { id: "refund-a", label: "REF-A - Refund request" },
  { id: "account-a", label: "ACC-A - Account recovery" },
];

const VIEWS = [
  ["ticket.html", "Helpdesk Ticket"],
  ["customer-record.html", "Customer / CRM Record"],
  ["business-records.html", "Business Records"],
  ["policy-library.html", "Policy Library"],
  ["decision-brief.html", "Blank Decision Brief"],
];

const escapeHtml = (value) => String(value ?? "")
  .replaceAll("&", "&amp;")
  .replaceAll("<", "&lt;")
  .replaceAll(">", "&gt;")
  .replaceAll('"', "&quot;")
  .replaceAll("'", "&#039;");

function selectedCase() {
  const requested = new URLSearchParams(window.location.search).get("case");
  return CASES.some((item) => item.id === requested) ? requested : CASES[0].id;
}

function shell(caseId) {
  const page = window.location.pathname.split("/").pop() || "ticket.html";
  const options = CASES.map((item) => `<option value="${item.id}" ${item.id === caseId ? "selected" : ""}>${item.label}</option>`).join("");
  const links = VIEWS.map(([href, label]) => `<a class="${href === page ? "active" : ""}" href="${href}?case=${caseId}">${label}</a>`).join("");
  document.body.innerHTML = `<header class="topbar"><div class="brand">Manual Case Workspace</div><label class="case-picker">Case <select id="case-picker">${options}</select></label></header><div class="layout"><nav class="nav">${links}</nav><main id="content" class="content"></main></div>`;
  document.querySelector("#case-picker").addEventListener("change", (event) => {
    window.location.search = `?case=${event.target.value}`;
  });
  return page;
}

function heading(data, title) {
  return `<p class="eyebrow">${escapeHtml(data.fixture_id)} / ${escapeHtml(data.case.category.replaceAll("_", " "))}</p><h1>${escapeHtml(title)}</h1>`;
}

function renderTicket(data) {
  const messages = data.conversation.map((message) => `<article class="message ${message.internal ? "internal" : ""}"><div class="message-head"><strong>${escapeHtml(message.author_name)}</strong><span>${escapeHtml(message.channel)} / ${escapeHtml(message.created_at)}</span></div><div>${escapeHtml(message.body)}</div><small>${escapeHtml(message.source_reference || "No source reference")}</small></article>`).join("");
  return `${heading(data, data.case.issue)}<div class="meta"><div><span class="label">Status</span>${escapeHtml(data.case.status)}</div><div><span class="label">Urgency / risk</span>${escapeHtml(data.case.urgency)} / ${escapeHtml(data.case.risk)}</div><div><span class="label">Due</span>${escapeHtml(data.case.due_at)}</div></div><section class="panel"><h2>Customer request</h2><p>${escapeHtml(data.case.request.customer_message)}</p><p><strong>Summary:</strong> ${escapeHtml(data.case.request.summary)}</p></section><section class="panel"><h2>Conversation</h2>${messages}</section>`;
}

function renderCustomer(data) {
  const customer = data.case.customer;
  return `${heading(data, "Customer / CRM Record")}<section class="panel"><div class="meta"><div><span class="label">Customer ID</span>${escapeHtml(customer.customer_id)}</div><div><span class="label">Tier</span>${escapeHtml(customer.tier)}</div><div><span class="label">Locale</span>${escapeHtml(customer.locale)}</div></div><h2>${escapeHtml(customer.name)}</h2><p>${escapeHtml(customer.contact)}</p><p><strong>Linked case:</strong> ${escapeHtml(data.case.public_id)}</p><p><strong>External reference:</strong> ${escapeHtml(data.case.external_reference)}</p></section>`;
}

function renderRecords(data) {
  const records = data.case.business_contexts.map((record) => {
    const fields = Object.entries(record.fields).map(([key, value]) => `<dt>${escapeHtml(key)}</dt><dd>${escapeHtml(value)}</dd>`).join("");
    return `<article class="record"><span class="label">${escapeHtml(record.type)} / ${escapeHtml(record.public_id)}</span><h2>${escapeHtml(record.label)}</h2><p><strong>Status:</strong> ${escapeHtml(record.status)} | <strong>Freshness:</strong> ${escapeHtml(record.freshness)} | <strong>Checked:</strong> ${escapeHtml(record.checked_at)}</p><p><strong>Source:</strong> ${escapeHtml(record.source)} / ${escapeHtml(record.source_reference)}</p><dl>${fields}</dl></article>`;
  }).join("");
  return `${heading(data, "Business Records")}${records}`;
}

function renderPolicies(data, policies) {
  const visible = policies.policies.filter((policy) => data.policy_ids.includes(policy.policy_id));
  return `${heading(data, "Policy Library")}${visible.map((policy) => `<article class="policy"><span class="label">${escapeHtml(policy.policy_id)} / version ${escapeHtml(policy.version)}</span><h2>${escapeHtml(policy.title)}</h2><p><strong>Categories:</strong> ${escapeHtml(policy.case_categories.join(", "))}</p>${policy.clauses.map((clause) => `<p><strong>${escapeHtml(clause.clause_id)}:</strong> ${escapeHtml(clause.text)}</p>`).join("")}</article>`).join("")}`;
}

const BRIEF_FIELDS = [
  ["disposition", "Disposition", "select", ["", "ready_for_review", "information_needed", "escalate"]],
  ["issue_summary", "Issue summary", "textarea"],
  ["verified_facts", "Verified facts (Fact | Source ID, one per line)", "textarea"],
  ["missing_information", "Missing or blocking information", "textarea"],
  ["policy", "Applicable policy (ID, version, clause)", "textarea"],
  ["risk_uncertainty", "Risk and uncertainty", "textarea"],
  ["suggested_resolution", "Suggested resolution", "textarea"],
  ["approval", "Required approver", "select", ["", "none", "specialist", "supervisor", "administrator"]],
  ["next_safe_action", "Next safe action", "textarea"],
  ["customer_response", "Customer response draft", "textarea"],
];

function renderBrief(data) {
  const storageKey = `decision-brief:${data.fixture_id}`;
  const saved = JSON.parse(localStorage.getItem(storageKey) || "{}");
  const fields = BRIEF_FIELDS.map(([name, label, type, options]) => {
    const value = saved[name] || "";
    const control = type === "select"
      ? `<select name="${name}">${options.map((option) => `<option value="${option}" ${option === value ? "selected" : ""}>${option || "Select..."}</option>`).join("")}</select>`
      : `<textarea name="${name}">${escapeHtml(value)}</textarea>`;
    return `<div class="field ${type === "textarea" ? "full" : ""}"><label for="${name}">${label}</label>${control}</div>`;
  }).join("");
  const html = `${heading(data, "Decision Brief")}<p class="notice">This worksheet starts blank. Record conclusions with source IDs so another reviewer can trace them.</p><form id="brief-form"><div class="form-grid">${fields}</div><div class="actions"><button class="button" type="button" id="save-brief">Save locally</button><button class="button secondary" type="button" id="export-brief">Export JSON</button><button class="button secondary" type="reset" id="clear-brief">Clear</button></div></form>`;
  document.querySelector("#content").innerHTML = html;
  const form = document.querySelector("#brief-form");
  const snapshot = () => Object.fromEntries(new FormData(form).entries());
  document.querySelector("#save-brief").addEventListener("click", () => localStorage.setItem(storageKey, JSON.stringify(snapshot())));
  document.querySelector("#export-brief").addEventListener("click", () => {
    const payload = { fixture_id: data.fixture_id, exported_at: new Date().toISOString(), ...snapshot() };
    const link = document.createElement("a");
    link.href = URL.createObjectURL(new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" }));
    link.download = `${data.fixture_id.toLowerCase()}-decision-brief.json`;
    link.click();
    URL.revokeObjectURL(link.href);
  });
  document.querySelector("#clear-brief").addEventListener("click", () => localStorage.removeItem(storageKey));
  return null;
}

async function start() {
  const caseId = selectedCase();
  const page = shell(caseId);
  const [caseResponse, policyResponse] = await Promise.all([fetch(`cases/${caseId}.json`), fetch("assets/policy-library.json")]);
  if (!caseResponse.ok || !policyResponse.ok) throw new Error("Benchmark files could not be loaded.");
  const data = await caseResponse.json();
  const policies = await policyResponse.json();
  const renderers = { "ticket.html": renderTicket, "customer-record.html": renderCustomer, "business-records.html": renderRecords, "policy-library.html": (item) => renderPolicies(item, policies), "decision-brief.html": renderBrief };
  const html = (renderers[page] || renderTicket)(data);
  if (html !== null) document.querySelector("#content").innerHTML = html;
}

start().catch((error) => {
  document.body.innerHTML = `<main class="home"><h1>Workspace unavailable</h1><p>${escapeHtml(error.message)}</p><p>Serve this directory through a local HTTP server; browser file URLs cannot load fixture JSON.</p></main>`;
});
