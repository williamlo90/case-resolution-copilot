export default function CaseWorkspaceLoading() {
  return (
    <div
      role="status"
      aria-label="Opening case"
      aria-busy="true"
      className="min-h-[calc(100vh-60px)] bg-surface"
    >
      <header className="border-b border-border px-4 pt-4 sm:px-6 lg:px-7">
        <div className="mx-auto max-w-[1540px]">
          <div className="h-4 w-28 animate-pulse bg-surface-subtle" />
          <div className="mt-5 flex flex-col gap-4 pb-5">
            <div className="h-4 w-40 animate-pulse bg-surface-subtle" />
            <div className="h-9 w-full max-w-3xl animate-pulse bg-surface-subtle" />
            <div className="h-4 w-72 max-w-full animate-pulse bg-surface-subtle" />
          </div>
          <div className="flex gap-4 overflow-hidden border-t border-border py-3 sm:gap-6">
            {[1, 2, 3, 4].map((item) => (
              <div
                key={item}
                className="h-5 min-w-16 max-w-24 flex-1 animate-pulse bg-surface-subtle"
              />
            ))}
          </div>
        </div>
      </header>

      <div className="mx-auto grid max-w-[1540px] xl:grid-cols-[minmax(0,1fr)_400px]">
        <div className="space-y-8 px-4 py-8 sm:px-6 lg:px-7">
          {[1, 2, 3].map((item) => (
            <section key={item} className="border-b border-border pb-8">
              <div className="h-5 w-36 animate-pulse bg-surface-subtle" />
              <div className="mt-4 h-4 w-full animate-pulse bg-surface-subtle" />
              <div className="mt-3 h-4 w-4/5 animate-pulse bg-surface-subtle" />
            </section>
          ))}
        </div>
        <aside className="hidden border-l border-border bg-[#fbfcfc] px-7 py-8 xl:block">
          <div className="h-5 w-40 animate-pulse bg-surface-subtle" />
          <div className="mt-5 h-8 w-64 animate-pulse bg-surface-subtle" />
          <div className="mt-10 h-4 w-full animate-pulse bg-surface-subtle" />
          <div className="mt-3 h-4 w-3/4 animate-pulse bg-surface-subtle" />
        </aside>
      </div>
      <span className="sr-only">Opening case...</span>
    </div>
  );
}
