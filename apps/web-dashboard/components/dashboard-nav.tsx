"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@repo/ui/lib/utils";
import type { CurrentUser } from "@/lib/actions/user/me/actions";
import { visibleNavLinks } from "./dashboard-nav-links";

export function DashboardNav({ user }: { user: CurrentUser | null }) {
  const pathname = usePathname();
  const role = user?.role ?? "PATIENT";
  const visibleLinks = visibleNavLinks(role);
  return (
    <nav className="flex items-center gap-1">
      {visibleLinks.map(({ href, label }) => (
        <Link
          key={href}
          href={href}
          className={cn(
            "rounded-md px-3 py-1.5 text-xs font-medium transition-colors",
            pathname === href
              ? "bg-muted text-foreground"
              : "text-muted-foreground hover:text-foreground hover:bg-muted/50",
          )}
        >
          {label}
        </Link>
      ))}
    </nav>
  );
}
