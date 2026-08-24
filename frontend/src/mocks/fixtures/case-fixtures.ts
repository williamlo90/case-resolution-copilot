import { CaseSummarySchema, CaseWorkspaceSchema, type CaseSummary, type CaseWorkspace } from "@/domain/cases/case";

const rawCases = [
  {
    id: "CS-2048", sourceId: "RF-1042", externalReference: "INV-88241", category: "billing_dispute", issue: "Duplicate subscription charge",
    customer: { name: "Maya Chen", isVip: false }, status: "needs_review", owner: { id: "USR-AR", name: "Alex Rivera", initials: "AR" }, urgency: "high", risk: "high",
    slaMinutesRemaining: 42, updatedAt: "2026-07-21T03:28:00.000Z", sourceFreshness: { status: "current", checkedAt: "2026-07-21T03:27:00.000Z" }, impact: { amount: 99, currency: "USD" },
  },
  {
    id: "CS-2047", sourceId: "TC-1039", externalReference: "PAY-55572", category: "refund_request", issue: "Refund not received",
    customer: { name: "Jordan Patel", isVip: false }, status: "investigating", owner: { id: "USR-PS", name: "Priya Shah", initials: "PS" }, urgency: "medium", risk: "medium",
    slaMinutesRemaining: 134, updatedAt: "2026-07-21T02:41:00.000Z", sourceFreshness: { status: "current", checkedAt: "2026-07-21T02:40:00.000Z" }, impact: { amount: 145, currency: "USD" },
  },
  {
    id: "CS-2046", sourceId: "BI-1037", externalReference: "ACC-19044", category: "account_access", issue: "Account access blocked",
    customer: { name: "Elena Garcia", isVip: true }, status: "information_needed", owner: null, urgency: "critical", risk: "high",
    slaMinutesRemaining: 18, updatedAt: "2026-07-21T01:58:00.000Z", sourceFreshness: { status: "stale", checkedAt: "2026-07-21T00:58:00.000Z" }, impact: null,
  },
  {
    id: "CS-2045", sourceId: "RF-1034", externalReference: "ORD-44812", category: "service_exception", issue: "Order arrived damaged",
    customer: { name: "Sam Wilson", isVip: false }, status: "new", owner: null, urgency: "medium", risk: "medium",
    slaMinutesRemaining: 260, updatedAt: "2026-07-21T01:06:00.000Z", sourceFreshness: { status: "current", checkedAt: "2026-07-21T01:05:00.000Z" }, impact: { amount: 78, currency: "USD" },
  },
  {
    id: "CS-2044", sourceId: "TC-1031", externalReference: "SUB-77421", category: "service_exception", issue: "Subscription cancelled unexpectedly",
    customer: { name: "Priya Nair", isVip: false }, status: "in_progress", owner: { id: "USR-JM", name: "Jordan Miles", initials: "JM" }, urgency: "medium", risk: "medium",
    slaMinutesRemaining: 207, updatedAt: "2026-07-20T23:52:00.000Z", sourceFreshness: { status: "current", checkedAt: "2026-07-20T23:51:00.000Z" }, impact: null,
  },
  {
    id: "CS-2043", sourceId: "BI-1028", externalReference: "CR-00359", category: "billing_dispute", issue: "Credit applied incorrectly",
    customer: { name: "Noah Williams", isVip: false }, status: "waiting_customer", owner: { id: "USR-ET", name: "Elena Torres", initials: "ET" }, urgency: "low", risk: "low",
    slaMinutesRemaining: 520, updatedAt: "2026-07-20T22:31:00.000Z", sourceFreshness: { status: "current", checkedAt: "2026-07-20T22:30:00.000Z" }, impact: { amount: 40, currency: "USD" },
  },
  {
    id: "CS-2042", sourceId: "RF-1026", externalReference: "ACC-33820", category: "account_access", issue: "Unrecognized account change",
    customer: { name: "Fatima Ahmed", isVip: true }, status: "needs_review", owner: { id: "USR-AR", name: "Alex Rivera", initials: "AR" }, urgency: "high", risk: "high",
    slaMinutesRemaining: 65, updatedAt: "2026-07-20T21:14:00.000Z", sourceFreshness: { status: "current", checkedAt: "2026-07-20T21:13:00.000Z" }, impact: null,
  },
  {
    id: "CS-2041", sourceId: "TC-1021", externalReference: "DEL-77409", category: "service_exception", issue: "Delivery compensation request",
    customer: { name: "Lucas Martin", isVip: false }, status: "new", owner: null, urgency: "medium", risk: "medium",
    slaMinutesRemaining: 318, updatedAt: "2026-07-20T20:07:00.000Z", sourceFreshness: { status: "current", checkedAt: "2026-07-20T20:05:00.000Z" }, impact: { amount: 55, currency: "USD" },
  },
  {
    id: "CS-2040", sourceId: "BI-1018", externalReference: "INV-99012", category: "billing_dispute", issue: "Invoice tax discrepancy",
    customer: { name: "Hana Kim", isVip: false }, status: "in_progress", owner: { id: "USR-PS", name: "Priya Shah", initials: "PS" }, urgency: "low", risk: "low",
    slaMinutesRemaining: 522, updatedAt: "2026-07-20T19:02:00.000Z", sourceFreshness: { status: "current", checkedAt: "2026-07-20T19:01:00.000Z" }, impact: { amount: 23, currency: "USD" },
  },
] as const;

