"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo } from "react";
import { AppShell } from "@/components/AppShell";
import { Pill } from "@/components/ui/Pill";
import { Spinner } from "@/components/ui/Spinner";
import { Table, TableBody, TableHead, Td, Th, Tr } from "@/components/ui/Table";
import { getProviderHealth, listProviders, updateProviderConfig, type ProviderConfig, type ProviderHealth } from "@/lib/api";
import { useWorkspace } from "@/lib/workspace-context";

function formatDuration(ms: number): string {
  return ms < 1000 ? `${Math.round(ms)}ms` : `${(ms / 1000).toFixed(1)}s`;
}

function ProviderRow({
  config,
  health,
  canEdit,
}: {
  config: ProviderConfig;
  health: ProviderHealth | undefined;
  canEdit: boolean;
}) {
  const queryClient = useQueryClient();

  const toggleMutation = useMutation({
    mutationFn: (enabled: boolean) => updateProviderConfig(config.id, { enabled }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["providers"] }),
  });

  const quota = health?.monthly_free_quota ?? config.monthly_free_quota;
  const remaining = health?.quota_remaining;

  return (
    <Tr>
      <Td className="font-mono font-medium text-fg">{config.provider}</Td>
      <Td className="text-fgMuted">{config.category.replace(/_/g, " ")}</Td>
      <Td>
        {canEdit ? (
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={config.enabled}
              disabled={toggleMutation.isPending}
              onChange={(e) => toggleMutation.mutate(e.target.checked)}
              className="h-3.5 w-3.5 accent-accent"
            />
            <span className="text-[12px] text-fgMuted">{config.enabled ? "enabled" : "disabled"}</span>
          </label>
        ) : (
          <Pill tone={config.enabled ? "success" : "muted"}>{config.enabled ? "enabled" : "disabled"}</Pill>
        )}
      </Td>
      <Td className="font-mono tabular-nums text-fgMuted">{config.priority}</Td>
      <Td className="font-mono tabular-nums text-fgMuted">
        {quota === null || quota === undefined ? "—" : remaining !== undefined ? `${remaining}/${quota}` : `${quota}/mo`}
      </Td>
      <Td className="font-mono tabular-nums text-fgMuted">
        {health ? `${Math.round(health.success_rate * 100)}%` : "—"}
      </Td>
      <Td className="font-mono tabular-nums text-fgMuted">{health ? formatDuration(health.avg_duration_ms) : "—"}</Td>
      <Td className="text-fgMuted">
        {health?.last_success_at ? new Date(health.last_success_at).toLocaleDateString() : "never called"}
      </Td>
    </Tr>
  );
}

function ProvidersContent() {
  const { currentUser } = useWorkspace();

  const providersQuery = useQuery({ queryKey: ["providers"], queryFn: listProviders });
  const healthQuery = useQuery({ queryKey: ["providers-health"], queryFn: getProviderHealth });

  const healthByKey = useMemo(() => {
    const map = new Map<string, ProviderHealth>();
    for (const h of healthQuery.data ?? []) {
      map.set(`${h.provider}:${h.category}`, h);
    }
    return map;
  }, [healthQuery.data]);

  const providers = (providersQuery.data ?? []).filter((p) => p.enabled);
  const canEdit = !!currentUser?.is_superuser;

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-[22px] font-semibold tracking-tight">Providers</h1>
        <p className="mt-1 text-[13px] text-fgMuted">
          The provider registry — every source discovery, enrichment, and outreach can draw from.
          Showing enabled providers only.
          {!canEdit && " Only a workspace admin's superuser account can enable/disable providers."}
        </p>
      </div>

      {providersQuery.isLoading && (
        <div className="flex items-center gap-2 text-[13px] text-fgMuted">
          <Spinner /> Loading providers…
        </div>
      )}

      {providers.length > 0 && (
        <Table>
          <TableHead>
            <Th>Provider</Th>
            <Th>Category</Th>
            <Th>Status</Th>
            <Th>Priority</Th>
            <Th>Quota</Th>
            <Th>Success rate</Th>
            <Th>Avg latency</Th>
            <Th>Last success</Th>
          </TableHead>
          <TableBody>
            {providers.map((config) => (
              <ProviderRow
                key={config.id}
                config={config}
                health={healthByKey.get(`${config.provider}:${config.category}`)}
                canEdit={canEdit}
              />
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  );
}

export default function ProvidersPage() {
  return (
    <AppShell title="Providers">
      <ProvidersContent />
    </AppShell>
  );
}
