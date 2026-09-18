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
  addCampaignStep,
  cancelCampaign,
  enrollContacts,
  getCampaign,
  getCampaignReport,
  listLeads,
  pauseCampaign,
  previewCampaignStep,
  processCampaignNow,
  resumeCampaign,
  startCampaign,
  type Campaign,
  type CampaignStatus,
} from "@/lib/api";
import { useWorkspace } from "@/lib/workspace-context";

const statusTone: Record<CampaignStatus, "success" | "warning" | "danger" | "accent" | "muted"> = {
  running: "success",
  scheduled: "accent",
  paused: "warning",
  draft: "muted",
  completed: "success",
  cancelled: "danger",
};

const inputClass =
  "rounded-lg border border-border bg-surface px-3 py-2 text-[13px] text-fg placeholder:text-fgMuted focus:border-accent focus:outline-none";

function SectionCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <Card className="flex flex-col gap-3">
      <h2 className="text-[13px] font-semibold text-fg">{title}</h2>
      {children}
    </Card>
  );
}

function LifecycleActions({ campaign, workspaceId }: { campaign: Campaign; workspaceId: string }) {
  const queryClient = useQueryClient();
  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["campaign", workspaceId, campaign.id] });

  const startMutation = useMutation({ mutationFn: () => startCampaign(workspaceId, campaign.id), onSuccess: invalidate });
  const pauseMutation = useMutation({ mutationFn: () => pauseCampaign(workspaceId, campaign.id), onSuccess: invalidate });
  const resumeMutation = useMutation({ mutationFn: () => resumeCampaign(workspaceId, campaign.id), onSuccess: invalidate });
  const cancelMutation = useMutation({ mutationFn: () => cancelCampaign(workspaceId, campaign.id), onSuccess: invalidate });

  const pending =
    startMutation.isPending || pauseMutation.isPending || resumeMutation.isPending || cancelMutation.isPending;
  const terminal = campaign.status === "completed" || campaign.status === "cancelled";

  return (
    <div className="flex flex-wrap items-center gap-2">
      <Pill tone={statusTone[campaign.status]}>{campaign.status}</Pill>
      {(campaign.status === "draft" || campaign.status === "scheduled") && (
        <Button variant="ghost" disabled={pending || campaign.steps.length === 0} onClick={() => startMutation.mutate()}>
          Start
        </Button>
      )}
      {campaign.status === "running" && (
        <Button variant="ghost" disabled={pending} onClick={() => pauseMutation.mutate()}>
          Pause
        </Button>
      )}
      {campaign.status === "paused" && (
        <Button variant="ghost" disabled={pending} onClick={() => resumeMutation.mutate()}>
          Resume
        </Button>
      )}
      {!terminal && (
        <Button variant="danger" disabled={pending} onClick={() => cancelMutation.mutate()}>
          Cancel
        </Button>
      )}
      {campaign.status === "draft" && campaign.steps.length === 0 && (
        <span className="text-[12px] text-fgMuted">Add at least one step before starting.</span>
      )}
    </div>
  );
}

