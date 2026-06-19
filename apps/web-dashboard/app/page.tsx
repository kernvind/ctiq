import Link from "next/link";
import { Suspense } from "react";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { Sparkles } from "lucide-react";
import { TrialSearchForm } from "@/components/trial-search-form";
import { PublicHeader } from "@/components/public-header";

export default async function HomePage() {
  // Logged-in users get the richer dashboard; the public home is for anonymous visitors.
  const token = (await cookies()).get("token");
  if (token) redirect("/dashboard");

  return (
    <div className="flex min-h-svh flex-col">
      <PublicHeader />

      <main className="flex-1 px-6 py-16">
        <div className="mx-auto max-w-2xl flex flex-col gap-6">
          <div className="text-center">
            <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">
              Find clinical trials in plain language
            </h1>
            <p className="mx-auto mt-2 max-w-xl text-sm text-muted-foreground">
              Describe a condition, treatment, or patient profile and search across clinical
              trials by meaning — no account required.
            </p>
          </div>

          {/* Submitting takes the visitor into the /search master-detail experience. */}
          <Suspense fallback={<div className="h-9 animate-pulse rounded-md bg-muted" />}>
            <TrialSearchForm basePath="/search" />
          </Suspense>

          <div className="rounded-lg border bg-muted/30 px-4 py-3">
            <div className="flex items-start gap-2">
              <Sparkles className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
              <p className="text-xs text-muted-foreground">
                <span className="font-medium text-foreground">Create a free account</span> to
                unlock AI-powered features — plain-language summaries, eligibility help, and chat
                with an assistant about a trial.{" "}
                <Link href="/signup" className="font-medium text-primary hover:underline">
                  Register
                </Link>
                .
              </p>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
