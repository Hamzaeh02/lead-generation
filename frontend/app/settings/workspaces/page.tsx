"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { AppShell } from "@/components/AppShell";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Pill } from "@/components/ui/Pill";
import { Spinner } from "@/components/ui/Spinner";
import { createWorkspace } from "@/lib/api";
import { useWorkspace } from "@/lib/workspace-context";

function WorkspacesContent() {
  const { workspaces, activeWorkspace, setActiveWorkspaceId } = useWorkspace();
  const queryClient = useQueryClient();
  const router = useRouter();
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");

  const createMutation = useMutation({
    mutationFn: () => createWorkspace(name),
    onSuccess: async (workspace) => {
      setName("");
      setCreating(false);
      await queryClient.invalidateQueries({ queryKey: ["workspaces"] });
      setActiveWorkspaceId(workspace.id);
      router.push("/dashboard");
    },
  });

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-[22px] font-semibold tracking-tight">Workspaces</h1>
          <p className="mt-1 text-[13px] text-fgMuted">
            Agency mode — operate several isolated client workspaces from one account.
          </p>
        </div>
        {!creating && <Button onClick={() => setCreating(true)}>New workspace</Button>}
      </div>

      {creating && (
        <Card className="flex flex-col gap-3">
          <form
            className="flex gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              if (name.trim()) createMutation.mutate();
            }}
          >
            <input
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Client or company name"
              className="flex-1 rounded-lg border border-border bg-surface px-3 py-2 text-[13px] text-fg placeholder:text-fgMuted focus:border-accent focus:outline-none"
            />
            <Button type="submit" disabled={createMutation.isPending}>
              {createMutation.isPending ? <Spinner className="h-3.5 w-3.5" /> : "Create"}
            </Button>
            <Button type="button" variant="ghost" onClick={() => setCreating(false)}>
              Cancel
            </Button>
          </form>
          <p className="text-[12px] text-fgMuted">You become this workspace&apos;s owner.</p>
        </Card>
      )}

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {workspaces.map((ws) => (
          <Card key={ws.id} className="flex flex-col gap-3">
            <div className="flex items-start justify-between gap-2">
              <div>
                <div className="text-[14px] font-medium text-fg">{ws.name}</div>
                <div className="text-[12px] text-fgMuted">{ws.slug}</div>
              </div>
              {ws.id === activeWorkspace?.id && <Pill tone="accent">active</Pill>}
            </div>
            <div className="flex items-center justify-between">
              <Pill tone="muted">{ws.plan}</Pill>
              {ws.id !== activeWorkspace?.id && (
                <Button variant="ghost" onClick={() => setActiveWorkspaceId(ws.id)}>
                  Switch
                </Button>
              )}
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}

export default function WorkspacesPage() {
  return (
    <AppShell title="Workspaces">
      <WorkspacesContent />
    </AppShell>
  );
}
