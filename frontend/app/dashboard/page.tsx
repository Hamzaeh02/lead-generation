"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { AppShell } from "@/components/AppShell";
import { Card } from "@/components/ui/Card";
import { Spinner } from "@/components/ui/Spinner";
import { getAnalyticsOverview } from "@/lib/api";
import { useWorkspace } from "@/lib/workspace-context";

function formatPercent(value: number | null): string {
  return value === null ? "—" : `${Math.round(value * 1000) / 10}%`;
}

function StatCard({ label, value, hint }: { label: string; value: React.ReactNode; hint?: string }) {
  return (
    <Card className="flex flex-col gap-1.5">
      <span className="text-[11.5px] font-medium uppercase tracking-wide text-fgMuted">{label}</span>
      <span className="font-mono text-[26px] font-semibold leading-none tabular-nums text-fg">
        {value}
      </span>
      {hint && <span className="text-[12px] text-fgMuted">{hint}</span>}
    </Card>
  );
}

function QuickLink({ href, label, description }: { href: string; label: string; description: string }) {
  return (
    <Link
      href={href}
      className="flex flex-col gap-1 rounded-xl border border-border bg-surface p-4 shadow-card hover:border-accent"
    >
      <span className="text-[13px] font-medium text-fg">{label}</span>
      <span className="text-[12px] text-fgMuted">{description}</span>
    </Link>
  );
}

function DashboardContent() {
  const { activeWorkspace, currentUser } = useWorkspace();

  const overviewQuery = useQuery({
    queryKey: ["analytics-overview", activeWorkspace?.id],
    queryFn: () => getAnalyticsOverview(activeWorkspace!.id),
    enabled: !!activeWorkspace,
  });

  const displayName = currentUser?.full_name ?? currentUser?.email ?? "";
  const overview = overviewQuery.data;

  return (
    <div className="flex flex-col gap-9">
      <div>
        <h1 className="text-[22px] font-semibold tracking-tight">Welcome back, {displayName.split(" ")[0]}</h1>
        <p className="mt-1 text-[13px] text-fgMuted">
          {activeWorkspace ? activeWorkspace.name : "No workspace selected"} — here&apos;s what&apos;s real right now.
        </p>
      </div>

      {overviewQuery.isLoading && (
        <div className="flex items-center gap-2 text-[13px] text-fgMuted">
          <Spinner /> Loading analytics…
        </div>
      )}

      {overview && (
        <>
          <section className="flex flex-col gap-3">
            <h2 className="text-[13px] font-semibold text-fg">Pipeline</h2>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <StatCard label="Companies" value={overview.total_companies} />
              <StatCard label="Contacts" value={overview.total_contacts} />
              <StatCard label="Verified emails" value={overview.verified_emails} />
              <StatCard
                label="High-intent leads"
                value={overview.high_intent_leads}
                hint="intent score ≥ 50"
              />
              <StatCard label="Meetings" value={overview.meetings} />
              <StatCard label="Won" value={overview.conversions} />
            </div>
          </section>

          <section className="flex flex-col gap-3">
            <h2 className="text-[13px] font-semibold text-fg">Outreach</h2>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <StatCard label="Sent" value={overview.emails_sent} />
              <StatCard label="Delivery rate" value={formatPercent(overview.delivery_rate)} />
              <StatCard label="Reply rate" value={formatPercent(overview.reply_rate)} />
              <StatCard label="Bounce rate" value={formatPercent(overview.bounce_rate)} />
            </div>
          </section>

          {overview.top_sources.length > 0 && (
            <section className="flex flex-col gap-3">
              <h2 className="text-[13px] font-semibold text-fg">Top sources</h2>
              <Card className="flex flex-col gap-2 p-4">
                {overview.top_sources.map((source) => (
                  <div key={source.provider} className="flex items-center justify-between text-[13px]">
                    <span className="text-fg">{source.provider}</span>
                    <span className="font-mono tabular-nums text-fgMuted">{source.count}</span>
                  </div>
                ))}
              </Card>
            </section>
          )}

          {overview.top_campaigns.length > 0 && (
            <section className="flex flex-col gap-3">
              <h2 className="text-[13px] font-semibold text-fg">Top campaigns</h2>
              <Card className="flex flex-col gap-2 p-4">
                {overview.top_campaigns.map((c) => (
                  <div key={c.campaign_id} className="flex items-center justify-between text-[13px]">
                    <span className="text-fg">{c.name}</span>
                    <span className="font-mono tabular-nums text-fgMuted">
                      {c.sent} sent · {c.replied} replied
                    </span>
                  </div>
                ))}
              </Card>
            </section>
          )}
        </>
      )}

      <section className="flex flex-col gap-3">
        <h2 className="text-[13px] font-semibold text-fg">Quick actions</h2>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <QuickLink href="/discover" label="Find companies" description="Run a provider search" />
          <QuickLink href="/leads" label="Review leads" description="Verify emails, check intent" />
          <QuickLink href="/campaigns" label="Start outreach" description="Build a sequence" />
        </div>
      </section>
    </div>
  );
}

export default function DashboardPage() {
  return (
    <AppShell title="Dashboard">
      <DashboardContent />
    </AppShell>
  );
}
