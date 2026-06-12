# Trading Runbook

Use this runbook before enabling live trading for a tenant and when debugging failed execution.

## Live Trading Gates

Live orders require every gate to pass:

1. User is authenticated and email verified.
2. Tenant plan includes `live_trading`.
3. MFA step-up succeeds when MFA is enabled.
4. `GLOBAL_LIVE_TRADING_ENABLED=true`.
5. Tenant `live_trading_paused=false`.
6. Request includes `confirm_live=true`.
7. Configured exchange is supported by the plan.
8. Monthly budget remains available.
9. Single-run and filled-order totals stay under `max_live_order_usdt`.

Dry-run remains available when live trading is globally or tenant paused.

## Common 403 Reasons

- `实盘执行 需要先完成邮箱验证`: verify the account email or resend the verification email from Settings.
- `全局实盘交易开关已关闭`: check deployment env `GLOBAL_LIVE_TRADING_ENABLED`.
- `当前租户实盘交易已暂停`: OWNER/ADMIN must review `/api/v1/admin/tenant/risk`.
- `实盘执行需要二次确认`: frontend must send `confirm_live=true`.
- `当前套餐不支持交易所`: select an exchange included in the current plan.
- `实盘单次金额不能超过 ...`: reduce budget or upgrade plan limits.

## Preflight

Run `GET /api/v1/exchange/preflight` before live execution. It summarizes:

- Email verification
- Exchange support
- API key presence
- Balance-read status
- Global and tenant live switches
- Monthly budget and remaining live spend
- Market data file freshness

The Execute page displays this as the "Live Preflight" panel.

## Request ID Debugging

Every response includes `X-Request-ID`. Error JSON also includes `request_id`.

When investigating a failure:

1. Copy the request ID from the toast or response.
2. Open the History page, switch to Operation Audit, and filter by Request ID.
3. Cross-reference server logs with the same ID.
4. For `exchange.run_dca`, parse `summary` as JSON for exchange, mode, symbols, totals, and failed order count.

## Automation Boundaries

Automation live trading is not enabled in this release.

- `automation_dry_run` can be run manually and by scheduler.
- `automation_live` remains a reserved setting and the backend refuses enabling it.
- Market data scheduler currently records heartbeat-style skips; use the Execute page's market data update action for controlled refresh.

## Exchange Key Safety

- Use a dedicated subaccount when possible.
- Enable only spot trading permissions.
- Disable withdrawals.
- Bind API keys to server egress IPs where supported.
- Rotate keys after staff changes, suspected exposure, or shared screenshots/logs.

## Team and Data Rights

- Invite users from Team; do not manually insert users unless recovering from an incident.
- Keep at least one active OWNER before role changes or deletion requests.
- Use Data Rights to export full trade history and operation audit CSV.
- Account deletion confirmation disables the account and revokes all sessions; it does not promise immediate hard deletion of audit records.

## Retention and Risk Events

- Risk events are recorded for tenant live-trading pause/resume and selected execution failures.
- Use the Ops page to review and resolve risk events.
- Retention cleanup removes old tenant-scoped operation audit, task run, and resolved risk event records according to the tenant policy.
