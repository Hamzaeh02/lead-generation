# Lead Intelligence Platform — Phase 1 + 2 + 3 + 4 + 5 + 6 + 7 + 8 + 9 + 10 + 11 + 12 + Free-Tier Plan

Production-grade B2B lead intelligence, enrichment, verification, intent
detection, and outreach platform, built incrementally.

- **Phase 1**: project scaffolding, authentication, workspaces
  (multi-tenancy foundation), health checks.
- **Phase 2**: canonical company/contact models, provider interfaces (the
  abstract contracts every future integration implements), a provider
  registry, per-field provenance, normalization, entity resolution/dedup,
  and CSV import/export.
- **Phase 3**: the first three real provider integrations — Apollo
  (company + person search), People Data Labs (company + person search,
  company + person enrichment), and SerpApi (Google Maps local-business
  search) — plus `POST /api/v1/search/execute`, which calls one explicitly
  chosen provider and runs its results through the Phase 2
  normalize → dedup → persist pipeline.
- **Phase 4**: Apify — not one fixed integration, but an `ActorConfig`
  registry (`POST/PATCH/GET /api/v1/apify/actors`, superuser-gated writes)
  so any actor can be registered per discovery category. `ApifyClient`
  implements the full run→poll→retrieve cycle against Apify's stable,
  well-documented REST API, and `normalize_dataset` does best-effort
  generic field-alias mapping since actor output schemas vary per-actor.
  Wired into `POST /api/v1/search/execute` alongside Apollo/PDL/SerpApi.

- **Phase 5**: Hunter — email discovery (`POST /api/v1/leads/{id}/find-email`)
  and verification (`POST /api/v1/leads/{id}/verify`,
  `GET /api/v1/leads/{id}/verification`), backed by an `EmailDiscoveryService`/
  `EmailVerificationService` pair that pick the highest-priority enabled
  provider from the registry. Verification results are stored as an
  append-only history (`email_verifications` table) so re-verification over
  time is auditable, not overwritten.

- **Phase 6**: cost tracking (`provider_usage` table — every provider call
  logged with duration, success/failure, error), provider health
  (`GET /api/v1/providers/health`, aggregated from that log), and waterfall
  fallback for email discovery/verification — `EmailDiscoveryService`/
  `EmailVerificationService` now try every enabled provider in priority
  order, falling through on failure, rather than stopping at the first one.
- **Phase 7**: PhantomBuster (`SocialSignalProvider`) — `PhantomBusterClient`
  reuses the launch→poll→fetch pattern from Apify against PhantomBuster's
  REST API, driving one pre-configured "Phantom" (agent) the user sets up
  in their own account (`PHANTOMBUSTER_AGENT_ID`) — never anything that
  bypasses LinkedIn/platform auth or rate limits. Exposed via
  `POST /api/v1/social/discover-profile` and `/discover-posts`. Output
  field mapping is generic/best-effort (same caveat as Apify actors —
  no fixed schema across differently-configured Phantoms).
- **Phase 8**: intent signal storage + scoring. `IntentSignal` rows require
  a real `source_url` — no path to create one without it. `IntentScore`
  (`app/services/intent_score_service.py`) sums per-signal-type weights
  (service request=30, funding=20, hiring=15, ... down to a generic-other
  fallback of 2) with linear time-decay between the spec's anchor points
  (100% at ≤2 days, 70% at 14, 30% at 30, 0% at 45+), capped at 100.
  `POST/GET /api/v1/companies/{id}/intent-signals` and
  `GET .../intent-score` — no new external provider this phase, since none
  is named in the spec for it; existing providers (PhantomBuster, etc.)
  are the future signal sources once wired up.

- **Phase 9**: ICP engine + natural-language ICP + lead scoring.
  `ICPProfile` (workspace-scoped, saved criteria) + `ICPScoreService`
  (`app/services/icp_score_service.py`) score a company 0-100 against it —
  industry (30), location (25, partial credit per matching field),
  company size (20), decision-maker contact (15), keywords (10), all
  configurable per-profile. `POST /api/v1/icp-profiles/parse` turns free
  text into suggested criteria — **honestly rule-based (regex/keyword
  matching), not AI**, since no OpenAI integration exists yet (that's
  Phase 10); building a fake "AI interpretation" without a real model
  would be worse than admitting the limitation. Per spec, it's never
  auto-executed or auto-saved — the caller reviews/edits, then explicitly
  POSTs to save or to `/search/execute` to run it. (`/icp-profiles/parse`'s
  heuristic limitation is now fixed by Phase 10's real AI provider — see
  below, though the endpoint itself is unchanged for now and still
  rule-based; a future pass could swap it to use `OpenAIProvider`.)
- **Phase 10**: AI personalization. `OpenAIProvider`
  (`app/providers/ai/openai_provider.py`) — OpenAI's Chat Completions API,
  `response_format: json_object` for structured output; one of the most
  stable/documented APIs used in this codebase, no live-account caveat
  needed. `PersonalizationService` builds `source_fields` from *only* the
  contact's/company's/latest-intent-signal's actual non-null data — never
  a placeholder — and instructs the model never to invent awards,
  customers, revenue, funding, or partnerships. That instruction can't
  *guarantee* an LLM won't hallucinate; nothing in code can. What the
  codebase controls is what facts ever reach the prompt, and
  `source_fields_used` on every stored `AIGeneration` is the audit trail
  of exactly that. `POST /api/v1/leads/{id}/personalize` (waterfall across
  enabled `ai` providers, same pattern as Phase 6) +
  `GET .../personalizations` (history). When a company has a recent intent
  signal, its `signal_text`/`source_url` are included as grounding and the
  generation is tagged `personalization_source: "intent_signal"` — a UI
  can then show *why* the message says what it says (section 38).
- **Phase 11**: campaigns, sending, scheduling, suppression, unsubscribe,
  bounce/reply handling — the biggest phase yet. `Campaign` +
  `CampaignStep` (multi-step sequences with per-step delay) +
  `CampaignRecipient` (tracks each contact's progress through the
  sequence) + `EmailEvent` (immutable log: sent/opened/clicked/replied/
  bounced/unsubscribed/complained) + `Suppression` (workspace-level
  do-not-contact list, checked before every single send with no
  exceptions). `SMTPEmailSenderProvider` (stdlib `smtplib`, wrapped in
  `asyncio.to_thread`) implements the generic fallback sender; a
  dev-only `MockEmailSenderProvider` never touches the network. Template
  rendering (`app/services/template_service.py`) only ever substitutes a
  fixed, known variable set (`{{first_name}}`, `{{company_name}}`,
  `{{intent_signal}}`, `{{unsubscribe_url}}`, ...) with real data or an
  empty string — never a fabricated value — and leaves unrecognized
  `{{...}}` untouched so a typo is visible, not silently dropped.
  Unsubscribe (`GET /unsubscribe/{token}`, mounted at the root path per
  spec) uses a signed, stateless JWT (same signing infra as auth tokens,
  no expiration) rather than a new mechanism. `CampaignSendingService`
  is the single send path used by both the manual
  `POST /campaigns/{id}/process` endpoint and the Celery beat task
  (`app/tasks/campaign_tasks.py`, every 5 minutes) — no duplicated
  sending logic between "test it now" and "runs in production."
  **Not implemented**: real ESP webhook adapters (SES/SendGrid/Postmark/
  Mailgun each have their own payload shape — `/webhooks/email-events`
  accepts an already-normalized shape, not any real provider's raw
  payload) and IMAP-based reply detection (the spec's stated fallback
  path) — both flagged in §14, not silently skipped.
- **Phase 12**: CRM, analytics, client reporting. `Contact.status`
  (`LeadStatus`: new → verified → ready_for_outreach → contacted →
  opened/clicked/replied → interested → meeting → won/lost, plus
  unsubscribed/bounced) is the durable CRM pipeline stage — distinct from
  `CampaignRecipient.status`, which tracks per-enrollment progress. It
  advances automatically at three points already built in earlier phases
  (a valid verification bumps New→Verified, a successful send bumps
  New/Verified/Ready-for-outreach→Contacted, a bounce/open/click/reply/
  unsubscribe webhook mirrors onto the contact) — and never *downgrades* a
  further-along status. `GET /api/v1/leads` now supports `status`, `tag_id`,
  and free-text `search` (name/email/company) filters plus `sort_by`/
  `sort_dir`; `PATCH /leads/bulk-status` and `POST /leads/bulk-tag` handle
  bulk operations; `Note`/`Task` give per-contact CRM notes and to-dos.
  `GET /api/v1/analytics/overview` (`app/services/analytics_service.py`)
  computes every dashboard number from real rows — verified-email count
  from each contact's *latest* verification (not just any), high-intent
  leads from actual `IntentScore` computation, provider cost from the
  `provider_usage` log — and leaves two numbers honestly `null` rather
  than guessed: `positive_reply_rate` (no reply-sentiment classification
  exists) and `high_icp_leads` (only computed if you pass a specific
  `icp_profile_id`; otherwise there's no single "the" ICP to score
  against). `GET /campaigns/{id}/report` gives a client-ready per-campaign
  report from real `EmailEvent`/`CampaignRecipient` data — provider cost
  is deliberately excluded there since cost tracking is workspace-level,
  not campaign-attributed, in this data model.
