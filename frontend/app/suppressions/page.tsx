"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { AppShell } from "@/components/AppShell";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { Pill } from "@/components/ui/Pill";
import { Spinner } from "@/components/ui/Spinner";
import { Table, TableBody, TableHead, Td, Th, Tr } from "@/components/ui/Table";
import { createSuppression, listSuppressions, type SuppressionReason } from "@/lib/api";
import { useWorkspace } from "@/lib/workspace-context";

const reasonTone: Record<SuppressionReason, "success" | "warning" | "danger" | "accent" | "muted"> = {
  unsubscribe: "warning",
  bounce: "danger",
  complaint: "danger",
  reply_opt_out: "accent",
  manual: "muted",
};

function SuppressionsContent() {
  const { activeWorkspace } = useWorkspace();
  const queryClient = useQueryClient();
  const [email, setEmail] = useState("");

  const suppressionsQuery = useQuery({
    queryKey: ["suppressions", activeWorkspace?.id],
    queryFn: () => listSuppressions(activeWorkspace!.id),
    enabled: !!activeWorkspace,
  });

  const mutation = useMutation({
    mutationFn: () => createSuppression(activeWorkspace!.id, email),
    onSuccess: () => {
      setEmail("");
      queryClient.invalidateQueries({ queryKey: ["suppressions", activeWorkspace?.id] });
    },
  });

  const suppressions = suppressionsQuery.data ?? [];

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-[22px] font-semibold tracking-tight">Suppressions</h1>
        <p className="mt-1 text-[13px] text-fgMuted">
          The do-not-contact list — checked before every single send, no exceptions.
        </p>
      </div>

      <form
        className="flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          if (email.trim()) mutation.mutate();
        }}
      >
        <input
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="email@example.com"
          className="w-72 rounded-lg border border-border bg-surface px-3 py-2 text-[13px] text-fg placeholder:text-fgMuted focus:border-accent focus:outline-none"
        />
        <Button type="submit" disabled={mutation.isPending}>
          {mutation.isPending ? <Spinner className="h-3.5 w-3.5" /> : "Suppress"}
        </Button>
      </form>
      {mutation.isError && <p className="text-[12.5px] text-danger">Could not add suppression.</p>}

      {suppressionsQuery.isLoading && (
        <div className="flex items-center gap-2 text-[13px] text-fgMuted">
          <Spinner /> Loading…
        </div>
      )}

      {suppressionsQuery.isSuccess && suppressions.length === 0 && (
        <EmptyState title="No suppressions yet" description="Manually suppressed, unsubscribed, and bounced emails will appear here." />
      )}

      {suppressions.length > 0 && (
        <Table>
          <TableHead>
            <Th>Email</Th>
            <Th>Reason</Th>
            <Th>Added</Th>
          </TableHead>
          <TableBody>
            {suppressions.map((s) => (
              <Tr key={s.id}>
                <Td className="font-medium text-fg">{s.email}</Td>
                <Td>
                  <Pill tone={reasonTone[s.reason]}>{s.reason.replace(/_/g, " ")}</Pill>
                </Td>
                <Td className="text-fgMuted">{new Date(s.created_at).toLocaleDateString()}</Td>
              </Tr>
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  );
}

export default function SuppressionsPage() {
  return (
    <AppShell title="Suppressions">
      <SuppressionsContent />
    </AppShell>
  );
}
