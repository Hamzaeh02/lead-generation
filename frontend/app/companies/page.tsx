"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { AppShell } from "@/components/AppShell";
import { EmptyState } from "@/components/ui/EmptyState";
import { Spinner } from "@/components/ui/Spinner";
import { Table, TableBody, TableHead, Td, Th, Tr } from "@/components/ui/Table";
import { listCompanies } from "@/lib/api";
import { useWorkspace } from "@/lib/workspace-context";

function CompaniesContent() {
  const { activeWorkspace } = useWorkspace();
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");

  const companiesQuery = useQuery({
    queryKey: ["companies", activeWorkspace?.id, query],
    queryFn: () => listCompanies(activeWorkspace!.id, { search: query || undefined, limit: 100 }),
    enabled: !!activeWorkspace,
  });

  const companies = companiesQuery.data ?? [];

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-[22px] font-semibold tracking-tight">Companies</h1>
          <p className="mt-1 text-[13px] text-fgMuted">
            Every business discovered or imported into this workspace.
          </p>
        </div>
        <form
          className="flex gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            setQuery(search);
          }}
        >
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search name or domain…"
            className="w-64 rounded-lg border border-border bg-surface px-3 py-1.5 text-[13px] text-fg placeholder:text-fgMuted focus:border-accent focus:outline-none"
          />
        </form>
      </div>

      {companiesQuery.isLoading && (
        <div className="flex items-center gap-2 text-[13px] text-fgMuted">
          <Spinner /> Loading companies…
        </div>
      )}

      {companiesQuery.isSuccess && companies.length === 0 && (
        <EmptyState
          title={query ? "No companies match that search" : "No companies yet"}
          description={
            query
              ? "Try a different name or domain."
              : "Run a discovery search to start populating this workspace."
          }
          action={
            !query && (
              <Link
                href="/discover"
                className="rounded-lg bg-accent px-3.5 py-2 text-[13px] font-medium text-white hover:opacity-90"
              >
                Discover companies
              </Link>
            )
          }
        />
      )}

      {companies.length > 0 && (
        <Table>
          <TableHead>
            <Th>Name</Th>
            <Th>Domain</Th>
            <Th>Location</Th>
            <Th>Industry</Th>
            <Th className="text-right">Employees</Th>
            <Th>Last seen</Th>
          </TableHead>
          <TableBody>
            {companies.map((company) => (
              <Tr key={company.id}>
                <Td>
                  <Link href={`/companies/${company.id}`} className="font-medium text-fg hover:text-accent">
                    {company.name ?? "Unnamed company"}
                  </Link>
                </Td>
                <Td className="text-fgMuted">{company.domain ?? "—"}</Td>
                <Td className="text-fgMuted">
                  {[company.city, company.state].filter(Boolean).join(", ") || "—"}
                </Td>
                <Td className="text-fgMuted">{company.industry ?? "—"}</Td>
                <Td className="text-right font-mono tabular-nums text-fgMuted">
                  {company.employee_count ?? "—"}
                </Td>
                <Td className="text-fgMuted">{new Date(company.last_seen).toLocaleDateString()}</Td>
              </Tr>
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  );
}

export default function CompaniesPage() {
  return (
    <AppShell title="Companies">
      <CompaniesContent />
    </AppShell>
  );
}