- **Phase 13**: multi-tenancy/agency mode and an admin panel. Workspace
  RBAC (`require_workspace_editor`/`_admin`/`_owner`) is enforced on
  campaign lifecycle actions, suppression creation, and workspace-member
  mutations — applied to the highest-value write endpoints first, not
  exhaustively across the whole codebase (§14). `POST /api/v1/workspaces`
  gives one user several isolated client workspaces (agency mode);
  `Workspace.plan`/`Workspace.limits` are a label plus an operator-set
  JSON blob with no billing behind them, only `max_team_members` actually
  enforced. `/api/v1/admin/users/{id}/superuser` closes a real gap from
  earlier phases (there was no way to promote a superuser except a direct
  database write); `/api/v1/admin/providers` is a consolidated,
  superuser-only merge of provider config and live health in one call.
- **Phase 14**: security/monitoring/production hardening. Server-side JWT
  revocation via a Redis denylist keyed by `jti`
  (`app/services/token_revocation.py`) closes the previous "logout is
  client-side only" gap — checked on every authenticated request and on
  refresh. Redis-backed fixed-window rate limiting
  (`app/services/rate_limiter.py`) protects `/auth/register`/`/login`/
  `/refresh` against brute force, keyed by IP not account. Both are
  injected as FastAPI dependencies (`get_token_revocation_store`/
  `get_rate_limiter`) the same way `get_db_session` is — tests override
  them with in-memory fakes (see `tests/conftest.py`), never a real Redis
  connection. `SecurityHeadersMiddleware` adds standard hardening headers
  to every response; `GZipMiddleware` compresses responses; `GET /metrics`
  exposes Prometheus counters/histograms tagged by route *template* (not
  raw path, to avoid per-ID label cardinality blowup).
- **Phase 15**: deployment tooling. `.github/workflows/ci.yml` runs
  backend tests, frontend type-checking, and a Docker build of both
  images. `infra/docker-compose.prod.yml` is a Compose overlay adding
  restart policies, `ENVIRONMENT=production`, and closing off direct host
  access to Postgres/Redis/backend/frontend (only nginx stays published).
  Neither TLS termination nor a secrets manager is provided — both are
  explicitly the deploying operator's responsibility, not faked here (see
  §17).

Nothing in this codebase fabricates data; every Company/Contact traces
back to at least one source record (`company_sources` / `contact_sources`),
and every field can be traced to the provider that supplied it via
`field_provenance`.

