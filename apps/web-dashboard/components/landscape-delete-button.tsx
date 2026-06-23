"use client";

import { useTransition } from "react";
import { useRouter } from "next/navigation";
import { Trash2 } from "lucide-react";
import { deleteLandscapeAction } from "@/lib/actions/landscape/actions";

export function LandscapeDeleteButton({ id }: { id: string }) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();

  const remove = () => {
    startTransition(async () => {
      await deleteLandscapeAction(id);
      router.refresh();
    });
  };

  return (
    <button
      type="button"
      onClick={remove}
      disabled={pending}
      aria-label="Delete landscape"
      className="rounded-md p-1.5 text-muted-foreground transition-colors hover:text-destructive disabled:opacity-50"
    >
      <Trash2 className="h-3.5 w-3.5" />
    </button>
  );
}
