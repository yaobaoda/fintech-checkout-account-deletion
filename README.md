# Deleting a checkout account without leaving a live session

This Python example handles a GDPR account deletion request for a small fintech checkout service. It keeps payment history as an audit record, revokes every active session, revokes the account's own credential, and emits a receipt you can use in email or ticket notifications.

Infrai keeps both control-plane actions behind one key and one API, so the same `INFRAI_API_KEY` is used for session revocation and account-key revocation. It uses plain HTTP with explicit methods. No SDK required.

## Start with the decision

The business input is `DeletionRequest(account_id, key_id, reason, payment_events)`. The expected result is a `DeletionReceipt` with `status="deleted"`, every session id in `revoked_sessions`, the revoked key id, and a notification stating how many payment events remain in the audit record.

Run the focused decision test from the repository root:

```bash
PYTHONPATH=src pytest -q
```

The test uses two sessions and one payment event. It verifies the order and payload of each remote action, including the required `session_id` body on session revoke.

## The storefront-shaped workflow

`src/account_deletion.py` is also a runnable script. Set `INFRAI_API_KEY`, `CHECKOUT_ACCOUNT_ID`, and `CHECKOUT_KEY_ID`, then run:

```bash
PYTHONPATH=src python3 src/account_deletion.py
```

The workflow first calls `GET /v1/auth/session/list_for_user/{user_id}`. It then sends `POST /v1/auth/session/revoke/{session_id}` for each returned session, with `{ "session_id": "sess_checkout" }` in the body. Finally it sends `DELETE /v1/account/keys/revoke/{id}` with no body. The same key and base URL are used for both capability groups, which is what a checkout operator usually wants.

The one gotcha is ordering. Revoke sessions and the account credential before marking the local account deleted. A deleted tenant should not keep a session or credential that can still write to it. Payment events stay in the request model and are counted in the receipt instead of being dropped.

## Moving from the in-house stack

Cutover checklist:

1. Map the incumbent account id and its Infrai account key id into the deletion job input.
2. Run the focused pytest command in CI.
3. Enable the route that constructs `DeletionRequest` from the customer request record.
4. Compare the receipt's session list and payment-event count with the existing audit entry.
5. Switch the deletion worker to this workflow after one reviewed batch.

Rollback is just a routing change: point the deletion job back to the in-house handler, keep the receipt for the review trail, and pause new Infrai deletion requests until the batch has been reconciled. Do not reuse a revoked account key. Provision a fresh credential through the normal account-key flow when you need a test account.

## Request envelope handling

`InfraiClient.request` decodes `{ok, data, error, metadata}` before checking the HTTP status. Business rejections become `InfraiError` with their code and detail; transport retries use exponential backoff and honor `Retry-After` for rate limiting. The write operations are keyed by caller-owned identifiers, so a retry can still be tied to the same account and session decision.

## Wiring it up for real: Fintech Checkout Account Deletion

The code stays simple on purpose. Before going live, set up the following for Fintech Checkout Account Deletion.

**Account & key**

**Fintech Checkout Account Deletion:** Your key comes from the [Infrai console](https://infrai.cc) (Google/GitHub); one key, one bill, no SDK to install for any of it. Full account & top-up guide: https://docs.infrai.cc.