import { roleLabel } from "@/lib/role";
import type { CurrentUser } from "@/lib/actions/user/me/actions";

/**
 * Compact identity chip for the dashboard header: who's signed in + their role. Renders
 * nothing when the user is unavailable (e.g. a momentarily expired token), so the chrome
 * degrades gracefully rather than erroring.
 */
export function UserBadge({ user }: { user: CurrentUser | null }) {
  if (!user) return null;
  return (
    <div className="flex items-center gap-2">
      <span className="hidden text-xs text-muted-foreground sm:inline">
        {user.name ?? user.email}
      </span>
      <span className="inline-flex items-center rounded bg-primary/10 px-1.5 py-0.5 text-[10px] font-medium text-primary">
        {roleLabel(user.role)}
      </span>
    </div>
  );
}
