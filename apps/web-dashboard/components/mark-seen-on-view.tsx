"use client";

import { useEffect, useRef } from "react";
import { markLandscapeSeenAction } from "@/lib/actions/landscape/actions";

/**
 * Updates a landscape's monitoring snapshot once, on view. Viewing the landscape *is*
 * the "check" — so after the page has computed and shown the delta, this records the
 * current ids as seen, making the next visit's "new since last check" accurate.
 */
export function MarkSeenOnView({
  id,
  nctIds,
}: {
  id: string;
  nctIds: string[];
}) {
  const done = useRef(false);
  useEffect(() => {
    if (done.current) return;
    done.current = true;
    void markLandscapeSeenAction(id, nctIds);
  }, [id, nctIds]);
  return null;
}
