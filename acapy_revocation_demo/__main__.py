"""Run the demo."""

import json
import os
from acapy_client.models.schema_send_request import SchemaSendRequest
import httpx

from acapy_client import Client
from acapy_client.api.connection import create_invitation, receive_invitation
from acapy_client.api.wallet import create_did, set_public_did
from acapy_client.api.schema import publish_schema
from acapy_client.api.ledger import accept_taa, fetch_taa
from acapy_client.models import (
    CreateInvitationRequest,
    ReceiveInvitationRequest,
    TAAAccept,
)


HOLDER_URL = os.environ.get("HOLDER", "http://localhost:3001")
ISSUER_URL = os.environ.get("ISSUER", "http://localhost:3003")


def describe(description: str, api):
    def _describe(**kwargs):
        print(description)
        request = api._get_kwargs(**kwargs)
        print("Request:", json.dumps(request, indent=2))
        result = api.sync(**kwargs)
        assert result
        print("Response:", json.dumps(result.to_dict(), indent=2))
        return result

    return _describe


def main():
    """Run steps."""
    holder = Client(base_url=HOLDER_URL)
    issuer = Client(base_url=ISSUER_URL)

    # Establish Connection {{{
    invite = describe("Create new invitation in holder", create_invitation)(
        client=holder, json_body=CreateInvitationRequest(), auto_accept="true"
    )

    describe("Receive invitation in issuer", receive_invitation)(
        client=issuer,
        json_body=ReceiveInvitationRequest.from_dict(invite.invitation.to_dict()),
    )
    # }}}

    # Prepare for writing to ledger {{{
    did_info = describe(
        "Create new DID for publishing to ledger in issuer", create_did
    )(client=issuer).result

    print("Publishing DID through https://selfserve.indiciotech.io")
    response = httpx.post(
        url="https://selfserve.indiciotech.io/nym",
        json={
            "network": "testnet",
            "did": did_info.did,
            "verkey": did_info.verkey,
        },
    )
    if response.is_error:
        print("Failed to publish DID:", response.text)
        return
    print("DID Published")

    result = describe(
        "Retrieve Transaction Author Agreement from the ledger", fetch_taa
    )(client=issuer).result

    result = describe("Sign transaction author agreement", accept_taa)(
        client=issuer,
        json_body=TAAAccept(
            mechanism="on_file",
            text=result.taa_record.text,
            version=result.taa_record.version,
        ),
    )

    result = describe("Set DID as public DID for issuer", set_public_did)(
        client=issuer, did=did_info.did
    ).result
    print(result.posture)
    # }}}

    # Prepare Credential ledger artifacts {{{
    result = describe("Publish schema to the ledger", publish_schema)(
        client=issuer,
        json_body=SchemaSendRequest(
            attributes=["firstname", "age"],
            schema_name="revocation_testing",
            schema_version="0.1.0",
        ),
    )
    print(result)
    # }}}


if __name__ == "__main__":
    main()
