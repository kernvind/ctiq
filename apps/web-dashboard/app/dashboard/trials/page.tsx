import { TrialSearchForm } from "@/components/trial-search-form";

export default function TrialsPage() {
  return (
    <div className="p-6">
      <div className="max-w-3xl mx-auto">
        <div className="mb-6">
          <h2 className="text-lg font-semibold">Trial Search</h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            Semantic search across clinical trials
          </p>
        </div>
        <TrialSearchForm />
      </div>
    </div>
  );
}