function StepsSection({ campaign, workspaceId }: { campaign: Campaign; workspaceId: string }) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [delayDays, setDelayDays] = useState(0);
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");

  const nextStepNumber = campaign.steps.length + 1;

  const mutation = useMutation({
    mutationFn: () =>
      addCampaignStep(workspaceId, campaign.id, {
        step_number: nextStepNumber,
        delay_days: delayDays,
        subject,
        body,
      }),
    onSuccess: () => {
      setOpen(false);
      setSubject("");
      setBody("");
      setDelayDays(0);
      queryClient.invalidateQueries({ queryKey: ["campaign", workspaceId, campaign.id] });
    },
  });

  return (
    <SectionCard title="Sequence steps">
      {campaign.steps.length > 0 ? (
        <div className="flex flex-col divide-y divide-border">
          {campaign.steps.map((step) => (
            <div key={step.id} className="flex flex-col gap-1 py-3 first:pt-0">
              <div className="flex items-center justify-between">
                <span className="text-[13px] font-medium text-fg">
                  Step {step.step_number} — {step.delay_days === 0 ? "immediately" : `+${step.delay_days}d`}
                </span>
                {!step.active && <Pill tone="muted">inactive</Pill>}
              </div>
              <p className="text-[12.5px] text-fg">{step.subject}</p>
              <p className="line-clamp-2 whitespace-pre-wrap text-[12px] text-fgMuted">{step.body}</p>
            </div>
          ))}
        </div>
      ) : (
        <p className="text-[12.5px] text-fgMuted">No steps yet.</p>
      )}

      {open ? (
        <form
          className="flex flex-col gap-2.5 border-t border-border pt-3"
          onSubmit={(e) => {
            e.preventDefault();
            mutation.mutate();
          }}
        >
          <label className="flex flex-col gap-1.5 text-[12.5px] text-fgMuted">
            Delay (days after previous step)
            <input
              type="number"
              min={0}
              value={delayDays}
              onChange={(e) => setDelayDays(Number(e.target.value))}
              className={inputClass}
            />
          </label>
          <label className="flex flex-col gap-1.5 text-[12.5px] text-fgMuted">
            Subject
            <input
              required
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              placeholder="{{first_name}}, quick question"
              className={inputClass}
            />
          </label>
          <label className="flex flex-col gap-1.5 text-[12.5px] text-fgMuted">
            Body
            <textarea
              required
              rows={5}
              value={body}
              onChange={(e) => setBody(e.target.value)}
              placeholder={"Hi {{first_name}},\n\n…"}
              className={inputClass}
            />
          </label>
          <div className="flex gap-2">
            <Button type="submit" disabled={mutation.isPending}>
              {mutation.isPending ? <Spinner className="h-3.5 w-3.5" /> : `Add step ${nextStepNumber}`}
            </Button>
            <Button type="button" variant="ghost" onClick={() => setOpen(false)}>
              Cancel
            </Button>
          </div>
        </form>
      ) : (
        <Button variant="ghost" onClick={() => setOpen(true)}>
          Add step
        </Button>
      )}
    </SectionCard>
  );
}

