export default function OperationsLoading() {
  return <div aria-busy="true" aria-label="Loading workspace" className="min-h-[calc(100vh-60px)] bg-surface"><div className="border-b border-border px-4 py-6 sm:px-6 lg:px-7"><div className="h-7 w-48 animate-pulse bg-surface-subtle" /><div className="mt-3 h-4 w-full max-w-xl animate-pulse bg-surface-subtle" /></div><div className="grid gap-3 px-4 py-6 sm:px-6 lg:grid-cols-3 lg:px-7">{[1,2,3].map((item) => <div key={item} className="h-32 animate-pulse border border-border bg-canvas" />)}</div></div>;
}
