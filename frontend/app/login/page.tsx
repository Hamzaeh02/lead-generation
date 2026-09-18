"use client";

import { useMutation } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { login, storeSession } from "@/lib/api";
import { useWorkspace } from "@/lib/workspace-context";

const inputClass =
  "rounded-lg border border-border bg-surface px-3 py-2 text-[13.5px] text-fg placeholder:text-fgMuted focus:border-accent focus:outline-none";

export default function LoginPage() {
  const router = useRouter();
  const { refreshAuth } = useWorkspace();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const mutation = useMutation({
    mutationFn: login,
    onSuccess: (data) => {
      storeSession(data);
      // WorkspaceProvider only checks localStorage for a token once, on
      // initial app mount — without this, authStatus would stay
      // "unauthenticated" after a client-side navigation and AppShell
      // would immediately bounce back to /login.
      refreshAuth();
      router.push("/dashboard");
    },
  });

  return (
    <main className="mx-auto flex min-h-screen max-w-sm flex-col justify-center gap-5 bg-bg px-6 text-fg">
      <h1 className="text-xl font-semibold tracking-tight">Log in</h1>
      <form
        className="flex flex-col gap-3"
        onSubmit={(e) => {
          e.preventDefault();
          mutation.mutate({ email, password });
        }}
      >
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
          {mutation.isPending ? "Logging in…" : "Log in"}
        </button>
        {mutation.isError && (
          <p className="text-[12.5px] text-danger">Invalid email or password.</p>
        )}
      </form>
      <p className="text-[13px] text-fgMuted">
        No account?{" "}
        <Link href="/register" className="text-accent hover:underline">
          Create one
        </Link>
      </p>
    </main>
  );
}
