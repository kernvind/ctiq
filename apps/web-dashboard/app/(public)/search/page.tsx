import { TrialResultsList } from "@/components/trial-results-list";
import { TrialSearchForm } from "@/components/trial-search-form";

/** Empty state shown in the detail pane until a trial is selected. */
import { searchTrialsAction } from "@/lib/actions/trial/search/actions";

export default async function SearchPage({
  searchParams,
}: {
  searchParams: Promise<{ q?: string }>;
}) {
  const query = (await searchParams).q ?? "";

  const results = query.length >= 10 ? await searchTrialsAction(query) : null;
  return (
    <div className="flex flex-col gap-4 rounded-lg border border-dashed p-6">
      <TrialSearchForm basePath="/search" />

      <TrialResultsList basePath="/search" state={results} query={query} />
    </div>
  );
}
