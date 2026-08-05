import { OperationsPageHeader } from "@/components/ui/operations-page-header";

export default function CasesPage() {
  return (
    <>
      <OperationsPageHeader
        title="Cases"
        description="Customer cases requiring investigation and a governed resolution."
      />
      <section className="mx-auto max-w-[1540px] px-4 py-12 sm:px-6 lg:px-7">
        <div className="border-y border-border py-10">
          <h2 className="text-lg font-semibold text-primary">No cases yet</h2>
          <p className="mt-2 text-sm text-secondary">
            Case intake is not connected in this workspace.
          </p>
        </div>
      </section>
    </>
  );
}