export const caseSummaryFixtures: readonly CaseSummary[] = CaseSummarySchema.array().parse(rawCases);

const primaryCase = caseSummaryFixtures[0];

export const primaryCaseWorkspaceFixture: CaseWorkspace = CaseWorkspaceSchema.parse({
  case: primaryCase,
  request: {
    receivedAt: "2026-07-21T02:46:00.000Z",
    channel: "email",
    customerMessage: "Hi Support, I was charged twice for the same monthly subscription. Both charges are for USD 99.00. Please reverse the duplicate charge before our finance close today.",
    summary: "Customer was charged twice for the same monthly subscription and requests reversal of the duplicate USD 99.00 charge.",
  },
  conversation: {
    id: "THR-2048",
    version: 1,
    updatedAt: "2026-07-21T02:46:00.000Z",
    messages: [
      {
        id: "MSG-2048-1",
        authorType: "customer",
        authorId: "CUS-100284",
        authorName: "Maya Chen",
        channel: "email",
        body: "Hi Support, I was charged twice for the same monthly subscription. Both charges are for USD 99.00. Please reverse the duplicate charge before our finance close today.",
        internal: false,
        sourceReference: "EMAIL-2048-1",
        createdAt: "2026-07-21T02:46:00.000Z",
        version: 1,
      },
    ],
  },
  customer: { id: "CUS-100284", tier: "standard", locale: "en-SG", contact: "maya.chen@example.com" },
  businessContexts: [
    { id: "SUB-88421", type: "subscription", label: "Pro monthly subscription", source: "Billing system", sourceReference: "SUB-88421", status: "active", fields: { plan: "Pro Monthly", billing_period: "May 2026", price: "USD 99.00" }, capturedAt: "2026-07-21T03:20:00.000Z", sourceFreshness: { status: "current", checkedAt: "2026-07-21T03:20:00.000Z" }, version: 1 },
    { id: "PAY-5501", type: "payment", label: "First captured charge", source: "Billing system", sourceReference: "PAY-5501", status: "paid", fields: { amount: "USD 99.00", captured_at: "10 May 2026 09:14" }, capturedAt: "2026-07-21T03:20:00.000Z", sourceFreshness: { status: "current", checkedAt: "2026-07-21T03:20:00.000Z" }, version: 1 },
    { id: "PAY-5502", type: "payment", label: "Duplicate captured charge", source: "Billing system", sourceReference: "PAY-5502", status: "duplicate", fields: { amount: "USD 99.00", captured_at: "10 May 2026 09:15" }, capturedAt: "2026-07-21T03:20:00.000Z", sourceFreshness: { status: "current", checkedAt: "2026-07-21T03:20:00.000Z" }, version: 1 },
  ],
  facts: [
    { id: "FACT-1", statement: "Two USD 99.00 charges were captured one minute apart.", source: "Billing system", verifiedAt: "2026-07-21T03:20:00.000Z" },
    { id: "FACT-2", statement: "Both charges reference the same active subscription and billing period.", source: "Billing system", verifiedAt: "2026-07-21T03:20:00.000Z" },
    { id: "FACT-3", statement: "No prior billing adjustment was issued for this case.", source: "Support history", verifiedAt: "2026-07-21T03:22:00.000Z" },
  ],
  missingInformation: [
    { id: "MISS-1", label: "Automatic reversal status", description: "Confirm whether the billing system has already scheduled an automatic reversal.", blocking: true },
  ],
  evidence: [
    { id: "POL-BILL-3.2", title: "Billing adjustments v3", citation: "Section 3.2 Duplicate charges", excerpt: "A duplicate charge caused by a billing error may be reversed to the original payment method.", applicability: "Both captured charges reference the same subscription and billing period.", effectiveDate: "01 Jun 2026", freshness: "current", conflictState: "none" },
    { id: "POL-BILL-3.4", title: "Billing adjustments v3", citation: "Section 3.4 Existing reversals", excerpt: "Before issuing a reversal, confirm that no automatic reversal is already pending.", applicability: "The target billing system can report a pending automatic reversal.", effectiveDate: "01 Jun 2026", freshness: "current", conflictState: "none" },
  ],
  risks: [
    { id: "RISK-1", label: "Policy alignment", outcome: "passed", explanation: "The duplicate charge meets the published adjustment criteria." },
    { id: "RISK-2", label: "Duplicate reversal", outcome: "information_needed", explanation: "A pending automatic reversal must be ruled out before execution." },
    { id: "RISK-3", label: "Approval threshold", outcome: "requires_review", explanation: "USD 99.00 exceeds the specialist reversal threshold of USD 50.00." },
  ],
  proposal: {
    id: "PROP-2048-1", version: 1, outcome: "Reverse duplicate charge", impact: { amount: 99, currency: "USD" }, confidence: "medium",
    uncertainty: "Outcome remains uncertain until the billing system confirms that no automatic reversal is pending.",
    rationale: "The duplicate charge is verified and the active policy permits reversal after the existing-reversal check.", state: "ready_for_review",
  },
  responseDraft: {
    id: "DFT-2048",
    version: 1,
    source: "saved",
    editVersion: 1,
    subject: "Duplicate subscription charge",
    body: "Hi Maya, we verified the duplicate USD 99.00 subscription charge. We are checking whether an automatic reversal is already pending and have prepared the adjustment for supervisor review. We will confirm the final outcome once that review is complete.",
    status: "ready",
    updatedAt: "2026-07-21T03:28:00.000Z",
  },
  proposedActions: [
    { id: "ACT-REV-1", type: "reverse_charge", label: "Reverse duplicate charge", impact: { amount: 99, currency: "USD" }, expectedOutcome: "One USD 99.00 reversal is recorded against payment PAY-5502.", reviewRequired: true },
  ],
  activity: [
    { id: "EV-1", label: "Customer request received", detail: "Email linked to the active subscription account.", actor: "System", timestamp: "2026-07-21T02:46:00.000Z", status: "completed" },
    { id: "EV-2", label: "Billing context verified", detail: "Two captured charges matched to the same billing period.", actor: "Alex Rivera", timestamp: "2026-07-21T03:20:00.000Z", status: "completed" },
    { id: "EV-3", label: "Policy evidence attached", detail: "Billing adjustments v3 sections 3.2 and 3.4.", actor: "Resolution service", timestamp: "2026-07-21T03:24:00.000Z", status: "completed" },
    { id: "EV-4", label: "Ready for supervisor review", detail: "Proposal is blocked from execution until review is complete.", actor: "Resolution service", timestamp: "2026-07-21T03:28:00.000Z", status: "waiting" },
  ],
  collections: {
    businessContexts: {
      returned: 3,
      total: 3,
      hasMore: false,
      nextCursor: null,
    },
    messages: {
      returned: 1,
      total: 1,
      hasMore: false,
      nextCursor: null,
    },
    activity: {
      returned: 4,
      total: 4,
      hasMore: false,
      nextCursor: null,
    },
  },
  availableCommands: ["request_information", "send_reply", "add_note", "add_evidence", "revise_resolution", "save_draft", "submit_for_review", "escalate", "export_audit"],
});

