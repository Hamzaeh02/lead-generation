"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { AppShell } from "@/components/AppShell";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { Pill } from "@/components/ui/Pill";
import { Spinner } from "@/components/ui/Spinner";
import {
  findDecisionMakers,
  getCompany,
  getIntentScore,
  getLeadScore,
  listCompanySources,
  listLeads,
  type Contact,
} from "@/lib/api";
import { useWorkspace } from "@/lib/workspace-context";

const DEFAULT_TITLES = "owner, founder, president, ceo, general manager";

function ContactRow({
  contact,
  workspaceId,
}: {
  contact: Contact;
  workspaceId: string;
}) {
  const scoreQuery = useQuery({
    queryKey: ["lead-score", workspaceId, contact.id],
    queryFn: () => getLeadScore(workspaceId, contact.id),
  });

  return (
    <Link
      href={`/leads/${contact.id}`}
      className="flex items-center justify-between gap-3 px-4 py-3 hover:bg-surface2"
    >
      <div>
        <div className="text-[13px] font-medium text-fg">
          {contact.full_name ?? contact.email ?? "Unnamed contact"}
        </div>
        <div className="text-[12px] text-fgMuted">{contact.job_title ?? contact.email ?? "—"}</div>
      </div>
      <div className="flex items-center gap-3">
        {scoreQuery.data && (
          <span
            className="font-mono text-[12.5px] tabular-nums text-fgMuted"
            title="Lead score: fit + intent + authority + reachability + engagement"
          >
            {scoreQuery.data.score}/100
          </span>
        )}
        <Pill tone={statusTone[contact.status] ?? "muted"}>{contact.status.replace(/_/g, " ")}</Pill>
      </div>
    </Link>
  );
}

function fieldRow(label: string, value: React.ReactNode) {
  if (!value) return null;
  return (
    <div className="flex items-center justify-between border-b border-border py-2.5 text-[13px] last:border-0">
      <span className="text-fgMuted">{label}</span>
      <span className="text-fg">{value}</span>
    </div>
  );
}

const statusTone: Record<string, "success" | "warning" | "danger" | "accent" | "muted"> = {
  won: "success",
  meeting: "success",
  interested: "accent",
  replied: "accent",
  bounced: "danger",
  unsubscribed: "danger",
  lost: "danger",
};

