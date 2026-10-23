"use strict";
(() => {
  const $ = (id) => document.getElementById(id);
  const scenarios = {
    verified_reopen: { code: "MANUAL-V2-01", task: "Write and review a brief, apply the authorized synthetic action once, read back its effect, record verified completion, then reopen with new evidence." },
    sop_revision: { code: "MANUAL-V2-02", task: "Approve under SOP v1. Receive v2, then decide whether the old action can execute and record your decision. Receive rollback v3 and decide again. Explain the authority for each decision." },
    timeout_recovery: { code: "MANUAL-V2-03", task: "Write and review the brief, apply the authorized synthetic action, handle a lost response safely, then read back the original operation. Verify the outcome before recording closure." },
  };
  let selected = "verified_reopen";
  let state;
  const storageKey = () => `case-resolution-v2-manual-1:${selected}`;
  const fresh = () => ({ pack: "v2-interactive-1", mode: "manual", scenario: selected,
    case_id: scenarios[selected].code, policy_version: 1, notes: {}, inputs: {}, history: [],
    target: { owner: `CUSTOMER-${scenarios[selected].code}`, currency: "USD", credited_minor: "0" },
    effects: [], provider_status: "No operation submitted.", created_at: new Date().toISOString() });
  function status(message, error = false) { $("status").textContent = message; $("status").classList.toggle("error", error); }
  function persist() {
    try { localStorage.setItem(storageKey(), JSON.stringify(state)); return true; }
    catch { status("Storage is unavailable. Download your result before leaving this page.", true); return false; }
  }
  function record(kind, data = {}) {
    const previous = kind === "reopened" ? [...state.history].reverse().find((e) => e.kind === "completed") : null;
    state.history.push({ id: crypto.randomUUID(), kind, at: new Date().toISOString(),
      role: $("role").value, policy_version: state.policy_version, reason: $("event-reason").value.trim(),
      reference: $("reference").value.trim() || null, previous_event_id: previous?.id ?? null, ...data });
    persist(); renderHistory();
  }
  function renderHistory() {
    $("history").replaceChildren();
    for (const event of state.history) {
      const li = document.createElement("li");
      li.textContent = `${event.kind} · ${event.role} · SOP v${event.policy_version} · ${event.reason || "No reason recorded"}${event.reference ? ` · ${event.reference}` : ""}${event.previous_event_id ? ` · previous completion ${event.previous_event_id}` : ""}`;
      $("history").append(li);
    }
    $("provider-status").textContent = state.provider_status;
    $("ledger").textContent = JSON.stringify({ target: state.target, effects: state.effects, effect_count: state.effects.length }, null, 2);
  }
  function renderPolicy() {
    const cap = state.policy_version === 2 ? "100" : "500";
    $("policy").textContent = `SOP v${state.policy_version}: An unused course may be refunded within 30 days only with 0% attendance, a verified original owner and exact target, amount and currency. Maximum USD ${cap}. Human approval is required for consequential actions. Approval binds its exact evidence and policy revision. A changed revision invalidates old authority; rollback creates a new revision. Verify downstream outcome before closing; reconcile an unknown outcome before any retry. Closure needs a simulated communication reference; reopen needs new evidence and links the previous completion.`;
    $("policy-history").replaceChildren();
    for (let v = 1; v <= state.policy_version; v++) {
      const li = document.createElement("li");
      const event = state.history.find((e) => e.kind === "policy_published" && e.policy_version === v);
      li.textContent = `Revision ${v} · cap USD ${v === 2 ? 100 : 500} · ${event?.at ?? state.created_at}${v === 3 ? " · previous content republished as a new revision" : ""}`;
      $("policy-history").append(li);
    }
    $("sop-controls").hidden = selected !== "sop_revision";
    $("revise").disabled = state.policy_version !== 1;
    $("rollback").disabled = state.policy_version !== 2;
  }
  function load(id) {
    selected = id;
    let saved = null;
    try { saved = JSON.parse(localStorage.getItem(storageKey()) || "null"); } catch { /* Keep a fresh form if the local record cannot be parsed. */ }
    state = saved?.pack === "v2-interactive-1" && saved.scenario === selected ? saved : fresh();
    $("task").textContent = scenarios[selected].task;
    $("case-id").textContent = `${state.case_id} · target COURSE-${state.case_id}`;
    $("source").replaceChildren();
    const fields = { original_recipient: state.target.owner, target: `COURSE-${state.case_id}`,
      authorized_amount_minor: "24000", currency: "USD", attendance_percent: "0", purchase_age_at_request_days: "5",
      source: "verified synthetic course register", delivery_state: "not_started", freshness: "current at request" };
    for (const [key, value] of Object.entries(fields)) {
      const dt = document.createElement("dt"); dt.textContent = key.replaceAll("_", " ");
      const dd = document.createElement("dd"); dd.textContent = value; $("source").append(dt, dd);
    }
    document.querySelectorAll("[data-field]").forEach((el) => { el.value = state.notes[el.dataset.field] || ""; });
    for (const id of ["role", "event-reason", "reference", "target", "recipient", "amount", "currency", "operation"]) {
      $(id).value = state.inputs[id] || (id === "role" ? "specialist" : "");
    }
    renderPolicy(); renderHistory(); status("Ready. Read the task and source evidence first.");
  }
  document.querySelectorAll("[data-field]").forEach((el) => el.addEventListener("input", () => { state.notes[el.dataset.field] = el.value; persist(); }));
  for (const id of ["role", "event-reason", "reference", "target", "recipient", "amount", "currency", "operation"]) {
    $(id).addEventListener("input", () => { state.inputs[id] = $(id).value; persist(); });
  }
  $("scenario").addEventListener("change", () => load($("scenario").value));
  $("save").addEventListener("click", () => { if (persist()) status("Saved in this browser. Download a copy before leaving."); });
  $("download").addEventListener("click", () => {
    persist(); const url = URL.createObjectURL(new Blob([JSON.stringify({ ...state, exported_at: new Date().toISOString() }, null, 2)], { type: "application/json" }));
    const link = document.createElement("a"); link.href = url; link.download = `${state.case_id}-manual.json`; link.click(); URL.revokeObjectURL(url);
  });
  document.querySelectorAll("[data-event]").forEach((el) => el.addEventListener("click", () => {
    if (!$("event-reason").value.trim()) return status("Record your reason or proof first.", true);
    if (["completed", "reopened"].includes(el.dataset.event) && !$("reference").value.trim()) return status("Add a communication or new-evidence reference first.", true);
    record(el.dataset.event); status("Manual decision recorded. The tool does not adjudicate correctness.");
  }));
  function revise(version) { state.policy_version = version; record("policy_published"); renderPolicy(); status(`Received SOP v${version}. Reassess the existing approval yourself.`); }
  $("revise").addEventListener("click", () => { if (state.policy_version === 1) revise(2); });
  $("rollback").addEventListener("click", () => { if (state.policy_version === 2) revise(3); });
  $("apply").addEventListener("click", () => {
    const payload = { target: $("target").value.trim(), recipient: $("recipient").value.trim(), amount_minor: $("amount").value.trim(), currency: $("currency").value.trim(), operation_id: $("operation").value.trim() };
    if (payload.target !== `COURSE-${state.case_id}` || payload.recipient !== state.target.owner || payload.amount_minor !== "24000" || payload.currency !== "USD" || payload.operation_id.length < 16) {
      record("target_rejected", { payload }); return status("Target rejected the payload before change. Check target, original recipient, cents, currency and operation ID.", true);
    }
    if (state.effects.length) { record("duplicate_blocked", { payload }); return status("Target already has an effect. Read back the existing operation; do not apply again.", true); }
    state.target.credited_minor = "24000";
    state.effects.push({ ...payload, at: new Date().toISOString(), credited_minor: "24000" });
    state.provider_status = selected === "timeout_recovery" ? "Response timed out; outcome unknown to caller. Reconcile the original operation." : "Receipt accepted. Read-back still required before claiming completion.";
    record(selected === "timeout_recovery" ? "target_response_unknown" : "target_receipt", { operation_id: payload.operation_id }); renderHistory(); status(state.provider_status);
  });
  $("readback").addEventListener("click", () => {
    const effect = state.effects.find((e) => e.operation_id === $("operation").value.trim());
    const observation = { found: Boolean(effect), target: state.target, effect_count: state.effects.length, operation_id: $("operation").value.trim() };
    state.provider_status = JSON.stringify(observation); record("target_readback", { observation }); renderHistory(); status("Read-back recorded. Compare it with the approved payload and write your verification notes.");
  });
  load(selected);
})();
