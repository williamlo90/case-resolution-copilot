import { AlertTriangle, FileCode2, FlaskConical, ShieldCheck } from "lucide-react";
import { WorkspaceLink as Link } from "@/components/navigation/workspace-link";
import { evaluatedDatasetFixture } from "@/mocks/fixtures/evaluation-fixtures";

export type EvidenceView = "evaluations" | "architecture";

function ResultPill({ result }: { result: "passed" | "failed" }) {
  return (
    <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-semibold ${
      result === "passed" ? "bg-success-bg text-success" : "bg-danger-bg text-danger"
    }`}>
      {result === "passed" ? "Passed" : "Failed"}
    </span>
  );
}

function decisionLabel(value: string) {
  const labels: Record<string, string> = {
    approve_resolution: "Approve resolution",
    safe_retry: "Safe retry",
    reconcile: "Check before retry",
    block_and_review: "Block and review",
  };
  return labels[value] ?? value.replaceAll("_", " ");
}

function Header({ activeView }: { activeView: EvidenceView }) {
  const items: Array<{ view: EvidenceView; label: string }> = [
    { view: "evaluations", label: "Case Checks" },
    { view: "architecture", label: "How It Is Checked" },
  ];

  return (
    <>
      <header className="border-b border-border bg-surface px-5 py-6 sm:px-8">
        <div className="mx-auto max-w-[1400px]">
          <p className="text-xs font-semibold uppercase tracking-[0.08em] text-muted">
            Reliability
          </p>
          <div className="mt-2 flex flex-wrap items-center justify-between gap-3">
            <h1 className="text-2xl font-semibold tracking-[-0.02em]">Reliability</h1>
            <span className="rounded-full bg-warning-bg px-3 py-1.5 text-xs font-semibold text-warning">
              Static baseline
            </span>
          </div>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-secondary">
            Versioned safety checks from a fixed dataset. This is not live
            production telemetry.
          </p>
          <dl className="mt-5 flex flex-wrap gap-x-7 gap-y-2 text-xs">
            <div>
              <dt className="inline text-muted">Baseline set </dt>
              <dd className="inline font-mono font-medium">{evaluatedDatasetFixture.goldenVersion}</dd>
            </div>
            <div>
              <dt className="inline text-muted">Result set </dt>
              <dd className="inline font-medium">Committed baseline</dd>
            </div>
            <div>
              <dt className="inline text-muted">Checked </dt>
              <dd className="inline font-medium">12 Jul 2026</dd>
            </div>
          </dl>
        </div>
      </header>

      <nav aria-label="Reliability sections" className="border-b border-border bg-surface px-5 sm:px-8">
        <div className="mx-auto flex max-w-[1400px] gap-6">
          {items.map((item) => (
            <Link
              key={item.view}
              href={item.view === "evaluations" ? "/evidence" : "/evidence?view=architecture"}
              aria-current={activeView === item.view ? "page" : undefined}
              className={`border-b-2 py-3 text-sm font-medium ${
                activeView === item.view
                  ? "border-action text-primary"
                  : "border-transparent text-secondary hover:text-primary"
              }`}
            >
              {item.label}
            </Link>
          ))}
        </div>
      </nav>
    </>
  );
}

function EvaluationCases() {
  const { summary } = evaluatedDatasetFixture;

  return (
    <section aria-labelledby="evaluation-heading">
      <h2 id="evaluation-heading" className="text-xl font-semibold">Case Checks</h2>
      <p className="mt-1 text-sm text-secondary">
        What should happen, what happened, and which safety gap still needs work.
      </p>

      <dl aria-label="Reliability summary" className="mt-4 grid max-w-xl grid-cols-3 overflow-hidden rounded-lg border border-border bg-surface">
        <div className="border-r border-border px-4 py-3">
          <dt className="text-xs font-medium text-muted">Total</dt>
          <dd className="mt-1 text-xl font-semibold tabular-nums">{summary.total}</dd>
        </div>
        <div className="border-r border-border px-4 py-3">
          <dt className="text-xs font-medium text-success">Passed</dt>
          <dd className="mt-1 text-xl font-semibold tabular-nums text-success">{summary.passed}</dd>
        </div>
        <div className="px-4 py-3">
          <dt className="text-xs font-medium text-danger">Failed</dt>
          <dd className="mt-1 text-xl font-semibold tabular-nums text-danger">{summary.failed}</dd>
        </div>
      </dl>

      <div className="mt-4 overflow-x-auto rounded-lg border border-border bg-surface">
        <table className="w-full min-w-[1040px] border-collapse text-left text-sm">
          <thead className="bg-surface-subtle text-xs text-secondary">
            <tr>
              <th className="px-4 py-3 font-semibold">Case</th>
              <th className="px-4 py-3 font-semibold">Should happen</th>
              <th className="px-4 py-3 font-semibold">Actually happened</th>
              <th className="px-4 py-3 font-semibold">Policy support</th>
              <th className="px-4 py-3 font-semibold">Next step</th>
              <th className="px-4 py-3 font-semibold">Result</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {evaluatedDatasetFixture.cases.map((item) => (
              <tr key={item.id} id={item.id} className="align-top">
                <td className="px-4 py-4">
                  <Link href={item.runHref} className="font-semibold hover:text-action hover:underline">
                    {item.scenario}
                  </Link>
                  <p className="mt-1 font-mono text-[11px] text-muted">{item.id}</p>
                  {item.failureReason ? (
                    <p className="mt-2 max-w-sm text-xs leading-5 text-danger">{item.failureReason}</p>
                  ) : null}
                </td>
                <td className="px-4 py-4 text-secondary">{decisionLabel(item.expectedDecision)}</td>
                <td className={item.result === "failed" ? "px-4 py-4 font-medium text-danger" : "px-4 py-4 text-secondary"}>
                  {decisionLabel(item.actualDecision)}
                </td>
                <td className="px-4 py-4 text-secondary">
                  {item.policyCitation}
                  <p className="mt-1 text-xs text-muted">{item.approval}</p>
                </td>
                <td className="px-4 py-4 font-mono text-xs text-secondary">{item.tool}</td>
                <td className="px-4 py-4">
                  <ResultPill result={item.result} />
                  {item.failedChecks.length ? (
                    <>
                      <p className="mt-2 max-w-[210px] text-[11px] leading-4 text-danger">
                        {item.failedChecks.join(", ")}
                      </p>
                      <dl className="mt-3 max-w-[260px] space-y-2 border-t border-border pt-3 text-xs font-normal leading-4">
                        <div>
                          <dt className="font-semibold text-primary">Risk</dt>
                          <dd className="text-secondary">{item.impact}</dd>
                        </div>
                        <div>
                          <dt className="font-semibold text-primary">What happened</dt>
                          <dd className="text-secondary">{item.safetyDisposition}</dd>
                        </div>
                        <div>
                          <dt className="font-semibold text-primary">Fix next</dt>
                          <dd className="text-secondary">{item.nextAction}</dd>
                        </div>
                      </dl>
                    </>
                  ) : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

const proofs = [
  {
    icon: FileCode2,
    title: "Bad data is blocked",
    invariant: "Invalid case, approval, activity, and reliability data fail before rendering.",
    checkArea: "Case data, approval data, activity data, reliability data",
    proof: "Covered by frontend schemas and backend contract checks",
  },
  {
    icon: ShieldCheck,
    title: "Unsafe retry is blocked",
    invariant: "When an account change may have happened, the user must check the account before trying again.",
    checkArea: "Retry decisions after uncertain account changes",
    proof: "Covered by deterministic simulator and recovery checks",
  },
  {
    icon: FlaskConical,
    title: "Old approvals are blocked",
    invariant: "Outdated plans and expired reviewer holds block decisions.",
    checkArea: "Approval version and reviewer hold age",
    proof: "Covered by version-bound approval checks",
  },
] as const;

function ArchitectureProof() {
  return (
    <section aria-labelledby="architecture-heading">
      <h2 id="architecture-heading" className="text-xl font-semibold">How It Is Checked</h2>
      <p className="mt-1 text-sm text-secondary">
        Three safeguards that are already covered by small checks.
      </p>
      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        {proofs.map((proof) => {
          const Icon = proof.icon;
          return (
            <article key={proof.title} className="rounded-lg border border-border bg-surface p-5">
              <Icon aria-hidden="true" className="text-action" size={20} />
              <h3 className="mt-4 font-semibold">{proof.title}</h3>
              <p className="mt-2 text-sm leading-6 text-secondary">{proof.invariant}</p>
              <dl className="mt-4 space-y-2 text-xs leading-5">
                <div>
                  <dt className="font-semibold text-primary">What is checked</dt>
                  <dd className="text-secondary">{proof.checkArea}</dd>
                </div>
                <div>
                  <dt className="font-semibold text-primary">Proof</dt>
                  <dd className="text-secondary">{proof.proof}</dd>
                </div>
              </dl>
            </article>
          );
        })}
      </div>

      <div className="mt-6 rounded-lg border border-warning/30 bg-warning-bg p-5">
        <div className="flex items-center gap-2">
          <AlertTriangle aria-hidden="true" className="text-warning" size={18} />
          <h3 className="font-semibold">Known Limits</h3>
        </div>
        <ul className="mt-4 grid gap-2 text-sm leading-6 text-secondary md:grid-cols-2">
          <li>These results come from a fixed dataset, not live customer traffic.</li>
          <li>Live database, authentication, and model health are not measured here.</li>
          <li>External case-source contract evidence has not been recorded.</li>
          <li>External action-target sandbox evidence has not been recorded.</li>
          <li>Email delivery and production telemetry are not verified here.</li>
          <li>Load, penetration, cost, and broad user-study evidence are not complete.</li>
        </ul>
      </div>
    </section>
  );
}

export function TechnicalEvidence({ activeView }: { activeView: EvidenceView }) {
  return (
    <div className="min-h-[calc(100vh-56px)] bg-canvas">
      <Header activeView={activeView} />
      <div className="mx-auto max-w-[1400px] px-5 py-8 sm:px-8">
        {activeView === "evaluations" ? <EvaluationCases /> : <ArchitectureProof />}
      </div>
    </div>
  );
}