export const caseWorkspaceFixtures: readonly CaseWorkspace[] = caseSummaryFixtures.map((summary) => {
  if (summary.id === primaryCase.id) return primaryCaseWorkspaceFixture;
  return CaseWorkspaceSchema.parse({
    ...primaryCaseWorkspaceFixture,
    case: summary,
    request: {
      ...primaryCaseWorkspaceFixture.request,
      customerMessage: `${summary.issue}. Please review the connected context and recommend the safest next step.`,
      summary: `${summary.customer.name} reported ${summary.issue.toLocaleLowerCase()} and needs a policy-supported resolution.`,
    },
    conversation: {
      ...primaryCaseWorkspaceFixture.conversation,
      id: `THR-${summary.id.slice(3)}`,
      messages: primaryCaseWorkspaceFixture.conversation.messages.map((message) => ({
        ...message,
        id: `MSG-${summary.id.slice(3)}-1`,
        authorName: summary.customer.name,
        body: `${summary.issue}. Please review the connected context and recommend the safest next step.`,
      })),
    },
    customer: { ...primaryCaseWorkspaceFixture.customer, id: `CUS-${summary.id.slice(3)}`, contact: `${summary.customer.name.toLocaleLowerCase().replaceAll(" ", ".")}@example.com`, tier: summary.customer.isVip ? "vip" : "standard" },
    proposal: { ...primaryCaseWorkspaceFixture.proposal, id: `PROP-${summary.id.slice(3)}-1`, outcome: summary.category === "account_access" ? "Escalate for verified account recovery" : summary.category === "refund_request" ? "Verify refund settlement" : summary.category === "service_exception" ? "Prepare service exception resolution" : "Review billing adjustment", impact: summary.impact, state: summary.status === "information_needed" ? "information_needed" : summary.status === "needs_review" ? "ready_for_review" : "draft" },
    responseDraft: { ...primaryCaseWorkspaceFixture.responseDraft, subject: summary.issue },
    availableCommands: summary.owner
      ? summary.status === "information_needed" || summary.status === "waiting_customer"
        ? ["resume_investigation", "send_reply", "add_note", "add_evidence", "revise_resolution", "save_draft", "escalate", "export_audit"]
        : ["request_information", "send_reply", "add_note", "add_evidence", "revise_resolution", "save_draft", "submit_for_review", "escalate", "export_audit"]
      : ["assign_to_me", "send_reply", "add_note", "add_evidence", "export_audit"],
  });
});
