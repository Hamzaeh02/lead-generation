"use client";

import { useMutation } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { registerAccount, storeSession } from "@/lib/api";
import { useWorkspace } from "@/lib/workspace-context";

const inputClass =
  "rounded-lg border border-border bg-surface px-3 py-2 text-[13.5px] text-fg placeholder:text-fgMuted focus:border-accent focus:outline-none";

export default function RegisterPage() {
  const router = useRouter();
  const { refreshAuth } = useWorkspace();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [workspaceName, setWorkspaceName] = useState("");

  const mutation = useMutation({
    mutationFn: registerAccount,
    onSuccess: (data) => {
      storeSession(data);
      // See login/page.tsx — WorkspaceProvider's localStorage check only
      // runs once on initial mount, so this must be triggered explicitly.
      refreshAuth();
      router.push("/dashboard");
    },
  });

  return (
    <main className="mx-auto flex min-h-screen max-w-sm flex-col justify-center gap-5 bg-bg px-6 text-fg">
      <h1 className="text-xl font-semibold tracking-tight">Create your workspace</h1>
      <form
        className="flex flex-col gap-3"
        onSubmit={(e) => {
          e.preventDefault();
          mutation.mutate({
            email,
            password,
            full_name: fullName || undefined,
            workspace_name: workspaceName,
          });
        }}
      >
        <input
          required
          placeholder="Workspace name"
          className={inputClass}
          value={workspaceName}
          onChange={(e) => setWorkspaceName(e.target.value)}
        />
        <input
          placeholder="Full name"
          className={inputClass}
          value={fullName}
          onChange={(e) => setFullName(e.target.value)}
        />
        <input
          type="email"
          required
          placeholder="Email"
          className={inputClass}
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <input
          type="password"
          required
          minLength={8}
          placeholder="Password"
          className={inputClass}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        <button
          type="submit"
          disabled={mutation.isPending}
          className="rounded-lg bg-accent px-4 py-2 text-[13.5px] font-medium text-white disabled:opacity-50"
        >
          {mutation.isPending ? "Creating…" : "Create workspace"}
        </button>
        {mutation.isError && (
          <p className="text-[12.5px] text-danger">
            Could not create account. Email may already be registered.
          </p>
        )}
      </form>
      <p className="text-[13px] text-fgMuted">
        Already have an account?{" "}
        <Link href="/login" className="text-accent hover:underline">
          Log in
        </Link>
      </p>
    </main>
  );
}
