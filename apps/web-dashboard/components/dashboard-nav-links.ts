import {
  Bookmark,
  LayoutDashboard,
  Map,
  Search,
  Stethoscope,
  type LucideIcon,
} from "lucide-react";
import type { CurrentUser } from "@/lib/actions/user/me/actions";

export type Role = NonNullable<CurrentUser>["role"];

export type NavLink = {
  href: string;
  label: string;
  // Compact label for the mobile bottom bar; falls back to `label`.
  shortLabel?: string;
  icon: LucideIcon;
  // Omit `roles` for links every role sees; otherwise the link shows only to the
  // listed roles. Eligibility Match is CLINICIAN-only (see the api-core RBAC gate).
  roles?: readonly Role[];
};

// Single source of truth shared by the desktop nav and the mobile bottom bar, so the
// two can't drift on which links a role sees.
export const NAV_LINKS: readonly NavLink[] = [
  { href: "/dashboard", label: "Overview", icon: LayoutDashboard },
  { href: "/dashboard/trials", label: "Trial Search", shortLabel: "Trials", icon: Search },
  { href: "/dashboard/saved", label: "Saved", icon: Bookmark },
  { href: "/dashboard/landscapes", label: "Landscapes", icon: Map, roles: ["ANALYST"] },
  {
    href: "/dashboard/match",
    label: "Eligibility Match",
    shortLabel: "Match",
    icon: Stethoscope,
    roles: ["CLINICIAN"],
  },
];

export function visibleNavLinks(role: Role): NavLink[] {
  return NAV_LINKS.filter((link) => !link.roles || link.roles.includes(role));
}
