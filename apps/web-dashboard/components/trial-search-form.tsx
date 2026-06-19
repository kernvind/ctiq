"use client";

import { useSearchParams } from "next/navigation";
import { Button } from "@repo/ui/components/button";
import { Input } from "@repo/ui/components/input";
import { Search } from "lucide-react";
import Form from "next/form";
/**
 * Trial-search input. Navigates to `${basePath}?q=<query>` on submit — the query lives in
 * the URL, which drives the (persistent) results list. Lives in a layout, which can't read
 * `searchParams`, so it seeds its value from `useSearchParams()` on the client.
 */

export function TrialSearchForm({ basePath }: { basePath: string }) {
  const searchParams = useSearchParams();
  const currentQuery = searchParams.get("q") ?? "";

  return (
    // Next.js Form automatically updates the URL ?q=... on submit
    <Form action={basePath} className="w-full">
      <div className="flex w-full items-center gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground pointer-events-none" />
          <Input
            name="q"
            type="text"
            placeholder="Describe the condition, treatment, or patient profile… (10–500 chars)"
            defaultValue={currentQuery}
            className="pl-8 w-full"
            minLength={10}
            maxLength={500}
            required
          />
        </div>
        <Button type="submit">Search</Button>
      </div>
    </Form>
  );
}