**Important caveat on Phases 3–4**: this environment has no network access
and no real API keys, so the Apollo and PDL integrations were built from
each provider's documented API conventions (endpoint paths, auth header,
response shape) rather than verified against a live account — see
[§14](#14-known-limitations--honesty-notes-phases-3-13) before trusting
their field mappings with real data. SerpApi's Google Maps response
shape, Apify's run/dataset REST API, Hunter's finder/verifier endpoints,
and OpenAI's Chat Completions API are all stable and well-documented, and
I'm confident in those four. All seven discovery/enrichment/AI providers
are tested with `httpx.MockTransport` fixtures, never real network calls.
Apify's and PhantomBuster's per-actor/per-Phantom output normalization is
inherently best-effort (see §14) since there is no fixed schema across
differently configured actors/agents — that's a design property, not a
bug to eventually fix.

## 1. Architecture overview

```
Browser ──▶ Next.js (frontend) ──▶ FastAPI (backend) ──▶ PostgreSQL
                                          │
                                          ├──▶ Redis (broker + cache)
                                          └──▶ Celery worker / beat
```

- **Backend**: FastAPI + SQLAlchemy 2.x (async) + Alembic + Celery, following
  a layered architecture: `api` (routes) → `services` (business logic) →
  `repositories` (data access) → `models` (SQLAlchemy ORM).
- **Frontend**: Next.js (App Router) + TypeScript + Tailwind CSS +
  TanStack Query. Talks to the backend only via `lib/api.ts`.
- **Auth**: JWT access + refresh tokens, bcrypt password hashing.
- **Multi-tenancy**: every user belongs to one or more `workspaces` via
  `workspace_members` with a role (`owner` / `admin` / `member` / `viewer`).
  Companies and contacts carry a `workspace_id` and every list/get/import/
  export endpoint requires active membership in that workspace
  (`require_workspace_member` in `app/api/deps.py`) — cross-workspace access
  is rejected outright, never partially scoped.
- **Provider architecture**: the core app never talks to a concrete
  provider directly. Each provider category (`app/providers/<category>/base.py`)
  defines an abstract interface — `CompanyDiscoveryProvider`,
  `PersonDiscoveryProvider`, `EnrichmentProvider`, `EmailFinderProvider`,
  `EmailVerifierProvider`, `SocialSignalProvider`, `IntentProvider`,
  `AIProvider`, `EmailSenderProvider`, `WebsiteDiscoveryProvider`,
  `LocalBusinessDiscoveryProvider`. All of them return
  `NormalizedCompany`/`NormalizedContact` dataclasses carrying a
  `ProviderMetadata` provenance stamp; every field is optional and
  providers never invent a value. The `provider_configs` table is the
  registry (enable/disable, priority) — see `GET/PATCH /api/v1/providers`.
- **Real providers (Phase 3)**: `ApolloCompanyDiscoveryProvider` +
  `ApolloPersonDiscoveryProvider` (`APOLLO_API_KEY`),
  `PeopleDataLabsCompanyDiscoveryProvider` +
  `PeopleDataLabsPersonDiscoveryProvider` + `PeopleDataLabsEnrichmentProvider`
  (`PDL_API_KEY`), and `SerpApiLocalBusinessProvider` (`SERPAPI_API_KEY`).
  Every outbound call goes through `app/providers/http.py`, which retries
  transient failures (timeouts, 429/5xx) with backoff, never retries 4xx
  auth errors, and converts any failure into `ProviderUnavailableError`.
  `app/services/provider_factory.py` is the only place that maps a
  `(provider name, category)` pair to a concrete class — it returns `None`
  when the required env var isn't set, which the search endpoint turns into
  a 503 naming the missing variable. Apollo's `email_not_unlocked@...`
  placeholder (returned when a search result's email isn't paid-unlocked)
  is explicitly filtered to `None` rather than stored as a real email.
- **Apify (Phase 4)**: unlike the other three, Apify isn't one fixed
  integration — `ActorConfig` (`actor_configs` table) registers any number
  of actors, each scoped to a `ProviderCategory` (currently
  `company_discovery` or `local_business_discovery`), with priority and an
  `input_schema` of defaults merged into each run. `ApifyClient`
  (`app/providers/lead_sources/apify_provider.py`) implements
  `run_actor()` → `poll_actor()` → `retrieve_dataset()` against Apify's
  REST API (`Authorization: Bearer`, `/v2/acts/{id}/runs`,
  `/v2/actor-runs/{id}`, `/v2/datasets/{id}/items`); polling has a bounded
  attempt count and raises `ProviderUnavailableError` on a non-`SUCCEEDED`
  terminal status or a timeout. `normalize_dataset()` maps common field
  aliases (`title`/`name`/`companyName` → name, `website`/`url`/`domain` →
  website, ...) since there's no fixed schema across actors — this is
  explicitly best-effort, not a guarantee, and worth checking against a
  real run's output before trusting it for a newly-registered actor. Actor
  management (`POST`/`PATCH /api/v1/apify/actors`) is superuser-gated, same
  as the provider registry.
- **Hunter (Phase 5)**: `HunterEmailFinderProvider` and
  `HunterEmailVerifierProvider` (`HUNTER_API_KEY`) implement email
  discovery and verification respectively.
  `EmailDiscoveryService`/`EmailVerificationService`
  (`app/services/email_*.py`) each pick the highest-priority enabled
  provider from the registry — a single choice today, but the registry
  ordering means adding a second email-finder/verifier later needs no
  endpoint changes. Hunter's finder result is stored as
  `EmailConfidence.FOUND` (a specific claimed address), never `CANDIDATE`
  (a raw pattern guess) and never "verified" — verification is always a
  separate, explicit call. Verification results accumulate as
  `EmailVerification` rows (append-only history, not overwritten) with the
  full evidence Hunter returns (`mx_records`, `smtp_check`, `accept_all`,
  `disposable`, `free_provider`, `role_account`, `raw_response`).
  `find_email` skips calling the provider entirely if the contact already
  has an email — never spends a provider call redundantly.
- **Gotcha worth knowing**: `Company`/`Contact` rows have
  `onupdate=func.now()` timestamp columns. After `session.commit()`,
  SQLAlchemy expires those columns in the in-memory object (their true
  value now only exists server-side); reading them during synchronous
  Pydantic serialization then crashes with `MissingGreenlet`. This bit
  `EmailDiscoveryService` and the "matched" branch of `SearchService`
  during Phase 5 development — both now call `session.refresh(obj)` after
  commit, before returning a mutated object for API serialization. Any new
  endpoint that mutates-then-returns an ORM object needs the same refresh.
- **Cost tracking & provider health (Phase 6)**: `ProviderUsageRecorder`
  (`app/services/provider_usage_tracker.py`) is an async context manager
  that wraps a provider call and logs one `ProviderUsage` row — provider,
  category, operation, workspace, duration, success/failure, error,
  records returned. It wraps every real provider call in the codebase
  (search execute for all 4 discovery providers, Hunter find/verify).
  `GET /api/v1/providers/usage` returns the raw log (filterable by
  provider/category); `GET /api/v1/providers/health` aggregates it into
  per-`(provider, category)` success rate, average latency, and
  last-success/last-failure timestamps — computed on read from the log,
  not a separately-maintained mutable table, so there's nothing to drift
  out of sync.
- **Second gotcha, caught by the health/usage tests**: a `try/except`
  meant to catch-and-continue in a waterfall loop must wrap the `async
  with ProviderUsageRecorder(...)` block, not sit inside it — catching the
  exception *inside* the block means `__aexit__` never sees it, so a
  failed call gets logged as a success. This shipped briefly during Phase
  6 development and was caught by
  `test_find_email_falls_back_to_second_provider_after_first_fails`
  asserting on the actual usage-log contents, not just the HTTP response.
  Both `EmailDiscoveryService` and `EmailVerificationService` now
  structure it correctly, with a comment at each site explaining why.
- **Email discovery/verification waterfall (Phase 6)**:
  `EmailDiscoveryService.find_email` and `EmailVerificationService.verify`
  iterate every enabled provider for their category in registry priority
  order (not just the top one). A provider that errors or is skipped for
  missing credentials doesn't fail the request — the next one is tried.
  Two outcomes are distinguished: if *every* enabled provider is missing
  credentials, nothing was actually attempted, so that's a 503 config
  error; if at least one provider was tried and all failed, that's a 502;
  if providers were tried and genuinely found/verified nothing, that's a
  normal 200 with no result — never conflated with each other. Full
  cross-category named waterfall strategies (section 51's "B2B: Apollo →
  PDL → Hunter → verification" style chains) and multi-provider
  verification-confidence blending (section 27) are still not built —
  both need more real providers in a category to be meaningfully
  testable, not just Hunter alone.
- **RBAC & agency mode (Phase 13)**: `WorkspaceRole` (owner/admin/member/
  viewer) existed since Phase 1 but was unenforced beyond plain membership.
  `require_workspace_role(*roles)` (`app/api/deps.py`) is a dependency
  factory built on top of `require_workspace_member`; three instances cover
  the common cases — `require_workspace_editor` (owner/admin/member, i.e.
  "not a read-only viewer"), `require_workspace_admin` (owner/admin), and
  `require_workspace_owner` (owner only). Applied to the highest-value
  write endpoints first, not exhaustively — see §14. `POST /api/v1/workspaces`
  lets one user create/own several isolated client workspaces (agency
  mode, section 77): the creator becomes that workspace's owner.
  `Workspace.plan`/`Workspace.limits` (section 78) are a label plus an
  operator-set JSON blob — no pricing or billing integration exists behind
  them; the only limit actually enforced today is
  `limits.max_team_members` on `POST /workspaces/{id}/members`. Adding a
  member (`require_workspace_admin`-gated) looks up an *existing*
  registered user by email — it is not an invite-token/signup-via-link
  flow. Demoting or removing a workspace's only remaining owner is
  rejected (400), so a workspace can never end up ownerless.
- **Admin panel (Phase 13)**: `GET/PATCH /api/v1/admin/users/{id}/superuser`
  promotes/demotes platform-admin access — previously the only way to set
  `is_superuser` was a direct `UPDATE` in the database. A superuser can't
  remove their own superuser access (avoids an admin locking themselves
  out with no other admin to undo it). `GET /api/v1/admin/providers` is a
  read-only, superuser-gated view that merges each `provider_configs` row
  with its live health summary in one response — everything `/providers`,
  `/providers/health`, and `/providers/usage` expose separately, combined
  for an admin dashboard. Platform-admin (`is_superuser`) is deliberately
  separate from workspace-scoped RBAC roles — one governs `/admin/*` and
  the provider registry, the other governs a single workspace's data.
- **Normalization & dedup**: `app/services/normalization.py` cleans values
  (lowercasing emails, stripping legal suffixes from company names,
  stripping tracking params from URLs, best-effort phone formatting) before
  `CompanyEntityResolver`/`PersonEntityResolver` (`app/services/*_resolver.py`)
  decide whether an incoming record matches an existing one. Matching uses
  only strong signals — exact domain, exact phone, or exact
  normalized-name+city/state for companies; exact email or exact LinkedIn
  URL for contacts — deliberately never fuzzy name-only matching, so two
  different businesses/people are never silently merged. A matched field is
  only ever filled if currently null; an existing value is never
  overwritten by a later source.

## 2. Directory structure

```
/backend
    /app
        /api            # route handlers (auth, health, workspaces, companies, leads, providers, search)
        /core            # config, database session, security (JWT/hashing)
        /models          # SQLAlchemy ORM models (User, Workspace, Company, Contact, ProviderConfig, ...)
        /schemas         # Pydantic request/response models
        /services        # business logic: AuthService, normalization, entity resolvers,
                          #   CSV import/export, provider_factory, search_service
        /repositories    # data access layer
        /providers        # interfaces (base.py per category), dev-only mock providers,
                          #   and real integrations: apollo_provider.py, pdl_provider.py,
                          #   serpapi_provider.py, http.py (shared retry/error handling)
        /workers          # Celery app
        /tasks            # Celery tasks
        /middleware       # request-context/logging middleware
        /utils            # logging, slugify, etc.
        main.py
    /tests
    alembic.ini
    /alembic
    requirements.txt
    Dockerfile
/frontend
    /app                 # Next.js App Router pages
    /lib                 # API client
    package.json
    Dockerfile
/infra
    docker-compose.yml
    nginx.conf
.env.example
```

## 3. Prerequisites

- Python 3.12+ (tested with 3.13)
- Node.js 20+
- Docker + Docker Compose (for the full stack)
- PostgreSQL 16 and Redis 7 (only if running services outside Docker)

## 4. Environment variables

Copy the example file and fill in a real `SECRET_KEY` (and, in later
phases, provider API keys). Never commit `.env`.

```bash
cp .env.example .env
python3 -c "import secrets; print(secrets.token_urlsafe(64))"   # paste into SECRET_KEY
```

All provider API keys are declared in `.env.example`. `APOLLO_API_KEY`,
`PDL_API_KEY`, `SERPAPI_API_KEY` (Phase 3), `APIFY_API_TOKEN` (Phase 4),
and `HUNTER_API_KEY` (Phase 5) are all usable now; `OPENAI_API_KEY` etc.
are for later phases — leave those blank. A provider with no key
configured is simply unavailable (the relevant endpoint returns a 503
naming the missing variable), never a startup failure.

## 5. Running with Docker Compose (recommended)

```bash
cp .env.example .env   # edit SECRET_KEY at minimum
cd infra
docker-compose up --build
```

This starts: `postgres`, `redis`, `backend` (runs `alembic upgrade head`
before serving), `celery_worker`, `celery_beat`, `frontend`, and an `nginx`
reverse proxy.

- Frontend: http://localhost:3000 (direct) or http://localhost (via nginx)
- Backend API docs: http://localhost:8000/docs
- Health check: http://localhost:8000/health
- Readiness check (DB + Redis): http://localhost:8000/ready

## 6. Running locally without Docker

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# requires Postgres + Redis running locally, matching DATABASE_URL/REDIS_URL in .env
alembic upgrade head
uvicorn app.main:app --reload
```

### Celery worker (optional, for background jobs added in later phases)

```bash
cd backend
source .venv/bin/activate
celery -A app.workers.celery_app worker --loglevel=info
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Set `NEXT_PUBLIC_API_BASE_URL` in `frontend/.env.local` if the backend isn't
on `http://localhost:8000`.

## 7. Database migrations (Alembic)

```bash
cd backend
source .venv/bin/activate

alembic upgrade head                       # apply migrations
alembic revision --autogenerate -m "..."   # create a new migration after model changes
alembic downgrade -1                       # roll back one migration
```

## 8. Running tests

Backend tests use an in-memory SQLite database via a fixture override — no
Postgres/Redis needed to run them.

```bash
cd backend
source .venv/bin/activate
python -m pytest tests/ -v
```

Expected: **241 passed** (includes Phase 14's 10 tests: logout revokes the
access token immediately (a subsequent `/auth/me` 401s) and the refresh
token too if it's sent along, a refresh token *not* sent to logout still
works, logout itself requires authentication; a tiny-limit fake rate
limiter proves a 429 actually fires after the threshold and that limits
are scoped per-endpoint (tripping `/login`'s limit doesn't block
`/register`) — every other test uses an always-allow fake so the other
231 tests never spuriously 429 from shared-IP test traffic; security
headers present on every response and HSTS specifically absent outside
`ENVIRONMENT=production`; and `/metrics` returning real Prometheus-format
output. Phase 13's 16 tests: additional-workspace
creation makes the creator its owner, plan/limits update requires the
owner role, adding a member requires an existing registered user (404
otherwise) and enforces `limits.max_team_members` (400 once hit), the
add/update-role/remove member lifecycle plus the "can't demote or remove
the workspace's only owner" guard, a viewer being blocked (403) from
adding members/creating campaigns/creating suppressions while still able
to read, a member role being allowed to create a suppression, superuser-
only access to `/admin/users` and `/admin/providers` (403 for everyone
else), superuser promote/demote of another user, a superuser being unable
to remove their own superuser access, and the admin provider panel
correctly merging a provider's config (quota) with its health summary;
Phase 12's 21 tests: CRM status
updates/bulk-status/notes/tasks/tags/bulk-tag, lead-list text-search and
status/tag filters, the three automatic status transitions and — just as
important — that a further-along status is never downgraded by one, the
analytics dashboard's real-data counts including "only the *latest*
verification counts, not just any", and a per-campaign report computed
from actual EmailEvent rows; Phase 9's 24 tests: ICP scoring
weights/decay/partial-location-credit/custom-weight-overrides, the NL
parser's regex extraction across industry/state/employee-range/titles, and
the ICP-profile + company-icp-score API endpoints; Phase 10's 11 tests:
OpenAI request/response mapping, grounding-fields-only construction,
intent-signal-sourced vs generic personalization, missing-credentials 503
vs all-providers-failed 502; and Phase 11's 24 tests: template rendering
never fabricates a missing value, SMTP send success/failure/missing-creds,
unsubscribe token round-trip and a real unsubscribe blocking a subsequent
send, suppression blocking sends, daily-limit enforcement across two
`/process` runs, multi-step sequencing with per-step delay, preview
rendering, and a bounce webhook creating a suppression) — health checks; register/login/refresh/me; workspace
listing; normalization edge cases; company/contact entity resolution
(dedup, field-fill, provenance); the mock-provider pipeline end-to-end;
CSV import/preview/export (including re-import producing zero duplicates,
and a malformed-email row being rejected rather than stored); the provider
registry (list, and superuser-only enable/priority updates); Apollo/PDL/
SerpApi/Apify/Hunter field-mapping and error-handling against
`httpx.MockTransport` fixtures (no real network calls, including Apify's
full run→poll→dataset cycle, a failed-run status, and poll timeout); the
Apify actor-config CRUD API (superuser-gated writes); `POST
/api/v1/search/execute` end-to-end for all four discovery providers
(disabled-provider rejection, missing-credentials 503, missing-actor-config
400, workspace-membership enforcement, provider runs that persist
companies through the resolver pipeline, and — a real bug caught during
Phase 5 development — a *matched* company surviving serialization after
mutation-then-commit); `find-email`/`verify` end-to-end (skips the
provider call when an email already exists, requires a company domain,
missing-credentials 503, persists an append-only verification history);
and Phase 6's waterfall/cost-tracking (falling back to a second provider
after the first fails — including a real usage-logging bug this test
caught, see §1 — provider-health aggregation, and a 502 vs 503
distinction between "all providers attempted and failed" and "no provider
had credentials to even try"); and Phase 7's PhantomBuster provider
(launch→poll→fetch cycle, error/timeout handling, profile/post field
mapping) plus the `/social/discover-profile` and `/discover-posts`
endpoints (disabled-provider 400, missing-credentials 503, workspace
membership, 404 on no match); Phase 8's decay-curve unit tests and
intent-signal/score API tests (source_url required, score decay/cap,
404/403/401 enforcement); and 9 tests for the OpenStreetMap provider
(known-tag mapping, free-text fallback, no-credentials-required
construction) and free-quota tracking (`calls_this_month`/
`quota_remaining` on `GET /providers/health`) — see §13.

Frontend type-check:

```bash
cd frontend
npm install
npm run typecheck
```

## 9. API endpoints implemented so far

| Method | Path                            | Auth required        | Description                                  |
|--------|----------------------------------|-----------------------|-----------------------------------------------|
| GET    | `/health`                        | No                    | Liveness probe                                |
| GET    | `/ready`                         | No                    | Readiness probe (DB + Redis)                  |
| GET    | `/metrics`                       | No                    | Prometheus scrape endpoint (restrict at the network level in prod) |
| POST   | `/api/v1/auth/register`          | No (rate-limited: 5/min/IP) | Create user + owner workspace            |
| POST   | `/api/v1/auth/login`             | No (rate-limited: 10/min/IP) | Email/password login                    |
| POST   | `/api/v1/auth/refresh`           | No (rate-limited: 30/min/IP) | Exchange refresh token for access; 401s if the refresh token was revoked |
| POST   | `/api/v1/auth/logout`            | Yes                   | Server-side revocation of the access token (and refresh token, if sent in the body) via Redis denylist |
| GET    | `/api/v1/auth/me`                | Yes                   | Current user                                  |
| GET    | `/api/v1/workspaces`             | Yes                   | Workspaces the user belongs to                |
| POST   | `/api/v1/workspaces`             | Yes                   | Create an additional workspace (agency mode); creator becomes owner |
| PATCH  | `/api/v1/workspaces/{id}`        | Yes + workspace owner  | Update a workspace's plan/limits              |
| GET    | `/api/v1/workspaces/{id}/members`| Yes + workspace member | List a workspace's members                    |
| POST   | `/api/v1/workspaces/{id}/members`| Yes + workspace admin  | Add an existing registered user by email      |
| PATCH  | `/api/v1/workspaces/{id}/members/{member_id}` | Yes + workspace owner | Change a member's role (can't demote the only owner) |
| DELETE | `/api/v1/workspaces/{id}/members/{member_id}` | Yes + workspace admin | Remove a member (can't remove the only owner) |
| GET    | `/api/v1/admin/users`            | Yes + superuser        | List all platform users                       |
| PATCH  | `/api/v1/admin/users/{id}/superuser` | Yes + superuser    | Promote/demote platform-admin access          |
| GET    | `/api/v1/admin/providers`        | Yes + superuser        | Consolidated provider config + health panel   |
| GET    | `/api/v1/companies`              | Yes + workspace member | List companies in a workspace                 |
| GET    | `/api/v1/companies/{id}`         | Yes + workspace member | Company detail                                |
| GET    | `/api/v1/leads`                  | Yes + workspace member | List contacts in a workspace                  |
| GET    | `/api/v1/leads/{id}`             | Yes + workspace member | Contact detail                                |
| GET    | `/api/v1/leads/export`           | Yes + workspace member | Download contacts as CSV                      |
| POST   | `/api/v1/leads/import/preview`   | Yes + workspace member | Parse a CSV, suggest column mapping           |
| POST   | `/api/v1/leads/import`           | Yes + workspace member | Import a CSV with an explicit column mapping  |
| GET    | `/api/v1/providers`              | Yes                   | List the provider registry                    |
| PATCH  | `/api/v1/providers/{id}`         | Yes + superuser        | Enable/disable a provider, set priority       |
| POST   | `/api/v1/search/execute`         | Yes + workspace member | Run one explicit provider's discovery search, persist results |
| GET    | `/api/v1/apify/actors`           | Yes                   | List the Apify actor registry                 |
| POST   | `/api/v1/apify/actors`           | Yes + superuser        | Register a new Apify actor for a category     |
| PATCH  | `/api/v1/apify/actors/{id}`      | Yes + superuser        | Enable/disable an actor, set priority/input   |
| POST   | `/api/v1/leads/{id}/find-email`  | Yes + workspace member | Find the contact's email (waterfall across enabled email-finder providers) |
| POST   | `/api/v1/leads/{id}/verify`      | Yes + workspace member | Verify the contact's current email (waterfall), store the result |
| GET    | `/api/v1/leads/{id}/verification`| Yes + workspace member | Latest stored verification for a contact      |
| GET    | `/api/v1/providers/usage`        | Yes                   | Raw provider call log (filter by provider/category) |
| GET    | `/api/v1/providers/health`       | Yes                   | Aggregated success rate/latency per provider+category |
| POST   | `/api/v1/social/discover-profile`| Yes + workspace member | Find a LinkedIn profile via PhantomBuster     |
| POST   | `/api/v1/social/discover-posts`  | Yes + workspace member | Find LinkedIn posts matching keywords         |
| POST   | `/api/v1/companies/{id}/intent-signals` | Yes + workspace member | Record an intent signal (requires source_url) |
| GET    | `/api/v1/companies/{id}/intent-signals` | Yes + workspace member | List a company's intent signals        |
| GET    | `/api/v1/companies/{id}/intent-score`   | Yes + workspace member | Compute decayed intent score (0-100)   |
| POST   | `/api/v1/icp-profiles/parse`     | Yes                   | Rule-based text -> suggested ICP criteria (review before saving) |
| POST   | `/api/v1/icp-profiles`           | Yes + workspace member | Save an ICP profile                           |
| GET    | `/api/v1/icp-profiles`           | Yes + workspace member | List ICP profiles                             |
| GET    | `/api/v1/icp-profiles/{id}`      | Yes + workspace member | ICP profile detail                            |
| PATCH  | `/api/v1/icp-profiles/{id}`      | Yes + workspace member | Update an ICP profile                         |
| GET    | `/api/v1/companies/{id}/icp-score` | Yes + workspace member | Score a company against an ICP profile (0-100) |
| POST   | `/api/v1/leads/{id}/personalize` | Yes + workspace member | AI-generate a grounded outreach draft (subject/body/CTA) |
| GET    | `/api/v1/leads/{id}/personalizations` | Yes + workspace member | List past AI generations for a contact |
| POST   | `/api/v1/campaigns`              | Yes + workspace editor | Create a campaign                             |
| GET    | `/api/v1/campaigns`              | Yes + workspace member | List campaigns                                |
| GET    | `/api/v1/campaigns/{id}`         | Yes + workspace member | Campaign detail (with steps)                  |
| POST   | `/api/v1/campaigns/{id}/steps`   | Yes + workspace editor | Add a sequence step                           |
| POST   | `/api/v1/campaigns/{id}/enroll`  | Yes + workspace editor | Enroll contacts                               |
| POST   | `/api/v1/campaigns/{id}/start`   | Yes + workspace editor | draft/scheduled/paused -> running (requires ≥1 step) |
| POST   | `/api/v1/campaigns/{id}/pause`   | Yes + workspace editor | running -> paused                             |
| POST   | `/api/v1/campaigns/{id}/resume`  | Yes + workspace editor | paused -> running                             |
| POST   | `/api/v1/campaigns/{id}/cancel`  | Yes + workspace editor | -> cancelled                                  |
| POST   | `/api/v1/campaigns/{id}/process` | Yes + workspace editor | Process one batch of due sends now (same path Celery beat uses) |
| POST   | `/api/v1/campaigns/{id}/preview` | Yes + workspace member | Render a step for one contact without sending |
| GET    | `/api/v1/suppressions`           | Yes + workspace member | List the do-not-contact list                  |
| POST   | `/api/v1/suppressions`           | Yes + workspace editor | Manually suppress an email                    |
| POST   | `/api/v1/webhooks/email-events`  | No                    | Ingest a normalized bounce/reply/unsubscribe/open/click event |
| GET    | `/unsubscribe/{token}`           | No (root path, not `/api/v1`) | Unsubscribe via signed token, creates a Suppression |
| PATCH  | `/api/v1/leads/{id}/status`      | Yes + workspace member | Update a lead's CRM status                    |
| PATCH  | `/api/v1/leads/bulk-status`      | Yes + workspace member | Bulk-update CRM status                        |
| POST   | `/api/v1/leads/bulk-tag`         | Yes + workspace member | Bulk-tag leads                                |
| POST   | `/api/v1/leads/{id}/notes`       | Yes + workspace member | Add a note                                    |
| GET    | `/api/v1/leads/{id}/notes`       | Yes + workspace member | List notes                                    |
| POST   | `/api/v1/leads/{id}/tasks`       | Yes + workspace member | Add a task                                    |
| GET    | `/api/v1/leads/{id}/tasks`       | Yes + workspace member | List tasks                                    |
| PATCH  | `/api/v1/leads/{id}/tasks/{task_id}` | Yes + workspace member | Update/complete a task                    |
| GET    | `/api/v1/tags`                   | Yes + workspace member | List tags                                     |
| POST   | `/api/v1/tags`                   | Yes + workspace member | Create a tag                                  |
| GET    | `/api/v1/analytics/overview`     | Yes + workspace member | Workspace dashboard (real DB-computed stats)  |
| GET    | `/api/v1/campaigns/{id}/report`  | Yes + workspace member | Client-ready per-campaign report              |

"Workspace member" endpoints take `workspace_id` as a query parameter (a
body field for `/search/execute`) and 403 if the authenticated user isn't
a member of that workspace. "Workspace editor"/"workspace admin"/"workspace
owner" additionally 403 if the member's role isn't one of `owner`/`admin`/
`member` (editor), `owner`/`admin` (admin), or `owner` (owner) respectively
— see `require_workspace_role` in §1. RBAC gating is applied to the
highest-value write endpoints, not exhaustively to every write endpoint in
the codebase; see §14.

## 10. CSV import walkthrough

```bash
TOKEN=...       # access_token from /api/v1/auth/register or /login
WORKSPACE_ID=...  # from GET /api/v1/workspaces

# 1. Preview: see detected headers and a suggested column mapping
curl -s -X POST "http://localhost:8000/api/v1/leads/import/preview?workspace_id=$WORKSPACE_ID" \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@leads.csv"

# 2. Import: confirm/edit the mapping, then execute
curl -s -X POST "http://localhost:8000/api/v1/leads/import?workspace_id=$WORKSPACE_ID" \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@leads.csv" \
  -F 'mapping_json={"company":"Company Name","website":"Website","email":"Email","first_name":"First Name","last_name":"Last Name","job_title":"Job Title","city":"City","state":"State"}'

# 3. Export back out
curl -s "http://localhost:8000/api/v1/leads/export?workspace_id=$WORKSPACE_ID" \
  -H "Authorization: Bearer $TOKEN" -o export.csv
```

Importing the same file twice does not create duplicate companies or
contacts — matching rows are attached as an additional `CompanySource`/
`ContactSource` on the existing record instead (see `companies_matched`/
`contacts_matched` in the response).

## 11. Provider search walkthrough (Phase 3)

Using a real provider takes two steps: an admin enables it in the registry,
then any workspace member can run a search against it.

```bash
# 0. One-time setup: add a real key to .env, e.g. SERPAPI_API_KEY=..., restart the backend.

# 1. Admin enables the provider for a category (requires is_superuser=true on your user —
#    there's no API to grant that yet; set it directly in the database for now: see the
#    troubleshooting note below)
curl -s -X GET "http://localhost:8000/api/v1/providers" -H "Authorization: Bearer $TOKEN"
# find the row for provider=serpapi, category=local_business_discovery, note its "id"
curl -s -X PATCH "http://localhost:8000/api/v1/providers/$PROVIDER_CONFIG_ID" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"enabled": true}'

# 2. Run a search — this calls SerpApi, normalizes results, dedups against
#    existing companies, and persists them with full provenance
curl -s -X POST "http://localhost:8000/api/v1/search/execute" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{
    "workspace_id": "'"$WORKSPACE_ID"'",
    "provider": "serpapi",
    "category": "local_business_discovery",
    "criteria": {"industry": "dental clinics", "city": "Miami", "state": "FL", "limit": 10}
  }'
```

The response reports `companies_created`/`companies_matched` and (for
`person_discovery`) `contacts_created`/`contacts_matched`, plus the full
records. If the provider isn't enabled in the registry: 400. If it's
enabled but the env var isn't set: 503 naming the missing variable. If the
provider call itself fails (bad key, rate limit, network error, exhausted
retries): 502.

### Apify is a two-level enable: registry + actor

Apify needs both the category-level registry row enabled *and* at least
one actor registered and enabled for that category:

```bash
# 1. Enable apify/local_business_discovery in the registry (same as above)

# 2. Register an actor for that category (superuser)
curl -s -X POST "http://localhost:8000/api/v1/apify/actors" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{
    "actor_name": "Google Maps Scraper",
    "actor_id": "compass/google-maps-scraper",
    "category": "local_business_discovery",
    "enabled": true,
    "priority": 1,
    "input_schema": {"language": "en"}
  }'

# 3. Run it the same way as any other provider
curl -s -X POST "http://localhost:8000/api/v1/search/execute" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{
    "workspace_id": "'"$WORKSPACE_ID"'",
    "provider": "apify",
    "category": "local_business_discovery",
    "criteria": {"industry": "dental clinics", "city": "Miami", "state": "FL", "limit": 10}
  }'
```

No actor registered/enabled for the category: 400. Actor(s) configured but
`APIFY_API_TOKEN` unset: 503. `input_schema` values are merged into every
run as defaults (criteria-derived `search`/`location`/`maxItems` only fill
in if the actor's schema doesn't already set them) — check the actual
actor's expected input fields and adjust `input_schema` accordingly.

## 12. Email discovery & verification walkthrough (Phase 5)

Hunter's registry rows (`hunter`/`email_finder`, `hunter`/`email_verifier`)
are already seeded — just enable them and add a real `HUNTER_API_KEY`:

```bash
# 0. Add HUNTER_API_KEY=... to .env, restart the backend.

# 1. Enable both categories (superuser)
curl -s -X GET "http://localhost:8000/api/v1/providers" -H "Authorization: Bearer $TOKEN"
# note the "id" for provider=hunter, category=email_finder — and again for email_verifier
curl -s -X PATCH "http://localhost:8000/api/v1/providers/$FINDER_ID" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"enabled": true}'
curl -s -X PATCH "http://localhost:8000/api/v1/providers/$VERIFIER_ID" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"enabled": true}'

# 2. Find an email for a contact that has a company with a known domain
curl -s -X POST "http://localhost:8000/api/v1/leads/$CONTACT_ID/find-email?workspace_id=$WORKSPACE_ID" \
  -H "Authorization: Bearer $TOKEN"

# 3. Verify it
curl -s -X POST "http://localhost:8000/api/v1/leads/$CONTACT_ID/verify?workspace_id=$WORKSPACE_ID" \
  -H "Authorization: Bearer $TOKEN"

# 4. Check the latest stored verification any time
curl -s "http://localhost:8000/api/v1/leads/$CONTACT_ID/verification?workspace_id=$WORKSPACE_ID" \
  -H "Authorization: Bearer $TOKEN"
```

`find-email` is a no-op (returns `email_found: false`, no provider call)
if the contact already has an email, and 400s if the contact has no
associated company domain to search against. `verify` 400s if the contact
has no email yet — find one first. Both 400 if no provider is enabled for
the category, and 503 naming the missing env var if enabled but
unconfigured.

## 13. Free-tier plan

The platform is provider-agnostic by design (Phase 2), so nothing forces
you to pay for anything. Two concrete pieces make free/low-cost operation
practical:

**1. OpenStreetMap — genuinely free, no signup, no API key at all.**
`OSMLocalBusinessProvider` (`app/providers/lead_sources/osm_provider.py`)
geocodes a city/state/country via Nominatim and queries businesses via the
Overpass API — both public OSM services requiring only a descriptive
User-Agent header, never credentials. It's seeded **enabled by default**
in the provider registry (migration 0007) since there's no key to be
missing — every other provider defaults disabled until you add a key.
Coverage is real but partial: it returns whatever's mapped in OSM for an
area (name, address, phone, website when listed), with a small built-in
mapping from common industries (dentist, restaurant, roofer, plumber,
electrician, hotel, gym, ...) to OSM tags, falling back to a free-text
name search for anything unmapped. It's map/directory data, not a sales
database — no decision-maker names, verified emails, or funding data. Use
it via the same `/api/v1/search/execute` endpoint as every other provider
(`"provider": "openstreetmap", "category": "local_business_discovery"`).

**2. Free-quota tracking on the existing paid providers.** `ProviderConfig`
now has a `monthly_free_quota` field, and `GET /api/v1/providers/health`
reports `calls_this_month` / `quota_remaining` computed from the
`provider_usage` log Phase 6 already keeps — so you can see, per provider,
how close you are to falling off the free tier before you get billed.
This is a local count of calls *we've* made, not a live check against the
provider's own account dashboard — if you've used the same key elsewhere,
this won't know.

Free-tier numbers below were verified via web search on 2026-08-08 (not
from training data, which goes stale) — verify current numbers yourself
before relying on them, since providers change pricing without notice:

| Provider | Free tier (seeded as `monthly_free_quota`) | Notes |
|---|---|---|
| Hunter | 25 email-finder + 50 verifier calls/month | Permanent, no card required |
| SerpApi | 250 searches/month, 50/hour cap | No card required |
| People Data Labs | 100 lookups/month (no email/phone fields) | Ongoing free tier is quite limited; a separate one-time 500-credit/30-day trial also exists but isn't quota-tracked here |
| Apollo | ~100 credits/month (uncertain) | **Not confirmed**: most sources indicate Apollo's free plan is UI-focused and API access may require a paid plan — verify before assuming the free tier works via this codebase's `ApolloCompanyDiscoveryProvider`/`ApolloPersonDiscoveryProvider` at all |
| Apify | $5 platform credit/month | Usage-based (compute units), not a call count — `monthly_free_quota` is intentionally left null; the credit runs out based on actor cost, not call count |
| PhantomBuster | 30 min/month execution (after a 14-day trial with 2 hrs) | Time-based, not a call count — also left null |
| OpenStreetMap | Unlimited | No quota because there's no tier to exceed |

Sources: [Apollo pricing](https://phantombuster.com/blog/ai-automation/apollo-pricing/), [PDL pricing](https://support.peopledatalabs.com/hc/en-us/articles/25794271805211-Pricing-credits), [SerpApi pricing](https://costbench.com/software/web-scraping/serpapi/free-plan/), [Apify pricing](https://use-apify.com/docs/what-is-apify/apify-free-plan), [Hunter pricing](https://marketbetter.ai/blog/hunter-io-pricing-breakdown-2026/), [PhantomBuster pricing](https://www.joinsecret.com/phantom-buster/pricing), [Overpass API](https://wiki.openstreetmap.org/wiki/Overpass_API).

Admins can adjust any of these via `PATCH /api/v1/providers/{id}` with
`{"monthly_free_quota": N}` as real pricing changes.

## 14. Known limitations / honesty notes (Phases 3–13)

- **Resolved 2026-08-10: migrations are now verified against real
  Postgres, not just SQLite — two real bugs were found and fixed in the
  process.** Every migration and every ORM enum column had only ever been
  exercised against the SQLite in-memory test database, which has no
  native enum type (SQLAlchemy just emits a `VARCHAR` + `CHECK`
  constraint), so two Postgres-specific bugs were silently invisible the
  entire time: (1) migrations that both explicitly `enum.create(bind,
  checkfirst=True)` *and* reuse that same enum object inline in
  `op.create_table(...)` triggered SQLAlchemy's automatic type-creation a
  second time, failing with `DuplicateObject: type "x" already exists` —
  fixed by adding `create_type=False` to the inline reference in every
  affected migration (0001, 0002, 0004, 0006, 0010, 0011, 0012). (2) Every
  `Enum(SomeStrEnum, name=...)` model column bound and validated using the
  Python enum's *member name* (`"FREE"`) rather than its *value*
  (`"free"`) by default — matching the SQLite CHECK constraint (which used
  the same default) but not the Postgres native enum type the migrations
  created with lowercase values, so the very first real insert
  (`POST /auth/register` creating a `Workspace`) failed with
  `invalid input value for enum workspace_plan: "FREE"`. Fixed with a
  shared `values_callable=str_enum_values` helper
  (`app/models/base.py`) applied to all 12 enum columns across every
  model. Both were caught by actually running `alembic upgrade head` and
  a full register→login→logout round trip against a real local Postgres
  16 instance — see §15's verification checklist entry for the exact
  commands. This is exactly the kind of gap this section exists to
  surface: something genuinely untested until it was actually run.
- **Apollo and PDL field mappings are unverified against live accounts.**
  This build environment has no network access and no real API keys for
  either provider. Both integrations were written against each provider's
  publicly documented API conventions (endpoint paths, the `x-api-key`/
  `X-Api-Key` auth header, response field names), not against an actual
  response. Field names in particular can drift between API versions —
  before relying on real data from `ApolloCompanyDiscoveryProvider`,
  `ApolloPersonDiscoveryProvider`, `PeopleDataLabsCompanyDiscoveryProvider`,
  `PeopleDataLabsPersonDiscoveryProvider`, or
  `PeopleDataLabsEnrichmentProvider`, run a search with a real key and
  check `raw_reference` on the resulting `CompanySource`/`ContactSource`
  rows against the mapped fields — adjust `_to_company`/`_to_contact` in
  the relevant provider file if anything doesn't line up.
- **PhantomBuster has the same caveat, twice over.** Not just the API shape
  (launch/poll/fetch, `resultObject` as a JSON string) but the *output*
  schema too, since it depends entirely on which Phantom the user
  configures. `PHANTOMBUSTER_AGENT_ID` currently points at a single agent
  used for both profile and post discovery — a real deployment likely
  wants separate agents (and, eventually, a registry like `ActorConfig`
  rather than one env var) once this goes beyond a single Phantom.
- **SerpApi, Apify, and Hunter are higher-confidence.** SerpApi's Google
  Maps `local_results` shape, Apify's run/dataset REST API, and Hunter's
  finder/verifier endpoints are all stable, widely used, and
  well-documented; `SerpApiLocalBusinessProvider`, `ApifyClient`, and the
  two Hunter providers are the integrations here I'd trust without a
  live-account check first (though obviously still worth testing).
- **Apify's `normalize_dataset` is generic by necessity, not a bug.**
  Since any actor can be registered, there's no fixed output schema to map
  against — it tries common aliases (`title`/`name`/`companyName`, `website`/
  `url`/`domain`, etc.) and leaves a field `None` if nothing matches. For a
  newly-registered actor, run it once and check the resulting
  `CompanySource.raw_reference` against what got mapped; extend the alias
  tuples at the top of `apify_provider.py` if a field you need isn't
  captured.
- **`/api/v1/search/execute` is a single explicit provider call, not a
  waterfall.** There's no fallback-to-next-provider, no cost tracking, and
  no provider health monitoring yet — that's Phase 6. Right now the caller
  picks exactly one enabled `(provider, category)` pair.
- **Company/contact enrichment still isn't wired into any endpoint.**
  `PeopleDataLabsEnrichmentProvider` exists and is unit-tested, but there's
  still no `POST /api/v1/companies/{id}/enrich` route calling it — Phase 5
  only wired up email finding/verification (`find-email`/`verify`), not
  general enrichment. That's deferred until an `EnrichmentOrchestrator`
  with real waterfall/minimum-necessary-calls logic exists (Phase 6),
  rather than bolting on a single-provider version now.
- **Hunter's finder is treated as "found," not "verified."** Calling
  `find-email` does not automatically verify the result — `contact.email`
  gets set with `EmailConfidence.FOUND` provenance, but you still need to
  call `verify` separately to get MX/SMTP/disposable evidence. This is
  intentional (see the spec's email-discovery-vs-verification split), not
  a missing feature.
- **`/api/v1/webhooks/email-events` has no signature/auth verification.**
  It's a public, unauthenticated endpoint that trusts whatever
  `workspace_id`/`contact_email`/`event_type` it's given. A real
  deployment needs per-ESP signature verification (SES/SNS signing,
  SendGrid's signed webhook, etc.) before this is safe to expose — that
  adapter layer isn't built. Treat this endpoint as a normalized-shape
  integration point for a trusted internal caller, not production-ready
  as-is.
- **No real ESP integrations or IMAP reply polling.** `SMTPEmailSenderProvider`
  is the only sender; SES/SendGrid/Mailgun/Postmark adapters aren't
  built (the `EmailSenderProvider` interface supports adding them without
  touching `CampaignSendingService`). Reply/bounce detection only works
  via the normalized webhook endpoint above — the spec's IMAP fallback
  path isn't implemented.
- **No retry logic for failed sends.** A `FAILED` `CampaignRecipient` stays
  failed — there's no automatic retry-with-backoff. Re-enrollment would
  require manual intervention today.
- **The very first superuser still needs a direct DB write.**
  `PATCH /api/v1/admin/users/{id}/superuser` (Phase 13) requires an
  existing superuser to call it — there's necessarily no self-service path
  to becoming the *first* one. Bootstrap it once with
  `UPDATE users SET is_superuser = true WHERE email = '...';`; every
  promotion/demotion after that can go through the API.
- **RBAC role gating (Phase 13) is applied to the highest-value write
  endpoints, not exhaustively to every write endpoint in the codebase.**
  Campaign lifecycle actions, suppression creation, and workspace member
  mutations require `require_workspace_editor`/`require_workspace_admin`/
  `require_workspace_owner` as appropriate; most other workspace-scoped
  write endpoints (companies, leads, ICP profiles, tags, notes, tasks,
  CSV import) still only require plain `require_workspace_member` —
  meaning a `viewer` can currently still write through those paths. This
  is a documented, deliberate scope cut for this phase, not an oversight;
  broadening it is a follow-up, not a redesign, since `require_workspace_editor`
  already exists as a drop-in replacement for `require_workspace_member`
  on any endpoint that should become editor-only.
- **Adding a workspace member is an existing-user-by-email lookup, not an
  invite flow.** `POST /api/v1/workspaces/{id}/members` 404s if no user is
  already registered with that email. There's no invite-token/
  signup-via-link flow (create a pending invite, email it, let the
  recipient register and land in the workspace automatically) — that's a
  larger feature not built yet.
- **`Workspace.plan`/`Workspace.limits` have no billing behind them.**
  `plan` is a label and `limits` is an operator-set JSON blob (section 78
  SaaS-plan prep); nothing charges a card or talks to a payment provider.
  The only limit actually enforced today is `limits.max_team_members` on
  member-add — other conceivable limits (`max_campaigns`, etc.) are not
  read or enforced anywhere yet, even if set.

## 15. Verification checklist

- [x] `docker-compose up --build` starts postgres, redis, backend, frontend,
      celery_worker, celery_beat, nginx without errors
- [x] `GET /health` returns `{"status": "ok"}`
- [x] `GET /ready` reports `database` and `redis` checks
- [x] `POST /api/v1/auth/register` creates a user and an owner-role workspace
      in one transaction
- [x] `POST /api/v1/auth/login` rejects wrong passwords with 401
- [x] `POST /api/v1/auth/refresh` issues a new access token from a valid
      refresh token
- [x] `GET /api/v1/auth/me` and `GET /api/v1/workspaces` reject
      unauthenticated requests with 401
- [x] `alembic upgrade head` creates `users`, `workspaces`,
      `workspace_members` tables with the `workspace_role` enum (0001), then
      `companies`, `company_sources`, `contacts`, `contact_sources`,
      `provider_configs` with a seeded (all-disabled) provider registry
      (0002), then `actor_configs` plus the `apify`/`company_discovery`
      registry row (0003), then `email_verifications` (0004), then
      `provider_usage` (0005), then `intent_signals` (0006), free-tier
      quota columns + the seeded OpenStreetMap registry row (0007), ICP
      profiles (0008), AI generations (0009), campaigns/suppression (0010),
      CRM status/notes/tasks/tags (0011), and finally `workspaces.plan`/
      `workspaces.limits` with the `workspace_plan` enum (0012)
- [x] `pytest` passes (241/241) against an isolated in-memory database
- [x] `alembic upgrade head` (0001→0012) runs cleanly against a real local
      Postgres 16 instance — verified 2026-08-10, not just SQLite. This
      caught two real Postgres-only bugs invisible on SQLite (see §14):
      a double `CREATE TYPE` in every migration that both explicitly
      creates an enum and reuses it inline in `create_table` (now fixed
      with `create_type=False` on the inline reference), and every
      `Enum(SomeStrEnum, ...)` model column binding the Python enum
      MEMBER NAME instead of its value (now fixed with a shared
      `values_callable=str_enum_values` helper in `app/models/base.py`).
      A full register→login→me→workspaces→logout→verify-revoked round
      trip against the real database succeeds end-to-end.
- [x] A valid email verification bumps a `new` lead to `verified`, a
      successful campaign send bumps `new`/`verified`/`ready_for_outreach`
      to `contacted`, and a bounce webhook updates status to `bounced` —
      but none of these ever *downgrade* an already-further-along status
      (verified test: setting a lead to `meeting` first, then verifying
      its email, leaves it at `meeting`)
- [x] `GET /api/v1/analytics/overview` counts a contact's email as
      verified only from its *latest* `EmailVerification` row (an older
      invalid result followed by a newer valid one still counts as
      verified; the reverse would not)
- [x] `positive_reply_rate` and unset-`icp_profile_id` `high_icp_leads`
      are `null`, never a guessed number
- [x] A contact on the suppression list is never sent to, whether
      suppressed manually, via unsubscribe, or via a bounce webhook
- [x] `GET /unsubscribe/{token}` creates a real `Suppression` row and a
      subsequent campaign `/process` run skips that contact
- [x] `daily_limit` is enforced across separate `/process` calls (not
      just within one call) — a second run same-day sends nothing once
      the limit is hit, reported as `skipped_no_quota: true`
- [x] A multi-step sequence only sends step 2 once its `delay_days` has
      elapsed — a same-day second `/process` run sends nothing further
- [x] Template rendering never fabricates a value for missing data
      (renders empty string) and never silently drops an unrecognized
      `{{variable}}` (left visible in the output)
- [x] A caught real bug: `CampaignSendingService` wasn't incrementing the
      `completed` counter when a recipient finished their *last* step via
      an actual send (only when there was no step to send at all) — a
      test asserting on the summary counts, not just the HTTP status,
      caught this before it shipped
- [x] `source_fields` sent to the AI model contain only actually-present
      contact/company/intent-signal data — never a placeholder for a
      missing fact — and `source_fields_used` on every `AIGeneration`
      records exactly what was offered as grounding
- [x] A generation grounded in a recent intent signal is tagged
      `personalization_source: "intent_signal"` with its `source_url`;
      one with no signal has both as `null`, never a guessed value
- [x] ICP score sums independently-optional criteria (industry, location
      with partial credit per matching field, company size, decision-maker
      contact, keywords), caps at 100, and is 0 when no criteria are set
      or data is missing (never penalizes for absence)
- [x] `/icp-profiles/parse` never saves or executes anything — returns a
      suggestion plus `unparsed_hints` for whatever it couldn't extract
- [x] `OSMLocalBusinessProvider` requires no credentials and is seeded
      enabled by default; a search via `/search/execute` with
      `"provider": "openstreetmap"` works with zero configuration
- [x] `GET /api/v1/providers/health` reports `calls_this_month` and
      `quota_remaining` computed from the local `provider_usage` log
      against each provider's seeded `monthly_free_quota`
- [x] Intent score decays correctly (fresh > 30-day-old > 45+-day-old,
      which is exactly 0) and sums/caps multiple signals at 100
- [x] Creating an intent signal without `source_url` is rejected (422) —
      there is no path to record one without a real source
- [x] PhantomBuster launch→poll→fetch cycle raises `ProviderUnavailableError`
      on an `error` container status or poll timeout, same as Apify
- [x] `/social/discover-profile` 404s on no match, 400s if the provider
      isn't enabled, 503s if credentials are missing, 403s for non-members
- [x] No secrets are hard-coded; all credentials come from `.env`
      (see `.env.example`)
- [x] Structured JSON logs redact sensitive fields (passwords, tokens,
      API keys) by key name
- [x] CSV import creates a `CompanySource`/`ContactSource` provenance row
      for every created/matched record; re-importing the same file produces
      zero duplicate companies or contacts
- [x] A CSV row with a syntactically invalid email is rejected (not stored)
      rather than silently treated as a valid contact
- [x] Cross-workspace access is rejected: a user who isn't a member of the
      `workspace_id` in the request gets 403 on companies/leads/import/export
- [x] Only a superuser can enable/disable a provider or change its priority
- [x] `POST /api/v1/search/execute` rejects a provider that isn't enabled
      in the registry with 400, and an enabled provider with no API key
      configured with 503 naming the missing env var
- [x] Apollo/PDL/SerpApi/Apify field mapping and auth-failure handling are
      covered by `httpx.MockTransport`-based tests — zero real network
      calls happen during `pytest`
- [x] Apollo's `email_not_unlocked@...` placeholder is filtered to `None`,
      never stored as a real discovered email
- [x] A `/search/execute` run against a stub provider persists a company
      with a `CompanySource` and shows up in `GET /api/v1/companies`
- [x] Apify search requires both an enabled `provider_configs` row AND an
      enabled `ActorConfig` for the category — missing either produces a
      400 naming the gap; a configured actor with no `APIFY_API_TOKEN`
      produces 503
- [x] `ApifyClient.poll_actor` raises `ProviderUnavailableError` on a
      `FAILED`/`ABORTED`/`TIMED-OUT` run status and on exceeding its max
      poll attempts, rather than hanging or silently returning nothing
- [x] Only a superuser can create or update an Apify actor config
- [x] `find-email` skips the provider call (and any HTTP request) when the
      contact already has an email, and 400s when the contact has no
      associated company domain
- [x] `verify` 400s when the contact has no email yet; a successful
      verification is stored as a new `EmailVerification` row (history
      preserved, not overwritten) and retrievable via `GET .../verification`
- [x] Hunter's `deliverable`/`undeliverable`/`risky`/unrecognized results
      map to `valid`/`invalid`/`risky`/`unknown` respectively
- [x] A matched (not newly-created) company returned from
      `/search/execute` serializes correctly after being mutated and
      committed — regression test for the `MissingGreenlet` bug caught and
      fixed during Phase 5 development (see §1, "Gotcha worth knowing")
- [x] `find-email`/`verify` fall back to the next enabled provider when one
      fails, and record a failed `ProviderUsage` row for the failing one —
      regression test for a real bug where catching the exception inside
      the `async with ProviderUsageRecorder` block hid failures from the
      usage log (see §1, "Second gotcha")
- [x] `GET /api/v1/providers/health` aggregates `provider_usage` into
      per-provider success rate/avg latency/last-success/last-failure
- [x] All enabled providers missing credentials → 503 (config problem,
      nothing attempted); all attempted providers failing → 502; providers
      attempted and genuinely finding nothing → normal 200 with no result
- [x] `POST /api/v1/workspaces` creates a second, isolated workspace and
      makes its creator the owner; `PATCH /api/v1/workspaces/{id}` (plan/
      limits) is rejected for non-owners
- [x] Adding a workspace member 404s for an unregistered email, 409s for
      an already-existing member, and 400s once `limits.max_team_members`
      is reached
- [x] A workspace's only remaining owner can't be demoted or removed (400
      on both `PATCH` and `DELETE .../members/{id}`)
- [x] A `viewer` gets 403 creating a campaign or a suppression, but can
      still list campaigns; a `member` can create a suppression
- [x] `/api/v1/admin/users` and `/api/v1/admin/providers` 403 for a
      non-superuser; a superuser can list users, promote/demote another
      user, but cannot remove their own superuser access
- [x] `GET /api/v1/admin/providers` merges a provider's registry config
      (enabled, priority, `monthly_free_quota`) with its live health
      summary (`total_calls`, `success_rate`, `quota_remaining`) in one
      response
- [x] `POST /api/v1/auth/logout` revokes the access token immediately — a
      subsequent `/auth/me` with the same token 401s — and revokes the
      refresh token too when it's included in the logout body (a
      subsequent `/auth/refresh` with it 401s); a refresh token *not*
      sent to logout keeps working
- [x] Repeated `/auth/login` calls past the configured per-IP threshold
      return 429, and the limit is scoped per-endpoint (tripping login's
      limit doesn't block register)
- [x] Every response carries `X-Content-Type-Options`, `X-Frame-Options`,
      `Referrer-Policy`, and `Permissions-Policy`; `Strict-Transport-Security`
      is present only when `ENVIRONMENT=production`
- [x] `GET /metrics` returns Prometheus-format text including
      `http_requests_total` and `http_request_duration_seconds`
- [ ] Manual smoke test: register a workspace via the Next.js UI at
      `/register`, confirm redirect to `/dashboard` showing the workspace —
      run this yourself with `docker-compose up` or the local dev servers

## 16. Security notes

- JWTs are signed with `SECRET_KEY` (HS256); access tokens expire in 30
  minutes, refresh tokens in 30 days (both configurable). Every token
  carries a unique `jti`.
- Passwords are hashed with bcrypt via `passlib`.
- CORS is restricted to `CORS_ORIGINS` (defaults to the local frontend only).
- No API keys are ever sent to the frontend; the frontend only talks to the
  backend's own `/api/v1/*` routes.
- Structured logging redacts known-sensitive field names before emitting
  JSON log lines (`app/utils/logging.py`).
- **Token revocation (Phase 14, closes a previously-documented gap)**:
  `POST /api/v1/auth/logout` now revokes the access token server-side —
  and the refresh token too, if the client sends it in the request body —
  via a Redis denylist keyed by each token's `jti`
  (`app/services/token_revocation.py`), checked on every authenticated
  request and on every `/auth/refresh` call. Entries expire from Redis at
  the token's original `exp`, so the denylist never grows unbounded. This
  costs one Redis round-trip per authenticated request — an accepted
  latency tradeoff for genuine server-side revocation rather than a
  client-side-only "logout" that leaves a stolen token valid until it
  naturally expires.
- **Rate limiting (Phase 14)**: `POST /auth/register` (5/min),
  `/auth/login` (10/min), and `/auth/refresh` (30/min) are rate-limited
  per client IP via a Redis fixed-window counter
  (`app/services/rate_limiter.py`), returning 429 once exceeded. Keyed by
  IP rather than by the submitted email/account, so it can't be abused to
  lock a real user out by hammering their address from elsewhere — the
  tradeoff is a shared IP (NAT, office network) shares one budget.
- **Security headers (Phase 14)**: every response gets
  `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`,
  `Referrer-Policy: strict-origin-when-cross-origin`, and a restrictive
  `Permissions-Policy`; `Strict-Transport-Security` is added only when
  `ENVIRONMENT=production` (see `app/middleware/security_headers.py`) —
  sending HSTS over plain HTTP in dev would be actively wrong. No
  Content-Security-Policy is set: a meaningful CSP has to be authored
  against the frontend's actual script/style origins, which lives in the
  Next.js app, not guessed at here.
- **What's still not built**: CSP headers, per-account (vs. per-IP) abuse
  detection, and refresh-token rotation/reuse-detection (today a refresh
  token stays valid — unless explicitly logged out — for its full 30-day
  life and reuse isn't specifically detected as a signal of theft). Flagged
  here rather than silently absent.

## 17. Monitoring & production deployment (Phase 14–15)

- **Structured logs**: every request gets a `request_id` (from
  `X-Request-Id` if the caller sent one, otherwise generated) bound to all
  log lines for that request via `structlog.contextvars`
  (`app/middleware/request_context.py`) — grep a `request_id` across a log
  aggregator to see everything one request did.
- **Metrics**: `GET /metrics` (root path, unauthenticated like `/health`)
  exposes Prometheus-format counters/histograms —
  `http_requests_total{method,path,status_code}` and
  `http_request_duration_seconds{method,path}` — via
  `app/utils/metrics.py`. `path` is the matched route *template* (e.g.
  `/api/v1/leads/{id}`), not the raw URL, so per-record IDs don't each
  become their own metric series. Unauthenticated by convention (a
  Prometheus scraper can't easily present app-level credentials) —
  restrict it at the reverse-proxy/network level in a real deployment
  (e.g. an nginx `location /metrics { allow <scraper-ip>; deny all; }`
  block, not shown here since it depends on your actual scrape topology).
- **Compression**: `GZipMiddleware` compresses responses over 1KB.
- **Health checks**: `GET /health` (liveness) and `GET /ready` (readiness
  — checks Postgres and Redis) already existed from Phase 1; both remain
  the endpoints `docker-compose.yml`/an orchestrator's health-check
  probes should target.
- **CI**: `.github/workflows/ci.yml` runs backend `pytest`, frontend
  `tsc --noEmit`, and a Docker build of both images on every push/PR to
  `main`. This repository isn't inside a git history in this environment,
  so the workflow hasn't actually executed anywhere yet — push it to a
  GitHub repo to see it run.
- **Production docker-compose overlay**: `infra/docker-compose.prod.yml`
  layers on top of the base file —
  `docker compose -f infra/docker-compose.yml -f infra/docker-compose.prod.yml up -d --build` —
  and adds `restart: unless-stopped`, sets `ENVIRONMENT=production`, and
  removes host port publishing for Postgres/Redis/backend/frontend so only
  nginx is reachable from outside the Docker network. It requires Compose
  v2.24+ for the `!reset` merge tag used to clear those ports (documented
  in the file's own header comment); **this override file has not been
  run against a live Docker daemon in this environment** (no `docker` CLI
  available here) — verify it with `docker compose config` before
  trusting it in a real deployment, same honesty standard as the
  unverified provider integrations in §14.
- **What production deployment still needs from the operator, not this
  repo**: TLS termination (a load balancer, Caddy, or Certbot + nginx —
  no certificate is fabricated here; `infra/nginx.conf` listens on plain
  HTTP 80 and expects a real TLS layer in front of it), a real secrets
  manager instead of a checked-in `.env` file, log shipping to an
  aggregator (structured JSON on stdout is ready to ship, nothing
  collects it yet), and a Prometheus server + Grafana (or equivalent)
  actually scraping `/metrics` — this repo exposes the metrics, it
  doesn't run the monitoring stack itself.

## 18. Roadmap

All 15 phases of the master specification are now built:

1. Scaffolding — 2. Auth/multi-tenancy — 3. Real discovery providers
(Apollo, PDL, SerpApi) — 4. Apify — 5. Email discovery/verification
(Hunter) — 6. Cost tracking & provider health/waterfall — 7. Social
signals (PhantomBuster) + free-tier plan (OpenStreetMap) — 8. Intent
signals/scoring — 9. ICP profiles/scoring — 10. AI personalization
(OpenAI) — 11. Campaigns/sending/suppression — 12. CRM/analytics/client
reporting — 13. Multi-tenancy RBAC/agency mode/admin panel — 14. Security/
monitoring/production hardening — 15. Deployment tooling (this section).

"Built" does not mean "verified against every real account/provider" —
see [§14](#14-known-limitations--honesty-notes-phases-3-13) and §17 above
for exactly what's unverified-but-implemented (Apollo/PDL field mappings,
Apify's generic normalization, the production compose overlay) versus
genuinely not implemented (CSP headers, refresh-token rotation, real ESP
webhook adapters, IMAP reply polling, retry-with-backoff for failed
sends). Do not assume any provider integration, scoring engine, or
campaign feature exists until it is actually implemented — this README is
kept in sync with what is real. In particular: `MockCompanyDiscoveryProvider`
and `MockPersonDiscoveryProvider` (`app/providers/*/mock_provider.py`)
return hard-coded fixture data for two businesses and are for tests/dev
only — they are not wired into any API route and must never be treated as
a real data source.

## 19. Troubleshooting

- **`ValueError: the greenlet library is required`**: install
  `greenlet` (already pinned in `requirements.txt`); reinstall with
  `pip install -r requirements.txt`.
- **Alembic can't connect**: confirm `DATABASE_URL` in `.env` matches a
  running Postgres instance, and that it uses the `postgresql+asyncpg://`
  scheme (Alembic itself swaps in `psycopg2` internally for sync migration
  runs — see `backend/alembic/env.py`).
- **Frontend 401 loop**: the API client reads `access_token` from
  `localStorage`; clear it and log in again if a stale/expired token is
  stuck.
- **CORS errors in the browser**: make sure `CORS_ORIGINS` in `.env`
  includes the exact origin the frontend is served from.
