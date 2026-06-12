# Security Release Checklist

Use this checklist before any commercial release or hosted demo that touches real users, billing, exchange credentials, or live trading.

## 1. Secrets and Credentials

- [ ] Confirm no real `.env`, API key, webhook secret, private key, certificate, database dump, or token is tracked by Git.
- [ ] Run CI secret scanning and resolve every finding before merging.
- [ ] Rotate any secret that has appeared in `backend/.env`, logs, screenshots, shared archives, reports, or a public/private repository.
- [ ] Generate production `SECRET_KEY` and `ENCRYPTION_KEY` with high entropy and store them in a managed secret store.
- [ ] Keep `ENCRYPTION_KEY` stable after launch unless a planned credential re-encryption migration is ready.
- [ ] Use separate secrets for development, staging, and production.

## 2. Environment Configuration

- [ ] Copy `.env.example` only as a local template; never commit real `.env` files.
- [ ] Set `DEBUG=false` in production.
- [ ] Set `COOKIE_SECURE=true` behind HTTPS.
- [ ] Keep `CSRF_PROTECTION=true` for cookie-auth browser traffic.
- [ ] Restrict `CORS_ORIGINS` to trusted HTTPS production domains.
- [ ] Verify `DATABASE_URL`, `REDIS_URL`, and optional provider API keys point to the intended environment.

## 2a. Account Security

- [ ] Email verification is required before live trading, exchange key changes, automation changes, tenant risk changes, and deletion confirmation.
- [ ] MFA setup, backup codes, and step-up flows have been tested for sensitive operations.
- [ ] Team invitations enforce `max_users` and preserve at least one active OWNER.
- [ ] Session revocation works for current and non-current devices.

## 3. Billing and Webhooks

- [ ] Configure production Stripe price IDs and webhook signing secret.
- [ ] Verify Stripe webhook signature checks are enabled outside local debug.
- [ ] Test subscription create, update, cancellation, payment failure, and customer portal flows.
- [ ] Confirm webhook retry/idempotency behavior before enabling paid plans.

## 4. Exchange and Live Trading

- [ ] Confirm global live trading switch is enabled only in intended production environments.
- [ ] Confirm tenant-level live trading pause is off only for tenants approved for real orders.
- [ ] Use exchange API keys with minimum required permissions.
- [ ] Confirm API keys cannot withdraw funds.
- [ ] Prefer subaccounts and IP allowlists for exchange API keys.
- [ ] Test dry-run execution against production-like config before enabling live trading.
- [ ] Verify live execution requires server-side entitlement, explicit confirmation, and risk limits.
- [ ] Confirm order attempts are audited with request ID, user, tenant, mode, exchange, symbol, amount, and result.

## 4a. Commercial Frontend

- [ ] Terms and Privacy pages are reachable from the landing and registration flows.
- [ ] New users see onboarding guidance before enabling live trading.
- [ ] Billing, gated features, empty states, and health/task status surfaces render without blank panels.
- [ ] Frontend tests, typecheck, and production build pass in CI.

## 5. Docker and Deployment

- [ ] Confirm Docker build contexts exclude `.env`, caches, local databases, `node_modules`, `dist`, and reports.
- [ ] Do not rely on `docker-compose.yml` for production secret management.
- [ ] Inject production secrets through the hosting platform, orchestrator, or secret manager.
- [ ] Confirm health checks and restart policy behavior in the target environment.
- [ ] Verify database and Redis backups are configured before launch.

## 6. Dependencies and CI

- [ ] Run backend tests.
- [ ] Run frontend typecheck and production build.
- [ ] Run dependency audit for Python and npm dependencies.
- [ ] Review unpinned backend dependency ranges before production promotion.
- [ ] Enable Dependabot or Renovate for dependency updates.

## 7. Rollback and Incident Response

- [ ] Document rollback steps for frontend, backend, database migrations, and configuration changes.
- [ ] Verify access to logs, metrics, and request IDs for production debugging.
- [ ] Prepare a customer-facing incident communication path.
- [ ] Confirm admin access and emergency feature disablement paths.

## 8. Data Rights and Retention

- [ ] Full trade history export works and excludes decrypted secrets.
- [ ] Operation audit export includes request IDs.
- [ ] Account deletion request and confirmation flows have been tested.
- [ ] Retention policy cleanup has been reviewed against legal and incident-response requirements.
- [ ] Privacy page accurately describes export, deletion, and retention behavior.
