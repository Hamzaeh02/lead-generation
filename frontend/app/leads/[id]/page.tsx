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
  createLeadNote,
  createLeadTask,
  findLeadEmail,
  getLatestLeadVerification,
  getLead,
  getLeadScore,
  listLeadNotes,
  listLeadPersonalizations,
  listLeadTasks,
  personalizeLead,
  updateLeadStatus,
  updateLeadTask,
  verifyLeadEmail,
  type LeadStatus,
} from "@/lib/api";
import { useWorkspace } from "@/lib/workspace-context";

const statusFlow: LeadStatus[] = [
  "new",
  "verified",
  "ready_for_outreach",
  "contacted",
  "opened",
  "clicked",
  "replied",
  "interested",
  "meeting",
  "won",
  "lost",
  "unsubscribed",
  "bounced",
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

const verificationTone: Record<string, "success" | "warning" | "danger" | "muted"> = {
  valid: "success",
  risky: "warning",
  invalid: "danger",
  unknown: "muted",
};

function SectionCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <Card className="flex flex-col gap-3">
      <h2 className="text-[13px] font-semibold text-fg">{title}</h2>
      {children}
    </Card>
  );
}

function LeadDetailContent({ contactId }: { contactId: string }) {
  const { activeWorkspace } = useWorkspace();
  const workspaceId = activeWorkspace?.id;
  const queryClient = useQueryClient();
  const [noteText, setNoteText] = useState("");
  const [taskTitle, setTaskTitle] = useState("");

  const leadQuery = useQuery({
    queryKey: ["lead", workspaceId, contactId],
    queryFn: () => getLead(workspaceId!, contactId),
    enabled: !!workspaceId,
  });

  const leadScoreQuery = useQuery({
    queryKey: ["lead-score", workspaceId, contactId],
    queryFn: () => getLeadScore(workspaceId!, contactId),
    enabled: !!workspaceId,
  });

  const verificationQuery = useQuery({
    queryKey: ["lead-verification", workspaceId, contactId],
    queryFn: () => getLatestLeadVerification(workspaceId!, contactId),
    enabled: !!workspaceId,
  });

  const notesQuery = useQuery({
    queryKey: ["lead-notes", workspaceId, contactId],
    queryFn: () => listLeadNotes(workspaceId!, contactId),
    enabled: !!workspaceId,
  });

  const tasksQuery = useQuery({
    queryKey: ["lead-tasks", workspaceId, contactId],
    queryFn: () => listLeadTasks(workspaceId!, contactId),
    enabled: !!workspaceId,
  });

  const personalizationsQuery = useQuery({
    queryKey: ["lead-personalizations", workspaceId, contactId],
    queryFn: () => listLeadPersonalizations(workspaceId!, contactId),
    enabled: !!workspaceId,
  });

  const statusMutation = useMutation({
    mutationFn: (status: LeadStatus) => updateLeadStatus(workspaceId!, contactId, status),
    onSuccess: (contact) => queryClient.setQueryData(["lead", workspaceId, contactId], contact),
  });

  const findEmailMutation = useMutation({
    mutationFn: () => findLeadEmail(workspaceId!, contactId),
    onSuccess: (result) => queryClient.setQueryData(["lead", workspaceId, contactId], result.contact),
  });

  const verifyMutation = useMutation({
    mutationFn: () => verifyLeadEmail(workspaceId!, contactId),
    onSuccess: (verification) => {
      queryClient.setQueryData(["lead-verification", workspaceId, contactId], verification);
      queryClient.invalidateQueries({ queryKey: ["lead", workspaceId, contactId] });
    },
  });

  const personalizeMutation = useMutation({
    mutationFn: () => personalizeLead(workspaceId!, contactId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["lead-personalizations", workspaceId, contactId] }),
  });

  const noteMutation = useMutation({
    mutationFn: (text: string) => createLeadNote(workspaceId!, contactId, text),
    onSuccess: () => {
      setNoteText("");
      queryClient.invalidateQueries({ queryKey: ["lead-notes", workspaceId, contactId] });
    },
  });

  const taskMutation = useMutation({
    mutationFn: (title: string) => createLeadTask(workspaceId!, contactId, { title }),
    onSuccess: () => {
      setTaskTitle("");
      queryClient.invalidateQueries({ queryKey: ["lead-tasks", workspaceId, contactId] });
    },
  });

  const toggleTaskMutation = useMutation({
    mutationFn: ({ taskId, completed }: { taskId: string; completed: boolean }) =>
      updateLeadTask(workspaceId!, contactId, taskId, { completed }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["lead-tasks", workspaceId, contactId] }),
  });

  if (leadQuery.isLoading) {
    return (
      <div className="flex items-center gap-2 text-[13px] text-fgMuted">
        <Spinner /> Loading lead…
      </div>
    );
  }

  if (leadQuery.isError || !leadQuery.data) {
    return <EmptyState title="Lead not found" description="It may have been removed, or you may not have access." />;
  }

  const lead = leadQuery.data;
  const verification = verificationQuery.data;

  return (
    <div className="flex flex-col gap-8">
      <div>
        <div className="mb-1 flex items-center gap-2 text-[12px] text-fgMuted">
          <Link href="/leads" className="hover:text-fg">
            Leads
          </Link>
          <span>/</span>
        </div>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-[22px] font-semibold tracking-tight">
              {lead.full_name ?? lead.email ?? "Unnamed contact"}
            </h1>
            <p className="mt-1 text-[13px] text-fgMuted">
              {lead.job_title ?? "—"}
              {lead.company_id && (
                <>
                  {" at "}
                  <Link href={`/companies/${lead.company_id}`} className="text-accent hover:underline">
                    {lead.company_name ?? "company"}
                  </Link>
                </>
              )}
            </p>
          </div>
          <select
            value={lead.status}
            onChange={(e) => statusMutation.mutate(e.target.value as LeadStatus)}
            disabled={statusMutation.isPending}
            className="rounded-lg border border-border bg-surface px-2.5 py-1.5 text-[13px] font-medium text-fg focus:border-accent focus:outline-none disabled:opacity-50"
          >
            {statusFlow.map((s) => (
              <option key={s} value={s}>
                {s.replace(/_/g, " ")}
              </option>
            ))}
          </select>
        </div>
      </div>

      <Card className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-4">
          <div>
            <h2 className="text-[13px] font-semibold text-fg">Lead score</h2>
            <p className="text-[12px] text-fgMuted">Fit + intent + authority + reachability + engagement</p>
          </div>
          {leadScoreQuery.data ? (
            <div className="font-mono text-[28px] font-semibold tabular-nums text-fg">
              {leadScoreQuery.data.score}
              <span className="text-[13px] font-normal text-fgMuted">/100</span>
            </div>
          ) : (
            <Spinner />
          )}
        </div>
        <div className="flex flex-col items-start gap-2 sm:items-end">
          {leadScoreQuery.data && leadScoreQuery.data.breakdown.length > 0 && (
            <p className="max-w-sm text-[11.5px] text-fgMuted sm:text-right">
              {leadScoreQuery.data.breakdown.join(" · ")}
            </p>
          )}
        </div>
      </Card>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <SectionCard title="Contact info">
          <div className="flex flex-col gap-2 text-[13px]">
            <div className="flex items-center justify-between">
              <span className="text-fgMuted">Email</span>
              <span className="text-fg">{lead.email ?? "—"}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-fgMuted">Phone</span>
              <span className="text-fg">{lead.phone ?? "—"}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-fgMuted">LinkedIn</span>
              {lead.linkedin_url ? (
                <a href={lead.linkedin_url} target="_blank" rel="noreferrer" className="text-accent hover:underline">
                  View profile
                </a>
              ) : (
                <span className="text-fg">—</span>
              )}
            </div>
          </div>
          <div className="flex flex-wrap gap-2 border-t border-border pt-3">
            <Button
              variant="ghost"
              onClick={() => findEmailMutation.mutate()}
              disabled={findEmailMutation.isPending || !!lead.email}
            >
              {findEmailMutation.isPending ? <Spinner className="h-3.5 w-3.5" /> : "Find email"}
            </Button>
            <Button
              variant="ghost"
              onClick={() => verifyMutation.mutate()}
              disabled={verifyMutation.isPending || !lead.email}
            >
              {verifyMutation.isPending ? <Spinner className="h-3.5 w-3.5" /> : "Verify email"}
            </Button>
          </div>
          {findEmailMutation.isSuccess && !findEmailMutation.data.email_found && (
            <p className="text-[12px] text-fgMuted">No email found by any enabled provider.</p>
          )}
          {verification && (
            <div className="flex items-center justify-between border-t border-border pt-3 text-[12.5px]">
              <Pill tone={verificationTone[verification.verification_status] ?? "muted"}>
                {verification.verification_status}
              </Pill>
              <span className="text-fgMuted">via {verification.provider}</span>
            </div>
          )}
        </SectionCard>

        <SectionCard title="AI personalization">
          <p className="text-[12.5px] text-fgMuted">
            Generates a grounded outreach draft from this contact&apos;s real data — never a fabricated fact.
          </p>
          <Button onClick={() => personalizeMutation.mutate()} disabled={personalizeMutation.isPending}>
            {personalizeMutation.isPending ? <Spinner className="h-3.5 w-3.5" /> : "Generate draft"}
          </Button>
          {personalizeMutation.isError && (
            <p className="text-[12.5px] text-danger">
              {(personalizeMutation.error as { response?: { data?: { detail?: string } } })?.response?.data
                ?.detail ?? "Draft generation failed."}
            </p>
          )}
          {personalizationsQuery.data && personalizationsQuery.data.length > 0 && (
            <div className="flex flex-col gap-3 border-t border-border pt-3">
              {personalizationsQuery.data.slice(0, 1).map((gen) => (
                <div key={gen.id} className="flex flex-col gap-1.5 text-[12.5px]">
                  {gen.subject && <p className="font-medium text-fg">{gen.subject}</p>}
                  {gen.body && <p className="whitespace-pre-wrap text-fgMuted">{gen.body}</p>}
                  <span className="text-[11px] text-fgMuted">
                    source: {gen.personalization_source ?? "generic"}
                  </span>
                </div>
              ))}
            </div>
          )}
        </SectionCard>
      </div>

      <section className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="flex flex-col gap-3">
          <h2 className="text-[13px] font-semibold text-fg">Notes</h2>
          <form
            className="flex gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              if (noteText.trim()) noteMutation.mutate(noteText.trim());
            }}
          >
            <input
              value={noteText}
              onChange={(e) => setNoteText(e.target.value)}
              placeholder="Add a note…"
              className="flex-1 rounded-lg border border-border bg-surface px-2.5 py-1.5 text-[12.5px] text-fg placeholder:text-fgMuted focus:border-accent focus:outline-none"
            />
            <Button type="submit" variant="ghost" disabled={noteMutation.isPending}>
              Add
            </Button>
          </form>
          {notesQuery.data && notesQuery.data.length > 0 ? (
            <Card className="flex flex-col divide-y divide-border p-0">
              {notesQuery.data.map((note) => (
                <div key={note.id} className="flex flex-col gap-1 px-4 py-3">
                  <p className="text-[13px] text-fg">{note.text}</p>
                  <span className="text-[11px] text-fgMuted">
                    {new Date(note.created_at).toLocaleString()}
                  </span>
                </div>
              ))}
            </Card>
          ) : (
            <EmptyState title="No notes yet" />
          )}
        </div>

        <div className="flex flex-col gap-3">
          <h2 className="text-[13px] font-semibold text-fg">Tasks</h2>
          <form
            className="flex gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              if (taskTitle.trim()) taskMutation.mutate(taskTitle.trim());
            }}
          >
            <input
              value={taskTitle}
              onChange={(e) => setTaskTitle(e.target.value)}
              placeholder="Add a task…"
              className="flex-1 rounded-lg border border-border bg-surface px-2.5 py-1.5 text-[12.5px] text-fg placeholder:text-fgMuted focus:border-accent focus:outline-none"
            />
            <Button type="submit" variant="ghost" disabled={taskMutation.isPending}>
              Add
            </Button>
          </form>
          {tasksQuery.data && tasksQuery.data.length > 0 ? (
            <Card className="flex flex-col divide-y divide-border p-0">
              {tasksQuery.data.map((task) => (
                <label key={task.id} className="flex items-center gap-3 px-4 py-3">
                  <input
                    type="checkbox"
                    checked={task.completed}
                    onChange={(e) =>
                      toggleTaskMutation.mutate({ taskId: task.id, completed: e.target.checked })
                    }
                    className="h-3.5 w-3.5 accent-accent"
                  />
                  <span className={`text-[13px] ${task.completed ? "text-fgMuted line-through" : "text-fg"}`}>
                    {task.title}
                  </span>
                </label>
              ))}
            </Card>
          ) : (
            <EmptyState title="No tasks yet" />
          )}
        </div>
      </section>
    </div>
  );
}

export default function LeadDetailPage() {
  const params = useParams<{ id: string }>();
  return (
    <AppShell title="Lead">
      <LeadDetailContent contactId={params.id} />
    </AppShell>
  );
}
