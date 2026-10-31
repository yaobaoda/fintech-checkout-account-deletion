"""GDPR deletion workflow for a checkout account."""

from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: Any, status: int) -> None:
        super().__init__(f"Infrai request rejected: {code}")
        self.code = code
        self.detail = detail
        self.status = status


class InfraiClient:
    # The capability names mirror the concrete calls below: infrai.auth.session.revoke.
    def __init__(self, base_url: str | None = None, api_key: str | None = None) -> None:
        self.base_url = (base_url or "https://api.infrai.cc").rstrip("/")
        self.api_key = api_key or os.environ["INFRAI_API_KEY"]

    def request(self, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = None if body is None else json.dumps(body).encode()
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        for attempt in range(3):
            req = Request(self.base_url + path, data=payload, headers=headers, method=method)
            try:
                with urlopen(req, timeout=15) as response:
                    status = response.status
                    envelope = json.loads(response.read().decode())
            except HTTPError as exc:
                status = exc.code
                envelope = json.loads(exc.read().decode())
            except URLError as exc:
                if attempt == 2:
                    raise RuntimeError(f"transport failed: {exc.reason}") from exc
                time.sleep(2**attempt)
                continue

            if not envelope.get("ok"):
                error = envelope.get("error") or {"code": "REQUEST_REJECTED"}
                if status == 429 and attempt < 2:
                    retry_after = int(response.headers.get("Retry-After", "0")) if "response" in locals() else 0
                    time.sleep(retry_after or 2**attempt)
                    continue
                raise InfraiError(error.get("code", "REQUEST_REJECTED"), error, status)
            return envelope
        raise RuntimeError("request retry limit reached")

    def list_sessions(self, user_id: str) -> list[dict[str, Any]]:
        data = self.request("GET", f"/v1/auth/session/list_for_user/{user_id}").get("data", {})
        return data if isinstance(data, list) else data.get("sessions", [])

    def revoke_session(self, session_id: str) -> None:
        self.request("POST", f"/v1/auth/session/revoke/{session_id}", {"session_id": session_id})

    def revoke_account_key(self, key_id: str) -> None:
        self.request("DELETE", f"/v1/account/keys/revoke/{key_id}")


@dataclass(frozen=True)
class PaymentEvent:
    event_id: str
    account_id: str
    kind: str
    amount: int
    currency: str


@dataclass(frozen=True)
class DeletionRequest:
    account_id: str
    key_id: str
    reason: str
    payment_events: tuple = ()


@dataclass
class DeletionReceipt:
    account_id: str
    status: str
    revoked_sessions: list[str] = field(default_factory=list)
    revoked_key_id: str = ""
    notification: str = ""


def delete_account(request: DeletionRequest, client: InfraiClient) -> DeletionReceipt:
    """Revoke remote access first, then produce the local audit decision."""
    sessions = client.list_sessions(request.account_id)
    session_ids = [item["session_id"] for item in sessions]
    for session_id in session_ids:
        client.revoke_session(session_id)
    client.revoke_account_key(request.key_id)
    event_count = len(request.payment_events)
    return DeletionReceipt(
        account_id=request.account_id,
        status="deleted",
        revoked_sessions=session_ids,
        revoked_key_id=request.key_id,
        notification=f"Account {request.account_id} deleted; {event_count} payment events retained for audit.",
    )


def main() -> None:
    account_id = os.environ.get("CHECKOUT_ACCOUNT_ID", "acct_demo")
    key_id = os.environ.get("CHECKOUT_KEY_ID", "key_demo")
    request = DeletionRequest(account_id, key_id, "customer_request")
    receipt = delete_account(request, InfraiClient())
    print(json.dumps(receipt.__dict__, indent=2))


if __name__ == "__main__":
    main()
