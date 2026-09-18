import Link from "next/link";

export default function HomePage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-6 bg-bg px-6 text-center text-fg">
      <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-accent">
        <svg viewBox="0 0 16 16" fill="none" className="h-5 w-5">
          <path
            d="M2 8L6 4M6 4L14 4M6 4L6 12M14 4L10 8M14 4V12L10 8"
            stroke="white"
            strokeWidth={1.4}
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </span>
      <div className="flex flex-col gap-2">
        <h1 className="text-2xl font-semibold tracking-tight">Lead Intelligence Platform</h1>
        <p className="text-[14px] text-fgMuted">
          Discover, enrich, verify, and reach the right decision-makers.
        </p>
      </div>
      <div className="flex gap-3">
        <Link
          href="/login"
          className="rounded-lg bg-accent px-4 py-2 text-[13px] font-medium text-white hover:opacity-90"
        >
          Log in
        </Link>
        <Link
          href="/register"
          className="rounded-lg border border-border bg-surface px-4 py-2 text-[13px] font-medium text-fg hover:bg-surface2"
        >
          Create workspace
        </Link>
      </div>
    </main>
  );
}
