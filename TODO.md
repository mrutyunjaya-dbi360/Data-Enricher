# ScrapeOps MVP — Deferred Items

These items are explicitly out of scope for Phase 1 / MVP. Do not implement them.

- Magic-link / SSO / self-serve signup
- BYOK per-user API keys (platform keys from env only)
- Master DB writes (Step 2 is read-only; matched flag still recorded)
- ClickHouse migration (Postgres only)
- Deep-crawl / multi-page Crawl4AI
- Custom output schemas
- Webhooks
- Multi-region, Kubernetes, auto-scaling
- Multi-tenant onboarding UI (MVP assumes single tenant seeded via data migration)
- Admin reassign datasource ownership UI (API only)
- Nightly rollup via Celery beat (MVP: on-job-complete only)
- Redis-based per-tenant rate limiting
- Global Crawl4AI pool (MVP: one browser per worker container)
- Invite flow / email verification beyond admin-provisioned active users
