"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AppShell } from "@/components/AppShell";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { Pill } from "@/components/ui/Pill";
import { Spinner } from "@/components/ui/Spinner";
import { Table, TableBody, TableHead, Td, Th, Tr } from "@/components/ui/Table";
import { getAdminProviderPanel, listAllUsers, updateUserSuperuser, type User } from "@/lib/api";
import { useWorkspace } from "@/lib/workspace-context";

function UserRow({ user, currentUserId }: { user: User; currentUserId: string | undefined }) {
  const queryClient = useQueryClient();
  const mutation = useMutation({
    mutationFn: (isSuperuser: boolean) => updateUserSuperuser(user.id, isSuperuser),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin-users"] }),
  });

  const isSelf = user.id === currentUserId;

  return (
    <Tr>
      <Td className="font-medium text-fg">{user.full_name ?? "—"}</Td>
      <Td className="text-fgMuted">{user.email}</Td>
      <Td>
        <Pill tone={user.is_active ? "success" : "muted"}>{user.is_active ? "active" : "disabled"}</Pill>
      </Td>
      <Td>
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={user.is_superuser}
            disabled={mutation.isPending || (isSelf && user.is_superuser)}
            onChange={(e) => mutation.mutate(e.target.checked)}
            className="h-3.5 w-3.5 accent-accent"
          />
          <span className="text-[12px] text-fgMuted">
            {user.is_superuser ? "superuser" : "standard"}
            {isSelf && user.is_superuser && " (you)"}
          </span>
        </label>
      </Td>
    </Tr>
  );
}

function AdminContent() {
  const { currentUser } = useWorkspace();

  const usersQuery = useQuery({ queryKey: ["admin-users"], queryFn: listAllUsers });
  const providersQuery = useQuery({ queryKey: ["admin-providers"], queryFn: getAdminProviderPanel });

  return (
    <div className="flex flex-col gap-8">
      <div>
        <h1 className="text-[22px] font-semibold tracking-tight">Admin</h1>
        <p className="mt-1 text-[13px] text-fgMuted">Platform-wide — not scoped to a single workspace.</p>
      </div>

      <section className="flex flex-col gap-3">
        <h2 className="text-[13px] font-semibold text-fg">Users</h2>
        {usersQuery.isLoading && <Spinner />}
        {usersQuery.data && (
          <Table>
            <TableHead>
              <Th>Name</Th>
              <Th>Email</Th>
              <Th>Status</Th>
              <Th>Access</Th>
            </TableHead>
            <TableBody>
              {usersQuery.data.map((u) => (
                <UserRow key={u.id} user={u} currentUserId={currentUser?.id} />
              ))}
            </TableBody>
          </Table>
        )}
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="text-[13px] font-semibold text-fg">Provider panel</h2>
        <p className="text-[12.5px] text-fgMuted">
          Config and live health merged in one view. Toggle providers from{" "}
          <a href="/providers" className="text-accent hover:underline">
            Providers
          </a>
          .
        </p>
        {providersQuery.data && providersQuery.data.length > 0 ? (
          <Card className="flex flex-col divide-y divide-border p-0">
            {providersQuery.data.map((p) => (
              <div key={`${p.provider}:${p.category}`} className="flex items-center justify-between gap-3 px-4 py-3 text-[13px]">
                <span className="font-mono font-medium text-fg">{p.provider}</span>
                <span className="text-fgMuted">{p.category.replace(/_/g, " ")}</span>
                <span className="font-mono tabular-nums text-fgMuted">
                  {Math.round(p.success_rate * 100)}% success
                </span>
                <span className="font-mono tabular-nums text-fgMuted">
                  {p.quota_remaining !== null ? `${p.quota_remaining} left` : "—"}
                </span>
              </div>
            ))}
          </Card>
        ) : (
          <EmptyState title="No provider activity yet" />
        )}
      </section>
    </div>
  );
}

export default function AdminPage() {
  const { currentUser } = useWorkspace();

  return (
    <AppShell title="Admin">
      {currentUser && !currentUser.is_superuser ? (
        <EmptyState title="Admin access required" description="This area is restricted to platform superusers." />
      ) : (
        <AdminContent />
      )}
    </AppShell>
  );
}
