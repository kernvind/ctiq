import { DashboardNav } from "@/components/dashboard-nav";
import { BottomTabBar } from "@/components/bottom-tab-bar";
import { UserBadge } from "@/components/user-badge";
import { getCurrentUser } from "@/lib/actions/user/me/actions";

export default async function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const user = await getCurrentUser();

  return (
    <div className="flex min-h-svh flex-col">
      <header className="border-b px-6 py-3 flex items-center justify-between gap-4">
        <div className="flex items-center gap-6">
          <span className="text-sm font-semibold">CTIQ Health</span>
          <div className="hidden md:flex">
            <DashboardNav />
          </div>
        </div>
        <div className="flex items-center gap-4">
          <UserBadge user={user} />
          <form action="/api/logout" method="POST">
            <button
              type="submit"
              className="text-xs text-muted-foreground hover:text-foreground transition-colors"
            >
              Sign out
            </button>
          </form>
        </div>
      </header>

      <main className="flex-1 pb-16 md:pb-0">{children}</main>

      <BottomTabBar />
    </div>
  );
}
