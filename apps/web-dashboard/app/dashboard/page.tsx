export default function DashboardPage() {
  return (
    <div className="flex min-h-svh flex-col">
      <header className="border-b px-6 py-4 flex items-center justify-between">
        <h1 className="text-xl font-semibold">Dashboard</h1>
        <form action="/api/logout" method="POST">
          <button
            type="submit"
            className="text-sm text-muted-foreground hover:text-foreground transition-colors"
          >
            Sign out
          </button>
        </form>
      </header>
      <main className="flex-1 p-6">
        <div className="max-w-4xl mx-auto">
          <h2 className="text-2xl font-bold mb-2">Welcome back</h2>
          <p className="text-muted-foreground">
            You are successfully logged in.
          </p>
        </div>
      </main>
    </div>
  );
}
