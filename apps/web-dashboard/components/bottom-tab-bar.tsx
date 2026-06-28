"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@repo/ui/lib/utils";
import type { CurrentUser } from "@/lib/actions/user/me/actions";
import { visibleNavLinks } from "./dashboard-nav-links";

export function BottomTabBar({ user }: { user: CurrentUser | null }) {
  const pathname = usePathname();
  const role = user?.role ?? "PATIENT";
  const tabs = visibleNavLinks(role);

  return (
    <nav className="fixed bottom-0 left-0 right-0 z-50 flex border-t bg-background md:hidden">
      {tabs.map(({ href, label, shortLabel, icon: Icon }) => {
        const active = pathname === href;
        return (
          <Link
            key={href}
            href={href}
            className={cn(
              "flex flex-1 flex-col items-center justify-center gap-1 py-3 text-[10px] font-medium transition-colors",
              active
                ? "text-foreground"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            <Icon
              className={cn("size-5", active && "stroke-[2.5px]")}
              aria-hidden
            />
            {shortLabel ?? label}
          </Link>
        );
      })}
    </nav>
  );
}
