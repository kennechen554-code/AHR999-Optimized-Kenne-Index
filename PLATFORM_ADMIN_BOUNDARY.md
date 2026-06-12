# Platform Admin Boundary

This project currently implements tenant-level administration only. `OWNER` and `ADMIN` are tenant roles and must not be treated as platform-wide operator roles.

## Principles

- Tenant admins can manage users, invitations, tenant risk, retention, and tenant-scoped observability.
- Platform operators require a separate identity boundary.
- Cross-tenant access must be exceptional, auditable, and reason-bound.
- Read-only access should be the default for support and incident investigation.

## Future Platform Admin Model

If cross-tenant operations are required, add:

- A separate platform admin role or identity-provider group.
- A break-glass endpoint that requires a reason, ticket/reference ID, and duration.
- Audit logs that record actor, target tenant, reason, request ID, start, and end.
- Clear UI separation from tenant admin pages.

## Forbidden Shortcuts

- Do not reuse tenant `OWNER` as a platform operator.
- Do not allow cross-tenant data export without explicit audit.
- Do not bypass tenant-scoped repository filters in normal user flows.
- Do not expose decrypted API keys, SMTP passwords, or payment secrets to platform operators.
