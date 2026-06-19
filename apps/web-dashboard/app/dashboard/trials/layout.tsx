/**
 * Dashboard trial search — same persistent master-detail as the public /search, nested in
 * the dashboard chrome. Form + results list stay mounted while the detail renders into
 * `{children}`.
 */
export default function DashboardTrialsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="p-6">
      <div className="mx-auto flex max-w-6xl flex-col gap-6">
        <div>
          <h2 className="text-lg font-semibold">Trial Search</h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            Semantic search across clinical trials
          </p>
        </div>

        <main className="flex-1 pb-16 md:pb-0">{children}</main>
      </div>
    </div>
  );
}
