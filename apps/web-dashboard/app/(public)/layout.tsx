import { PublicHeader } from "@/components/public-header";

/**
 * Public master-detail search. The form + results list live here in the layout, so they
 * stay mounted while the detail page renders into `{children}` — selecting a trial (or
 * going back) never re-runs the search.
 */
export default function SearchLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-screen flex-col">
      <PublicHeader />

      <div className="p-6">
        <div className="mx-auto flex max-w-6xl flex-col gap-6">
          <main className="flex-1 pb-16 md:pb-0">{children}</main>
        </div>
      </div>
    </div>
  );
}
