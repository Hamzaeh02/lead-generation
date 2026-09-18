"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { AppShell } from "@/components/AppShell";
import { EmptyState } from "@/components/ui/EmptyState";
import { Pill } from "@/components/ui/Pill";
import { Spinner } from "@/components/ui/Spinner";
import { Table, TableBody, TableHead, Td, Th, Tr } from "@/components/ui/Table";
import { listLeads, type LeadStatus } from "@/lib/api";
import { useWorkspace } from "@/lib/workspace-context";

const statusOptions: { value: LeadStatus | ""; label: string }[] = [
  { value: "", label: "All statuses" },
  { value: "new", label: "New" },
  { value: "verified", label: "Verified" },
  { value: "ready_for_outreach", label: "Ready for outreach" },
  { value: "contacted", label: "Contacted" },
  { value: "opened", label: "Opened" },
  { value: "clicked", label: "Clicked" },
  { value: "replied", label: "Replied" },
  { value: "interested", label: "Interested" },
  { value: "meeting", label: "Meeting" },
  { value: "won", label: "Won" },
  { value: "lost", label: "Lost" },
  { value: "unsubscribed", label: "Unsubscribed" },
  { value: "bounced", label: "Bounced" },
];

const statusTone: Record<string, "success" | "warning" | "danger" | "accent" | "muted"> = {
  won: "success",
  meeting: "success",
  verified: "success",
  interested: "accent",
  replied: "accent",
  ready_for_outreach: "accent",
  bounced: "danger",
  unsubscribed: "danger",
  lost: "danger",
  contacted: "warning",
  opened: "warning",
  clicked: "warning",
};

function LeadsContent() {
  const { activeWorkspace } = useWorkspace();
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<LeadStatus | "">("");

  const leadsQuery = useQuery({
    queryKey: ["leads", activeWorkspace?.id, query, status],
    queryFn: () =>
      listLeads(activeWorkspace!.id, {
        search: query || undefined,
        status: status || undefined,
        limit: 100,
      }),
    enabled: !!activeWorkspace,
  });

  const leads = leadsQuery.data ?? [];

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-[22px] font-semibold tracking-tight">Leads</h1>
          <p className="mt-1 text-[13px] text-fgMuted">Every contact in this workspace&apos;s CRM pipeline.</p>
        </div>
        <div className="flex gap-2">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              setQuery(search);
            }}
          >
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search name, email, company…"
              className="w-64 rounded-lg border border-border bg-surface px-3 py-1.5 text-[13px] text-fg placeholder:text-fgMuted focus:border-accent focus:outline-none"
            />
          </form>
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value as LeadStatus | "")}
            className="rounded-lg border border-border bg-surface px-2.5 py-1.5 text-[13px] text-fg focus:border-accent focus:outline-none"
          >
            {statusOptions.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {leadsQuery.isLoading && (
        <div className="flex items-center gap-2 text-[13px] text-fgMuted">
          <Spinner /> Loading leads…
        </div>
      )}

      {leadsQuery.isSuccess && leads.length === 0 && (
        <EmptyState
          title="No leads match these filters"
          description="Discover companies and people, or import a CSV, to start building your pipeline."
        />
      )}

      {leads.length > 0 && (
        <Table>
          <TableHead>
            <Th>Name</Th>
            <Th>Company</Th>
            <Th>Title</Th>
            <Th>Email</Th>
            <Th>Status</Th>
            <Th>Last seen</Th>
          </TableHead>
          <TableBody>
            {leads.map((lead) => (
              <Tr key={lead.id}>
                <Td>
                  <Link href={`/leads/${lead.id}`} className="font-medium text-fg hover:text-accent">
                    {lead.full_name ?? lead.email ?? "Unnamed contact"}
                  </Link>
                </Td>
                <Td className="text-fgMuted">{lead.company_name ?? "—"}</Td>
                <Td className="text-fgMuted">{lead.job_title ?? "—"}</Td>
                <Td className="text-fgMuted">{lead.email ?? "—"}</Td>
                <Td>
                  <Pill tone={statusTone[lead.status] ?? "muted"}>{lead.status.replace(/_/g, " ")}</Pill>
                </Td>
                <Td className="text-fgMuted">{new Date(lead.last_seen).toLocaleDateString()}</Td>
              </Tr>
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  );
}

export default function LeadsPage() {
  return (
    <AppShell title="Leads">
      <LeadsContent />
    </AppShell>
  );
}
