# Design Decisions

- Single tenant seeded on first migration with name "Default", slug "default".
- JWT via djangorestframework-simplejwt (access + refresh + blacklist on logout).
- Celery concurrency forced to 1 per worker process; scale horizontally with more worker containers.
- EventEmitter uses a lock + list buffer + daemon flush thread; failures on flush are logged, never raised into pipeline.
- Pricing hardcoded; costs stored on Event at emit time.
- Job resume only from `paused` (credit); cancelled jobs are terminal.
- Field mapping defaults to the pipeline's DEFAULT_CONTEXT_FIELD_MAP when not supplied.
- SSE stream endpoint uses Django StreamingHttpResponse with periodic Job counter poll (no Redis pubsub for MVP).
- SSRF resolver uses socket.getaddrinfo with 5s timeout; blocks on any private IP including link-local metadata.
- Admin "View as" filter is client-side sessionStorage only; API still scopes by authenticated user unless admin passes user_id on metrics endpoints.