function EnrollSection({ campaignId, workspaceId }: { campaignId: string; workspaceId: string }) {
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const leadsQuery = useQuery({
    queryKey: ["enroll-leads", workspaceId, query],
    queryFn: () => listLeads(workspaceId, { search: query || undefined, limit: 50 }),
  });

  const mutation = useMutation({
    mutationFn: () => enrollContacts(workspaceId, campaignId, Array.from(selected)),
    onSuccess: () => setSelected(new Set()),
  });

  function toggle(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  return (
    <SectionCard title="Enroll contacts">
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
          placeholder="Search leads to enroll…"
          className={`${inputClass} flex-1`}
        />
      </form>

      {leadsQuery.isLoading && <Spinner />}

      {leadsQuery.data && leadsQuery.data.length > 0 && (
        <div className="flex max-h-64 flex-col divide-y divide-border overflow-y-auto rounded-lg border border-border">
          {leadsQuery.data.map((lead) => (
            <label key={lead.id} className="flex items-center gap-3 px-3 py-2 hover:bg-surface2">
              <input
                type="checkbox"
                checked={selected.has(lead.id)}
                onChange={() => toggle(lead.id)}
                className="h-3.5 w-3.5 accent-accent"
              />
              <span className="flex-1 text-[13px] text-fg">{lead.full_name ?? lead.email ?? "Unnamed"}</span>
              <span className="text-[12px] text-fgMuted">{lead.email ?? "no email"}</span>
            </label>
          ))}
        </div>
      )}

      <div className="flex items-center gap-3">
        <Button disabled={selected.size === 0 || mutation.isPending} onClick={() => mutation.mutate()}>
          {mutation.isPending ? <Spinner className="h-3.5 w-3.5" /> : `Enroll ${selected.size || ""}`.trim()}
        </Button>
        {mutation.isSuccess && (
          <span className="text-[12.5px] text-fgMuted">
            {mutation.data.enrolled} enrolled, {mutation.data.already_enrolled} already enrolled,{" "}
            {mutation.data.not_found} not found
          </span>
        )}
      </div>
    </SectionCard>
  );
}

function PreviewSection({ campaign, workspaceId }: { campaign: Campaign; workspaceId: string }) {
  const [contactId, setContactId] = useState("");
  const [stepNumber, setStepNumber] = useState(campaign.steps[0]?.step_number ?? 1);
  const [search, setSearch] = useState("");

  const leadsQuery = useQuery({
    queryKey: ["preview-leads", workspaceId, search],
    queryFn: () => listLeads(workspaceId, { search: search || undefined, limit: 20 }),
  });

  const mutation = useMutation({
    mutationFn: () => previewCampaignStep(workspaceId, campaign.id, contactId, stepNumber),
  });

  if (campaign.steps.length === 0) return null;

  return (
    <SectionCard title="Preview">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <label className="flex flex-col gap-1.5 text-[12.5px] text-fgMuted">
          Step
          <select
            value={stepNumber}
            onChange={(e) => setStepNumber(Number(e.target.value))}
            className={inputClass}
          >
            {campaign.steps.map((s) => (
              <option key={s.id} value={s.step_number}>
                Step {s.step_number}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1.5 text-[12.5px] text-fgMuted">
          Contact
          <input
            list="preview-contacts"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              const match = leadsQuery.data?.find(
                (l) => (l.full_name ?? l.email ?? "") === e.target.value
              );
              setContactId(match?.id ?? "");
            }}
            placeholder="Search a contact…"
            className={inputClass}
          />
          <datalist id="preview-contacts">
            {leadsQuery.data?.map((l) => (
              <option key={l.id} value={l.full_name ?? l.email ?? l.id} />
            ))}
          </datalist>
        </label>
      </div>
      <Button
        variant="ghost"
        disabled={!contactId || mutation.isPending}
        onClick={() => mutation.mutate()}
      >
        {mutation.isPending ? <Spinner className="h-3.5 w-3.5" /> : "Render preview"}
      </Button>
      {mutation.data && (
        <div className="flex flex-col gap-2 rounded-lg border border-border p-3">
          <p className="text-[13px] font-medium text-fg">{mutation.data.subject}</p>
          <p className="whitespace-pre-wrap text-[12.5px] text-fgMuted">{mutation.data.body}</p>
          {mutation.data.unrecognized_variables.length > 0 && (
            <p className="text-[11.5px] text-warning">
              Unrecognized variables: {mutation.data.unrecognized_variables.join(", ")}
            </p>
          )}
        </div>
      )}
    </SectionCard>
  );
}

function formatPercent(value: number | null): string {
  return value === null ? "—" : `${Math.round(value * 1000) / 10}%`;
}

function PerformanceCard({
  title,
  subtitle,
  rate,
  breakdown,
}: {
  title: string;
  subtitle: string;
  rate: number | null;
  breakdown: [string, number][];
}) {
  return (
    <Card className="flex flex-col gap-3">
      <span className="text-[12.5px] font-medium text-fg">{title}</span>
      <span className="font-mono text-[32px] font-semibold leading-none tabular-nums text-fg">
        {formatPercent(rate)}
      </span>
      <div className="flex items-center gap-3 text-[12.5px] text-fgMuted">
        {breakdown.map(([label, value]) => (
          <span key={label}>
            {value} {label}
          </span>
        ))}
      </div>
      <p className="border-t border-border pt-2 text-[11.5px] text-fgMuted">{subtitle}</p>
    </Card>
  );
}

function ReportSection({ campaignId, workspaceId }: { campaignId: string; workspaceId: string }) {
  const reportQuery = useQuery({
    queryKey: ["campaign-report", workspaceId, campaignId],
    queryFn: () => getCampaignReport(workspaceId, campaignId),
  });

  const processMutation = useMutation({
    mutationFn: () => processCampaignNow(workspaceId, campaignId),
    onSuccess: () => reportQuery.refetch(),
  });

  if (!reportQuery.data) {
    return (
      <SectionCard title="Report">
        <Spinner />
      </SectionCard>
    );
  }

  const r = reportQuery.data;
  const stat = (label: string, value: React.ReactNode) => (
    <div className="flex flex-col gap-1">
      <span className="text-[11px] uppercase tracking-wide text-fgMuted">{label}</span>
      <span className="font-mono text-[18px] font-semibold tabular-nums text-fg">{value}</span>
    </div>
  );

  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <PerformanceCard
          title="Emails sent successfully"
          subtitle="Delivery performance"
          rate={r.delivery_rate}
          breakdown={[
            ["Delivered", r.delivered],
            ["Bounced", r.bounced],
          ]}
        />
        <PerformanceCard
          title="Open rate"
          subtitle="Inbox interactions"
          rate={r.open_rate}
          breakdown={[
            ["Opened", r.opened],
            ["Clicked", r.clicked],
          ]}
        />
        <PerformanceCard
          title="Reply activity"
          subtitle="Reply engagement — positive replies are AI-classified from actual reply text; unclassified replies (no text captured, or no AI provider enabled at the time) aren't counted as positive."
          rate={r.reply_rate}
          breakdown={[
            ["total replies", r.replied],
            ["positive replies", r.positive_replies],
          ]}
        />
      </div>

      <SectionCard title="Other stats">
        <div className="grid grid-cols-3 gap-4 sm:grid-cols-5">
          {stat("Enrolled", r.contacts_enrolled)}
          {stat("Sent", r.sent)}
          {stat("Unsubscribed", r.unsubscribed)}
          {stat("Meetings", r.meetings)}
          {stat("Won", r.won)}
        </div>
        <div className="flex items-center gap-2 border-t border-border pt-3">
          <Button variant="ghost" disabled={processMutation.isPending} onClick={() => processMutation.mutate()}>
            {processMutation.isPending ? <Spinner className="h-3.5 w-3.5" /> : "Process due sends now"}
          </Button>
          {processMutation.data && (
            <span className="text-[12px] text-fgMuted">
              {processMutation.data.sent} sent
              {processMutation.data.skipped_no_quota ? " — daily limit reached" : ""}
            </span>
          )}
        </div>
      </SectionCard>
    </div>
  );
}

function CampaignDetailContent({ campaignId }: { campaignId: string }) {
  const { activeWorkspace } = useWorkspace();
  const workspaceId = activeWorkspace?.id;

  const campaignQuery = useQuery({
    queryKey: ["campaign", workspaceId, campaignId],
    queryFn: () => getCampaign(workspaceId!, campaignId),
    enabled: !!workspaceId,
  });

  if (campaignQuery.isLoading) {
    return (
      <div className="flex items-center gap-2 text-[13px] text-fgMuted">
        <Spinner /> Loading campaign…
      </div>
    );
  }

  if (campaignQuery.isError || !campaignQuery.data || !workspaceId) {
    return <EmptyState title="Campaign not found" />;
  }

  const campaign = campaignQuery.data;

  return (
    <div className="flex flex-col gap-6">
      <div>
        <div className="mb-1 flex items-center gap-2 text-[12px] text-fgMuted">
          <Link href="/campaigns" className="hover:text-fg">
            Campaigns
          </Link>
          <span>/</span>
        </div>
        <h1 className="text-[22px] font-semibold tracking-tight">{campaign.name}</h1>
        <p className="mt-1 text-[13px] text-fgMuted">
          {campaign.from_name ? `${campaign.from_name} <${campaign.from_email}>` : campaign.from_email} ·{" "}
          {campaign.daily_limit}/day
        </p>
        <div className="mt-3">
          <LifecycleActions campaign={campaign} workspaceId={workspaceId} />
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <StepsSection campaign={campaign} workspaceId={workspaceId} />
        <EnrollSection campaignId={campaign.id} workspaceId={workspaceId} />
      </div>

      <PreviewSection campaign={campaign} workspaceId={workspaceId} />
      <ReportSection campaignId={campaign.id} workspaceId={workspaceId} />
    </div>
  );
}

export default function CampaignDetailPage() {
  const params = useParams<{ id: string }>();
  return (
    <AppShell title="Campaign">
      <CampaignDetailContent campaignId={params.id} />
    </AppShell>
  );
}
