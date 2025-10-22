# BossQ AI Workspace

The BossQ AI workspace now runs on a Supabase-backed foundation derived from the GrowNext starter. The childcare dashboards remain intact while authentication, organization management, and API services are provided by the new shared packages.

## Project Layout

```
apps/
  api/          Fastify API with Supabase auth + Prisma (placeholder during migration)
  web/          Next.js 14 client (Supabase auth + BossQ childcare dashboards)
  worker/       Playwright-based invoice automation worker (Python)
packages/
  core/         Env loading, logging, Supabase JWT helpers
  db/           Prisma schema + organization/user services
  contracts/    Shared Zod contracts (auth + BossQ domain types)
  ui/           Shared component library & Tailwind preset
  config/       tsconfig / eslint / vitest presets
supabase/       Supabase CLI config.toml and seed data
scripts/        Utility scripts (e.g. invoice_downloader maintenance helpers)
```

## Prerequisites

- Node.js ≥ 20.11 (WSL recommended on Windows)
- pnpm ≥ 8.15 (`corepack enable pnpm`)
- Docker Desktop with WSL2 backend
- Supabase CLI (`npm install -g supabase`)
- Python ≥ 3.10 (for the BossQ invoice worker)

## Initial Setup

1. **Install dependencies**
   ```bash
   pnpm install
   ```
2. **Python worker environment**
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -e .
   playwright install
   ```
3. **Environment variables**
   - Copy `.env.example` → `.env` and fill in Supabase keys (`SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, etc.).
   - Copy `apps/web/.env.local.example` → `apps/web/.env.local` for client-side overrides.
   - Set `GEMINI_API_KEY` (optional) to re-enable the AI query demo.
4. **Run Supabase locally**
   ```bash
   pnpm supabase:start
   ```
   The CLI spins up the Supabase Docker stack using `supabase/config.toml` and writes credentials to `supabase/.env`. Mirror those values into `.env` so the API, web client, and worker can connect.
5. **Provision the database**
   ```bash
   pnpm db:generate
   pnpm db:push
   ```
   This generates the Prisma client and pushes the GrowNext auth + organization schema into your local Supabase Postgres instance.
6. **Start local services**
   ```bash
   pnpm api:dev    # Fastify API on http://localhost:3001
   pnpm web:dev    # Next.js UI on http://localhost:3000
   pnpm worker:dev # BossQ invoice worker (bridges to Python Playwright runner)
   ```
   Redis is expected on `redis://localhost:6379` (update `.env` to `redis://redis:6379` when running through Docker). When iterating on the Python worker directly, you can still run `python -m invoice_downloader` from `apps/worker`.

## Docker Workflow

`Dockerfile.dev` plus `docker-compose.yml` provide a container-first dev setup:

```bash
docker compose up --build
```

This mounts the workspace into dev containers that run `pnpm install` on demand and start the API, web, and worker services alongside a Redis container. Stop with `docker compose down`. Supabase still runs via `pnpm supabase:start`; expose it on `host.docker.internal` (see `.env.example`) so the containers can reach it.

## Useful Scripts

| Command | Description |
| --- | --- |
| `pnpm api:dev` | Start the Fastify API with tsx watcher |
| `pnpm web:dev` | Start the Next.js dev server |
| `pnpm worker:dev` | Start the BossQ Playwright worker bridge |
| `python -m invoice_downloader` | Run the Python Playwright worker directly |
| `pnpm worker:enqueue` | Enqueue a test job into the worker queue |
| `pnpm db:generate` | Run `prisma generate` for `@bossq/db` |
| `pnpm db:push` | Push Prisma schema into Supabase |
| `pnpm supabase:start` / `pnpm supabase:stop` | Manage the local Supabase stack |
| `pnpm build` | Turbo build for all workspaces |
| `pnpm lint` | Turbo lint (Next.js lint still reports pre-existing UI issues) |

### Python worker quality checks

Run the Playwright worker's static analysis locally before opening a pull request:

```bash
ruff check .
mypy apps/worker/src
```

The `ruff` invocation sweeps the entire repository, while `mypy` focuses on the
Python worker package that houses the invoice automation entrypoint.

## Next Steps

- Replace mocked BossQ childcare data with Supabase queries using the new API endpoints.
- Address remaining `next lint` warnings (`react/no-children-prop`, a11y click handlers, etc.).
- Harden Docker for production (multi-stage build, prebuilt artifacts) once the dev flow is stable.

Happy building!