function CompanyDetailContent({ companyId }: { companyId: string }) {
  const { activeWorkspace } = useWorkspace();
  const workspaceId = activeWorkspace?.id;
  const queryClient = useQueryClient();
  const [titlesInput, setTitlesInput] = useState(DEFAULT_TITLES);

  const companyQuery = useQuery({
    queryKey: ["company", workspaceId, companyId],
    queryFn: () => getCompany(workspaceId!, companyId),
    enabled: !!workspaceId,
  });

  const contactsQuery = useQuery({
    queryKey: ["company-contacts", workspaceId, companyId],
    queryFn: () => listLeads(workspaceId!, { company_id: companyId, limit: 100 }),
    enabled: !!workspaceId,
  });

  const sourcesQuery = useQuery({
    queryKey: ["company-sources", workspaceId, companyId],
    queryFn: () => listCompanySources(workspaceId!, companyId),
    enabled: !!workspaceId,
  });

  const intentQuery = useQuery({
    queryKey: ["company-intent", workspaceId, companyId],
    queryFn: () => getIntentScore(workspaceId!, companyId),
    enabled: !!workspaceId,
  });

  const decisionMakersMutation = useMutation({
    mutationFn: () =>
      findDecisionMakers(
        workspaceId!,
        companyId,
        titlesInput
          .split(",")
          .map((t) => t.trim())
          .filter(Boolean)
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["company-contacts", workspaceId, companyId] });
    },
  });

  if (companyQuery.isLoading) {
    return (
      <div className="flex items-center gap-2 text-[13px] text-fgMuted">
        <Spinner /> Loading company…
      </div>
    );
  }

  if (companyQuery.isError || !companyQuery.data) {
    return <EmptyState title="Company not found" description="It may have been removed, or you may not have access." />;
  }

  const company = companyQuery.data;

  return (
    <div className="flex flex-col gap-8">
      <div>
        <div className="mb-1 flex items-center gap-2 text-[12px] text-fgMuted">
          <Link href="/companies" className="hover:text-fg">
            Companies
          </Link>
          <span>/</span>
        </div>
        <h1 className="text-[22px] font-semibold tracking-tight">
          {company.name ?? "Unnamed company"}
        </h1>
        <p className="mt-1 text-[13px] text-fgMuted">
          {[company.industry, company.city, company.state].filter(Boolean).join(" · ") || "No profile details yet"}
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <h2 className="mb-1 text-[13px] font-semibold text-fg">Profile</h2>
          <div className="flex flex-col">
            {fieldRow(
              "Website",
              company.website && (
                <a href={company.website} target="_blank" rel="noreferrer" className="text-accent hover:underline">
                  {company.website}
                </a>
              )
            )}
            {fieldRow("Domain", company.domain)}
            {fieldRow("Phone", company.phone)}
            {fieldRow(
              "Address",
              [company.address, company.city, company.state, company.country, company.postal_code]
                .filter(Boolean)
                .join(", ") || null
            )}
            {fieldRow("Employees", company.employee_count)}
            {fieldRow(
              "LinkedIn",
              company.linkedin_url && (
                <a href={company.linkedin_url} target="_blank" rel="noreferrer" className="text-accent hover:underline">
                  View profile
                </a>
              )
            )}
            {fieldRow("First seen", new Date(company.first_seen).toLocaleDateString())}
            {fieldRow("Last seen", new Date(company.last_seen).toLocaleDateString())}
          </div>
          {company.description && (
            <p className="mt-3 border-t border-border pt-3 text-[13px] leading-relaxed text-fgMuted">
              {company.description}
            </p>
          )}
        </Card>

        <div className="flex flex-col gap-4">
          <Card>
            <h2 className="mb-2 text-[13px] font-semibold text-fg">Intent score</h2>
            {intentQuery.data ? (
              <>
                <div className="font-mono text-[28px] font-semibold tabular-nums text-fg">
                  {intentQuery.data.score}
                  <span className="text-[13px] font-normal text-fgMuted">/100</span>
                </div>
                <p className="mt-1 text-[12px] text-fgMuted">
                  {intentQuery.data.signal_count} signal{intentQuery.data.signal_count === 1 ? "" : "s"} on file
                </p>
              </>
            ) : (
              <Spinner />
            )}
          </Card>
        </div>
      </div>

      <section className="flex flex-col gap-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-[13px] font-semibold text-fg">
            Contacts {contactsQuery.data && `(${contactsQuery.data.length})`}
          </h2>
          {company.domain ? (
            <div className="flex flex-wrap items-center gap-2">
              <input
                value={titlesInput}
                onChange={(e) => setTitlesInput(e.target.value)}
                placeholder="owner, founder, ceo…"
                className="w-64 rounded-lg border border-border bg-surface px-2.5 py-1.5 text-[12px] text-fg placeholder:text-fgMuted focus:border-accent focus:outline-none"
              />
              <Button
                variant="ghost"
                disabled={decisionMakersMutation.isPending}
                onClick={() => decisionMakersMutation.mutate()}
              >
                {decisionMakersMutation.isPending ? <Spinner className="h-3.5 w-3.5" /> : "Find decision-makers"}
              </Button>
            </div>
          ) : (
            <span className="text-[12px] text-fgMuted">Add a domain to search for decision-makers.</span>
          )}
        </div>

        {decisionMakersMutation.isError && (
          <p className="text-[12.5px] text-danger">
            {(decisionMakersMutation.error as { response?: { data?: { detail?: string } } })?.response?.data
              ?.detail ?? "Decision-maker search failed."}
          </p>
        )}
        {decisionMakersMutation.isSuccess && (
          <p className="text-[12.5px] text-fgMuted">
            {decisionMakersMutation.data.contacts_created} new, {decisionMakersMutation.data.contacts_matched}{" "}
            already on file
            {decisionMakersMutation.data.contacts.length === 0 && " — nobody found for these titles at this domain."}
          </p>
        )}

        {contactsQuery.data && contactsQuery.data.length > 0 ? (
          <Card className="flex flex-col divide-y divide-border p-0">
            {contactsQuery.data.map((contact) => (
              <ContactRow key={contact.id} contact={contact} workspaceId={workspaceId!} />
            ))}
          </Card>
        ) : (
          <EmptyState title="No contacts found at this company yet" />
        )}
      </section>

      {intentQuery.data && intentQuery.data.signals.length > 0 && (
        <section className="flex flex-col gap-3">
          <h2 className="text-[13px] font-semibold text-fg">Intent signals</h2>
          <Card className="flex flex-col divide-y divide-border p-0">
            {intentQuery.data.signals.map((signal) => (
              <div key={signal.id} className="flex flex-col gap-1 px-4 py-3">
                <div className="flex items-center justify-between">
                  <span className="text-[13px] font-medium text-fg">
                    {signal.signal_type.replace(/_/g, " ")}
                  </span>
                  <span className="text-[12px] text-fgMuted">
                    {new Date(signal.detected_at).toLocaleDateString()}
                  </span>
                </div>
                {signal.signal_text && <p className="text-[12.5px] text-fgMuted">{signal.signal_text}</p>}
                <a
                  href={signal.source_url}
                  target="_blank"
                  rel="noreferrer"
                  className="text-[12px] text-accent hover:underline"
                >
                  Source
                </a>
              </div>
            ))}
          </Card>
        </section>
      )}

      <section className="flex flex-col gap-3">
        <h2 className="text-[13px] font-semibold text-fg">Provenance</h2>
        {sourcesQuery.data && sourcesQuery.data.length > 0 ? (
          <Card className="flex flex-col divide-y divide-border p-0">
            {sourcesQuery.data.map((source) => (
              <div key={source.id} className="flex items-center justify-between gap-3 px-4 py-3 text-[13px]">
                <span className="font-mono text-fg">{source.provider}</span>
                <span className="text-fgMuted">{source.source_type}</span>
                {source.source_url ? (
                  <a href={source.source_url} target="_blank" rel="noreferrer" className="text-accent hover:underline">
                    View source
                  </a>
                ) : (
                  <span className="text-fgMuted">—</span>
                )}
                <span className="text-fgMuted">{new Date(source.retrieved_at).toLocaleDateString()}</span>
              </div>
            ))}
          </Card>
        ) : (
          <EmptyState title="No provenance records" description="This company has no recorded source yet." />
        )}
      </section>
    </div>
  );
}

export default function CompanyDetailPage() {
  const params = useParams<{ id: string }>();
  return (
    <AppShell title="Company">
      <CompanyDetailContent companyId={params.id} />
    </AppShell>
  );
}
