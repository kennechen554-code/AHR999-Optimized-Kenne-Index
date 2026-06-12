# Productization Roadmap

This roadmap captures the next launch-readiness work after the initial SaaS hardening, commercial UX, trading risk controls, and migration baseline.

## Phase 2A: Team Invites and RBAC

### Data Model

Add an invitation table:

- `id`
- `tenant_id`
- `email`
- `role`
- `token_hash`
- `expires_at`
- `accepted_at`
- `revoked_at`
- `created_by_user_id`
- `created_at`

### API

- `GET /api/v1/admin/users`: keep as the tenant member list.
- `POST /api/v1/admin/invitations`: OWNER/ADMIN creates an invite.
- `GET /api/v1/admin/invitations`: list pending invites.
- `DELETE /api/v1/admin/invitations/{id}`: revoke pending invite.
- `POST /api/v1/auth/invitations/accept`: accept invite, set password, create user in target tenant.
- `PATCH /api/v1/admin/users/{id}/role`: change role with safety checks.

### Safety Rules

- Enforce `Tenant.max_users` before creating or accepting invites.
- Require at least one active OWNER per tenant.
- Prevent users from demoting or disabling themselves when they are the only OWNER.
- Treat plan entitlements as product capability and role as tenant authorization.

### Frontend

Add a Team section in `SettingsPage` or a dedicated `/app/team` page:

- Member list with role and status.
- Invite form for email + role.
- Pending invite list with revoke action.
- Role change controls only for OWNER/ADMIN.

## Phase 2B: Data Rights and Compliance

### Export APIs

- `GET /api/v1/history/export`: server-side full CSV export for trade records using the same schema accepted by import.
- `GET /api/v1/audit/operations/export`: CSV export for operation audit fields, including `request_id`.
- `GET /api/v1/account/export`: portable archive metadata endpoint or zip job in a later phase.

### Portable Data Package

The eventual package should include:

- Profile and tenant metadata.
- Masked configuration without decrypted API keys.
- Trade records CSV.
- Operation audit CSV.
- Task run logs CSV or JSON.
- Billing metadata references, not raw Stripe secrets.

### Deletion Request MVP

Start with a deletion request flow instead of immediate hard delete:

1. User requests deletion.
2. System sends confirmation email.
3. Confirmed request revokes sessions and disables the account.
4. OWNER deletion requires transfer or explicit tenant deletion flow.
5. Admin/audit records keep non-secret evidence of the request.

### Policy Updates

Replace placeholder Privacy text with operational commitments:

- Export path.
- Deletion request path.
- Expected response time.
- Retention categories.
- Support contact.

## Phase 2C: Tenant Ops Page

Add an OWNER/ADMIN-only `/app/ops` page.

### Data Sources

- `GET /api/v1/health/detail`
- `GET /api/v1/tasks/status`
- `GET /api/v1/tasks/runs`
- `GET /api/v1/audit/operations?result=failed`

### Panels

- Database, Redis, Stripe webhook, SMTP readiness.
- Market data freshness by symbol.
- Task runtime status and recent failed runs.
- Recent failed operation audit rows with request ID.
- Tenant risk status, including live trading pause.

### Navigation

Link failed task rows to Settings automation.
Link failed audit rows to History operation audit with a prefilled request ID.

## Phase 3: Enterprise Security and Operations

### MFA and Step-up

Implement TOTP first:

- TOTP secret enrollment.
- Recovery codes.
- Disable/reset flow for OWNER/ADMIN.
- Step-up requirement for live trading, API key changes, role changes, tenant risk switches, and deletion requests.

### Trading Alerts

Create alert events for:

- Live order failed.
- Budget exhausted.
- Global live trading disabled.
- Tenant live trading paused.
- Three consecutive automation failures.

Delivery channels:

- In-app alert list.
- System email.
- Optional webhook/Hermes channel.

### Retention and Logs

- Add configurable retention for operation audit and task runs.
- Keep regulatory or incident exceptions.
- Adopt structured JSON logs in production with `request_id`, `tenant_id`, `user_id`, `path`, `status`, and duration.
- Keep secrets and decrypted credentials out of logs.

### Platform Admin

If cross-tenant operations are needed, design a separate platform admin boundary:

- Separate role or identity provider group.
- Explicit reason/audit for cross-tenant access.
- Read-only default.
- Break-glass flow for emergency intervention.
