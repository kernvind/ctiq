"use client";

import { useState } from "react";
import { MatchView } from "@/features/eligibility-match/match-view";
import { PortfolioManager, type PortfolioEntry } from "./portfolio-manager";

/**
 * Portfolio screening workspace (site-payer wedge). Owns the portfolio list so the manager and
 * the screening form share one source of truth — the "Screen patient" button enables the instant
 * a trial is added and disables when the portfolio is emptied.
 */
export function PortfolioScreen({
  initialPortfolio,
}: {
  initialPortfolio: PortfolioEntry[];
}) {
  const [entries, setEntries] = useState<PortfolioEntry[]>(initialPortfolio);
  return (
    <div className="flex flex-col">
      <PortfolioManager entries={entries} setEntries={setEntries} />
      <MatchView mode="portfolio" canScreen={entries.length > 0} />
    </div>
  );
}
