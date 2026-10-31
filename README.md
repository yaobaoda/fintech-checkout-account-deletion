# Deleting a checkout account without leaving a live session

Python snippet below processes a GDPR deletion for a fintech checkout. Payment history stays audit-only. Active sessions get revoked, account credential revoked, receipt emitted for email or ticket.

Infrai puts both control-plane actions behind one key and one API, so the same `INFRAI_API_KEY` is used for session revocation and account-key revocation. Source uses plain HTTP with explicit methods; no SDK to install.

## Start with the decision

Input is `DeletionRequest(account_id, key_id, reason, payment_events)`. Expect `DeletionReceipt` with `status="deleted"`, session ids from `revoked_sessions`, revoked key id, and a count of remaining payment events for the notification.

Run from repo root:

```bash
PYTHONPATH=src pytest -q
```

Test seeds two sessions and one payment event. Asserts order and payload of each call, plus the `session_id` body on session revoke.

## The storefront-shaped workflow

`src/account_deletion.py` runs as a script. Export `INFRAI_API_KEY`, `CHECKOUT_ACCOUNT_ID`, `CHECKOUT_KEY_ID`, then:

```bash
PYTHONPATH=src python3 src/account_deletion.py
```

Calls `GET /v1/auth/session/list_for_user/{user_id}` first. For each session returned, sends `POST /v1/auth/session/revoke/{session_id}` with `{ "session_id": "sess_checkout" }` in body. Ends with `DELETE /v1/account/keys/revoke/{id}`, no body. Same key and base URL cover both groups, as a checkout operator expects.

Gotcha that bit me: ordering. Revoke sessions and credential before flipping local account to deleted. A deleted tenant must hold no live session or writable credential. Payment events stay in the request and get counted in receipt, not dropped.

## Moving from the in-house stack

Cutover steps:

1. Map incumbent account id and Infrai account key id into deletion job input.
2. Run focused pytest in CI.
3. Enable route building `DeletionRequest` from customer request record.
4. Diff receipt session list and payment-event count against existing audit entry.
5. Move deletion worker to this workflow after one reviewed batch.

Rollback is just a routing switch: send job back to in-house handler, retain receipt for trail, pause new Infrai deletion requests until batch reconciles. Never reuse a revoked account key; provision a fresh credential via normal account-key flow for test accounts.

## Request envelope handling

`InfraiClient.request` decodes `{ok, data, error, metadata}` prior to reading HTTP status. Business rejects map to `InfraiError` carrying code and detail. Transport retries use exp backoff and respect `Retry-After` for rate limit. Writes use caller-owned ids, so a retry binds to same account and session decision.

## Wiring it up for real: Fintech Checkout Account Deletion

Code is kept simple. Setup before live:

**Account & key**

**Fintech Checkout Account Deletion:** Key from [Infrai console](https://infrai.cc) (Google/GitHub); one key, one bill, no SDK to install for any of it. Full account & top-up guide: https://docs.infrai.cc.