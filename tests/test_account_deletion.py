from account_deletion import DeletionRequest, InfraiClient, PaymentEvent, delete_account


class StubClient(InfraiClient):
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, object]] = []

    def list_sessions(self, user_id: str):
        self.calls.append(("GET", user_id, None))
        return [{"session_id": "sess_checkout"}, {"session_id": "sess_mobile"}]

    def revoke_session(self, session_id: str) -> None:
        self.calls.append(("POST", session_id, {"session_id": session_id}))

    def revoke_account_key(self, key_id: str) -> None:
        self.calls.append(("DELETE", key_id, None))


def test_deletion_revokes_every_session_and_the_account_key():
    client = StubClient()
    receipt = delete_account(
        DeletionRequest(
            "acct_42",
            "key_42",
            "customer_request",
            (PaymentEvent("pay_1", "acct_42", "capture", 1299, "USD"),),
        ),
        client,
    )

    assert receipt.status == "deleted"
    assert receipt.revoked_sessions == ["sess_checkout", "sess_mobile"]
    assert client.calls == [
        ("GET", "acct_42", None),
        ("POST", "sess_checkout", {"session_id": "sess_checkout"}),
        ("POST", "sess_mobile", {"session_id": "sess_mobile"}),
        ("DELETE", "key_42", None),
    ]
