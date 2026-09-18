"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { AppShell } from "@/components/AppShell";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { Pill } from "@/components/ui/Pill";
import { Spinner } from "@/components/ui/Spinner";
import { createCampaign, listCampaigns, type CampaignStatus } from "@/lib/api";
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

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint: string;
  children: React.ReactNode;
}) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className="text-[13px] font-medium text-fg">{label}</span>
      {children}
      <span className="text-[11.5px] text-fgMuted">{hint}</span>
    </label>
  );
}

function CreateCampaignForm({
  open,
  onOpen,
  onClose,
  onCreated,
}: {
  open: boolean;
  onOpen: () => void;
  onClose: () => void;
  onCreated: (id: string) => void;
}) {
  const { activeWorkspace } = useWorkspace();
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [fromName, setFromName] = useState("");
  const [fromEmail, setFromEmail] = useState("");
  const [dailyLimit, setDailyLimit] = useState(50);

  const mutation = useMutation({
    mutationFn: () =>
      createCampaign(activeWorkspace!.id, {
        name,
        from_name: fromName || undefined,
        from_email: fromEmail,
        daily_limit: dailyLimit,
      }),
    onSuccess: (campaign) => {
      queryClient.invalidateQueries({ queryKey: ["campaigns", activeWorkspace?.id] });
      onCreated(campaign.id);
    },
  });

  if (!open) {
    return <Button onClick={onOpen}>New campaign</Button>;
  }

  return (
    <Card className="flex flex-col gap-5">
      <div>
        <h2 className="text-[15px] font-semibold text-fg">Set up a new campaign</h2>
        <p className="mt-1 text-[12.5px] text-fgMuted">
          This just names the campaign and its sender identity. You&apos;ll write the actual emails and
          pick which contacts receive them on the next page, once this is created.
        </p>
      </div>
      <form
        className="grid grid-cols-1 gap-4 sm:grid-cols-2"
        onSubmit={(e) => {
          e.preventDefault();
          mutation.mutate();
        }}
      >
        <div className="sm:col-span-2">
          <Field label="Campaign name" hint="An internal label for you — contacts never see this.">
            <input
              required
              autoFocus
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Austin Dentists Q1"
              className={inputClass}
            />
          </Field>
        </div>
        <Field label="From email" hint="The address your contacts will see this arrive from.">
          <input
            required
            type="email"
            value={fromEmail}
            onChange={(e) => setFromEmail(e.target.value)}
            placeholder="you@yourcompany.com"
            className={inputClass}
          />
        </Field>
        <Field label="From name" hint="Optional — shown next to the from email, e.g. “Alex from Acme”.">
          <input
            value={fromName}
            onChange={(e) => setFromName(e.target.value)}
            placeholder="Your name"
            className={inputClass}
          />
        </Field>
        <Field
          label="Daily send limit"
          hint="Max emails sent per day, so you don't blast everyone at once and get flagged as spam."
        >
          <input
            type="number"
            min={1}
            value={dailyLimit}
            onChange={(e) => setDailyLimit(Number(e.target.value))}
            className={inputClass}
          />
        </Field>
        <div className="flex items-center gap-2 sm:col-span-2">
          <Button type="submit" disabled={mutation.isPending}>
            {mutation.isPending ? <Spinner className="h-3.5 w-3.5" /> : "Create campaign"}
          </Button>
          <Button type="button" variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          {mutation.isError && <p className="text-[12.5px] text-danger">Could not create campaign.</p>}
        </div>
      </form>
    </Card>
  );
}

function CampaignsContent() {
  const { activeWorkspace } = useWorkspace();
  const router = useRouter();
  const [formOpen, setFormOpen] = useState(false);

  const campaignsQuery = useQuery({
    queryKey: ["campaigns", activeWorkspace?.id],
    queryFn: () => listCampaigns(activeWorkspace!.id),
    enabled: !!activeWorkspace,
  });

  const campaigns = campaignsQuery.data ?? [];

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-[22px] font-semibold tracking-tight">Campaigns</h1>
          <p className="mt-1 text-[13px] text-fgMuted">
            Automated email sequences sent to your leads, with delivery/open/reply tracking.
          </p>
        </div>
        {!formOpen && <Button onClick={() => setFormOpen(true)}>New campaign</Button>}
      </div>

      {formOpen && (
        <CreateCampaignForm
          open
          onOpen={() => setFormOpen(true)}
          onClose={() => setFormOpen(false)}
          onCreated={(id) => router.push(`/campaigns/${id}`)}
        />
      )}

      {campaignsQuery.isLoading && (
        <div className="flex items-center gap-2 text-[13px] text-fgMuted">
          <Spinner /> Loading campaigns…
        </div>
      )}

      {campaignsQuery.isSuccess && campaigns.length === 0 && !formOpen && (
        <EmptyState
          title="No campaigns yet"
          description="A campaign is an email sequence you send to a list of your leads — write the emails, pick who gets them, and track opens/replies as they come in."
          action={<Button onClick={() => setFormOpen(true)}>Create your first campaign</Button>}
        />
      )}

      {campaigns.length > 0 && (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {campaigns.map((campaign) => (
            <Link key={campaign.id} href={`/campaigns/${campaign.id}`}>
              <Card className="flex h-full flex-col gap-3 hover:border-accent">
                <div className="flex items-start justify-between gap-2">
                  <span className="text-[14px] font-medium text-fg">{campaign.name}</span>
                  <Pill tone={statusTone[campaign.status]}>{campaign.status}</Pill>
                </div>
                <div className="flex flex-col gap-1 text-[12.5px] text-fgMuted">
                  <span>{campaign.from_email}</span>
                  <span>{campaign.steps.length} step{campaign.steps.length === 1 ? "" : "s"}</span>
                  <span>{campaign.daily_limit}/day limit</span>
                </div>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

export default function CampaignsPage() {
  return (
    <AppShell title="Campaigns">
      <CampaignsContent />
    </AppShell>
  );
}
