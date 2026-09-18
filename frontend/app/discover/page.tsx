"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useMemo, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Spinner } from "@/components/ui/Spinner";
import { executeSearch, listProviders, type ProviderCategory } from "@/lib/api";
import { BUSINESS_TYPES, COUNTRIES, RESULT_LIMITS, US_STATES } from "@/lib/discover-options";
import { useWorkspace } from "@/lib/workspace-context";

const categories: { value: ProviderCategory; label: string }[] = [
  { value: "company_discovery", label: "Companies" },
  { value: "person_discovery", label: "People" },
  { value: "local_business_discovery", label: "Local businesses" },
  { value: "website_discovery", label: "Websites" },
];

const inputClass =
  "rounded-lg border border-border bg-surface px-3 py-2 text-[13px] text-fg placeholder:text-fgMuted focus:border-accent focus:outline-none";

function DiscoverContent() {
  const { activeWorkspace } = useWorkspace();
  const workspaceId = activeWorkspace?.id;

  const [category, setCategory] = useState<ProviderCategory>("company_discovery");
  const [provider, setProvider] = useState("");
  const [businessType, setBusinessType] = useState("");
  const [customKeyword, setCustomKeyword] = useState("");
  const [city, setCity] = useState("");
  const [country, setCountry] = useState("United States");
  const [state, setState] = useState("");
  const [customState, setCustomState] = useState("");
  const [limit, setLimit] = useState(25);

  const industry = businessType || undefined;
  const keywords = businessType ? undefined : customKeyword || undefined;
  const resolvedState = country === "United States" ? state : customState;

  const providersQuery = useQuery({ queryKey: ["providers"], queryFn: listProviders });

  const availableProviders = useMemo(
    () => (providersQuery.data ?? []).filter((p) => p.enabled && p.category === category),
    [providersQuery.data, category]
  );

  const selectedProvider = provider || availableProviders[0]?.provider || "";

  const searchMutation = useMutation({
    mutationFn: () =>
      executeSearch({
        workspace_id: workspaceId!,
        provider: selectedProvider,
        category,
        criteria: {
          keywords,
          industry,
          city: city || undefined,
          state: resolvedState || undefined,
          country: country || undefined,
          limit,
        },
      }),
  });

  return (
    <div className="flex flex-col gap-8">
      <div>
        <h1 className="text-[22px] font-semibold tracking-tight">Discover</h1>
        <p className="mt-1 text-[13px] text-fgMuted">
          Run a real provider search — results are persisted as companies and contacts, never invented.
        </p>
      </div>

      <Card className="flex flex-col gap-4">
        <form
          className="flex flex-col gap-4"
          onSubmit={(e) => {
            e.preventDefault();
            if (selectedProvider && workspaceId) searchMutation.mutate();
          }}
        >
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <label className="flex flex-col gap-1.5 text-[12.5px] text-fgMuted">
              Category
              <select
                value={category}
                onChange={(e) => {
                  setCategory(e.target.value as ProviderCategory);
                  setProvider("");
                }}
                className={inputClass}
              >
                {categories.map((c) => (
                  <option key={c.value} value={c.value}>
                    {c.label}
                  </option>
                ))}
              </select>
            </label>

            <label className="flex flex-col gap-1.5 text-[12.5px] text-fgMuted">
              Provider
              <select
                value={selectedProvider}
                onChange={(e) => setProvider(e.target.value)}
                className={inputClass}
                disabled={availableProviders.length === 0}
              >
                {availableProviders.length === 0 ? (
                  <option value="">No enabled provider for this category</option>
                ) : (
                  availableProviders.map((p) => (
                    <option key={p.id} value={p.provider}>
                      {p.provider}
                    </option>
                  ))
                )}
              </select>
            </label>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <label className="flex flex-col gap-1.5 text-[12.5px] text-fgMuted">
              Business type
              <select
                value={businessType}
                onChange={(e) => setBusinessType(e.target.value)}
                className={inputClass}
              >
                {BUSINESS_TYPES.map((b) => (
                  <option key={b.value} value={b.value}>
                    {b.label}
                  </option>
                ))}
              </select>
            </label>

            {!businessType && (
              <label className="flex flex-col gap-1.5 text-[12.5px] text-fgMuted">
                Keyword
                <input
                  value={customKeyword}
                  onChange={(e) => setCustomKeyword(e.target.value)}
                  className={inputClass}
                  placeholder="e.g. dental clinic"
                />
              </label>
            )}

            <label className="flex flex-col gap-1.5 text-[12.5px] text-fgMuted">
              Country
              <select
                value={country}
                onChange={(e) => {
                  setCountry(e.target.value);
                  setState("");
                  setCustomState("");
                }}
                className={inputClass}
              >
                {COUNTRIES.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </label>

            <label className="flex flex-col gap-1.5 text-[12.5px] text-fgMuted">
              {country === "United States" ? "State" : "State / region"}
              {country === "United States" ? (
                <select value={state} onChange={(e) => setState(e.target.value)} className={inputClass}>
                  <option value="">Any state</option>
                  {US_STATES.map((s) => (
                    <option key={s} value={s}>
                      {s}
                    </option>
                  ))}
                </select>
              ) : (
                <input
                  value={customState}
                  onChange={(e) => setCustomState(e.target.value)}
                  className={inputClass}
                  placeholder="Optional"
                />
              )}
            </label>

            <label className="flex flex-col gap-1.5 text-[12.5px] text-fgMuted">
              City
              <input
                value={city}
                onChange={(e) => setCity(e.target.value)}
                className={inputClass}
                placeholder="e.g. Austin"
              />
            </label>

            <label className="flex flex-col gap-1.5 text-[12.5px] text-fgMuted">
              Result limit
              <select value={limit} onChange={(e) => setLimit(Number(e.target.value))} className={inputClass}>
                {RESULT_LIMITS.map((n) => (
                  <option key={n} value={n}>
                    {n} results
                  </option>
                ))}
              </select>
            </label>
          </div>

          <div>
            <Button type="submit" disabled={!selectedProvider || searchMutation.isPending}>
              {searchMutation.isPending ? <Spinner className="h-3.5 w-3.5" /> : "Run search"}
            </Button>
          </div>
        </form>

        {searchMutation.isError && (
          <p className="text-[12.5px] text-danger">
            {(searchMutation.error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
              "Search failed — the provider may be unavailable."}
          </p>
        )}
      </Card>

      {searchMutation.isSuccess && (
        <div className="flex flex-col gap-6">
          <div className="flex flex-wrap gap-4 text-[13px] text-fgMuted">
            <span>
              <strong className="font-mono text-fg">{searchMutation.data.companies_created}</strong> companies created
            </span>
            <span>
              <strong className="font-mono text-fg">{searchMutation.data.companies_matched}</strong> companies matched
            </span>
            <span>
              <strong className="font-mono text-fg">{searchMutation.data.contacts_created}</strong> contacts created
            </span>
            <span>
              <strong className="font-mono text-fg">{searchMutation.data.contacts_matched}</strong> contacts matched
            </span>
          </div>

          {searchMutation.data.companies.length > 0 && (
            <Card className="flex flex-col divide-y divide-border p-0">
              {searchMutation.data.companies.map((company) => (
                <Link
                  key={company.id}
                  href={`/companies/${company.id}`}
                  className="flex items-center justify-between px-4 py-3 hover:bg-surface2"
                >
                  <span className="text-[13px] font-medium text-fg">{company.name ?? "Unnamed company"}</span>
                  <span className="text-[12px] text-fgMuted">{company.domain ?? company.city ?? "—"}</span>
                </Link>
              ))}
            </Card>
          )}

          {searchMutation.data.contacts.length > 0 && (
            <Card className="flex flex-col divide-y divide-border p-0">
              {searchMutation.data.contacts.map((contact) => (
                <Link
                  key={contact.id}
                  href={`/leads/${contact.id}`}
                  className="flex items-center justify-between px-4 py-3 hover:bg-surface2"
                >
                  <span className="text-[13px] font-medium text-fg">
                    {contact.full_name ?? contact.email ?? "Unnamed contact"}
                  </span>
                  <span className="text-[12px] text-fgMuted">{contact.job_title ?? contact.email ?? "—"}</span>
                </Link>
              ))}
            </Card>
          )}

          {searchMutation.data.companies.length === 0 && searchMutation.data.contacts.length === 0 && (
            <p className="text-[13px] text-fgMuted">The provider ran successfully but found nothing for these criteria.</p>
          )}
        </div>
      )}
    </div>
  );
}

export default function DiscoverPage() {
  return (
    <AppShell title="Discover">
      <DiscoverContent />
    </AppShell>
  );
}
