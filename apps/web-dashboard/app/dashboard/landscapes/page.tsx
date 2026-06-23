import Link from "next/link";
import { Map, ChevronRight } from "lucide-react";
import { getLandscapes } from "@/lib/landscapes";
import { LandscapeDeleteButton } from "@/components/landscape-delete-button";

export default async function LandscapesPage() {
  const landscapes = await getLandscapes();

  return (
    <div className="p-6">
      <div className="mx-auto flex max-w-3xl flex-col gap-4">
        <div>
          <h2 className="text-lg font-semibold">Landscapes</h2>
          <p className="mt-0.5 text-xs text-muted-foreground">
            Saved searches you monitor for new trials.
          </p>
        </div>

        {landscapes.length === 0 ? (
          <p className="rounded-lg border p-6 text-center text-sm text-muted-foreground">
            No landscapes yet. Run a search in{" "}
            <Link href="/dashboard/trials" className="text-primary hover:underline">
              Trial Search
            </Link>{" "}
            and tap “Save as landscape”.
          </p>
        ) : (
          <div className="flex flex-col gap-2">
            {landscapes.map((l) => (
              <div
                key={l.id}
                className="flex items-center gap-3 rounded-lg border bg-background p-3"
              >
                <Map className="h-4 w-4 shrink-0 text-muted-foreground" />
                <Link
                  href={`/dashboard/landscapes/${l.id}`}
                  className="min-w-0 flex-1"
                >
                  <p className="truncate text-sm font-medium">{l.name}</p>
                  <p className="truncate text-[11px] text-muted-foreground">
                    “{l.spec.q}”
                    {l.lastCheckedAt
                      ? ` · ${l.lastSeenNctIds.length} trials at last check`
                      : " · not checked yet"}
                  </p>
                </Link>
                <LandscapeDeleteButton id={l.id} />
                <Link
                  href={`/dashboard/landscapes/${l.id}`}
                  aria-label={`Open ${l.name}`}
                >
                  <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />
                </Link>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
