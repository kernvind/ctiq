import Link from "next/link";

/** Header for the public (no-account) pages: home and trial detail. */
export function PublicHeader() {
  return (
    <header className="border-b px-6 py-3 flex items-center justify-between gap-4">
      <Link href="/" className="text-sm font-semibold">
        CTIQ Health
      </Link>
      <nav className="flex items-center gap-4">
        <Link
          href="/login"
          className="text-xs font-medium text-muted-foreground hover:text-foreground transition-colors"
        >
          Sign in
        </Link>
        <Link
          href="/signup"
          className="rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
        >
          Register
        </Link>
      </nav>
    </header>
  );
}
