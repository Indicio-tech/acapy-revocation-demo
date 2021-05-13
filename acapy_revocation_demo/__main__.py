"""Run the demo."""

import json
import os
import time
from typing import cast

from acapy_client import Client
from acapy_client.api.connection import create_invitation, receive_invitation
from acapy_client.api.credential_definition import publish_cred_def
from acapy_client.api.issue_credential_v_10 import (
    get_issue_credential_records_cred_ex_id,
    issue_credential_automated,
)
from acapy_client.api.ledger import accept_taa, fetch_taa
from acapy_client.api.present_proof import get_present_proof_records, send_proof_request
from acapy_client.api.revocation import publish_revocations, revoke_credential
from acapy_client.api.schema import publish_schema
from acapy_client.api.wallet import create_did, set_public_did
from acapy_client.models import (
    CreateInvitationRequest,
    CredAttrSpec,
    CredentialDefinitionSendRequest,
    CredentialPreview,
    IndyProofRequest,
    IndyProofRequestRequestedAttributes,
    IndyProofRequestRequestedPredicates,
    PublishRevocations,
    ReceiveInvitationRequest,
    SchemaSendRequest,
    TAAAccept,
    V10CredentialExchange,
    V10CredentialProposalRequestMand,
    V10PresentationSendRequestRequest,
)
from acapy_client.types import Response
import httpx


HOLDER_URL = os.environ.get("HOLDER", "http://localhost:3001")
ISSUER_URL = os.environ.get("ISSUER", "http://localhost:3003")


def describe(description: str, api):
    def _describe(**kwargs):
        print(description)
        request = api._get_kwargs(**kwargs)
        print("Request:", json.dumps(request, indent=2))
        result: Response = api.sync_detailed(**kwargs)
        if result.status_code == 200:
            print("Response:", json.dumps(result.parsed.to_dict(), indent=2))
        else:
            raise Exception("Request failed!", result.status_code, result.content)
        return result.parsed

    return _describe


def main():
    """Run steps."""
    holder = Client(base_url=HOLDER_URL)
    issuer = Client(base_url=ISSUER_URL)

    # Establish Connection {{{
    holder_conn_record = describe("Create new invitation in holder", create_invitation)(
        client=holder, json_body=CreateInvitationRequest(), auto_accept="true"
    )

    issuer_conn_record = describe("Receive invitation in issuer", receive_invitation)(
        client=issuer,
        json_body=ReceiveInvitationRequest.from_dict(
            holder_conn_record.invitation.to_dict()
        ),
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

    issuer.timeout = 30
    result = describe(
        "Publish credential definition with revocation support", publish_cred_def
    )(
        client=issuer,
        json_body=CredentialDefinitionSendRequest(
            revocation_registry_size=10,
            schema_id=result.schema_id,
            support_revocation=True,
        ),
    )
    issuer.timeout = 5
    # }}}

    # Issue Credential and request presentation {{{
    issue_result = describe("Issue credential to holder", issue_credential_automated)(
        client=issuer,
        json_body=V10CredentialProposalRequestMand(
            connection_id=issuer_conn_record.connection_id,
            credential_proposal=CredentialPreview(
                attributes=[
                    CredAttrSpec(name="firstname", value="Bob"),
                    CredAttrSpec(name="age", value="42"),
                ]
            ),
            cred_def_id=result.credential_definition_id,
        ),
    )
    issue_result = cast(V10CredentialExchange, issue_result)
    time.sleep(1)
    result = describe("Request proof from holder", send_proof_request)(
        client=issuer,
        json_body=V10PresentationSendRequestRequest(
            connection_id=issuer_conn_record.connection_id,
            proof_request=IndyProofRequest(
                name="proof of name",
                version="0.1.0",
                requested_attributes=IndyProofRequestRequestedAttributes.from_dict(
                    {
                        "firstname": {
                            "name": "firstname",
                            "non_revoked": {"to": int(time.time())},
                        }
                    }
                ),
                requested_predicates=IndyProofRequestRequestedPredicates(),
            ),
        ),
    )
    time.sleep(1)
    result = describe("List presentations", get_present_proof_records)(client=issuer)
    # }}}

    # Revoke credential and request presentation {{{
    cred_ex = describe(
        "Retrieve credential revocation info", get_issue_credential_records_cred_ex_id
    )(client=issuer, cred_ex_id=issue_result.credential_exchange_id)

    result = describe("Revoke credential", revoke_credential)(
        client=issuer,
        cred_rev_id=cred_ex.revocation_id,
        rev_reg_id=cred_ex.revoc_reg_id,
        publish=False,
    )
    result = describe("Publish revocations", publish_revocations)(
        client=issuer, json_body=PublishRevocations()
    )
    time.sleep(10)
    result = describe(
        "Request proof from holder again after revoking", send_proof_request
    )(
        client=issuer,
        json_body=V10PresentationSendRequestRequest(
            connection_id=issuer_conn_record.connection_id,
            proof_request=IndyProofRequest(
                name="proof of name",
                version="0.1.0",
                requested_attributes=IndyProofRequestRequestedAttributes.from_dict(
                    {
                        "firstname": {
                            "name": "firstname",
                            "non_revoked": {"to": int(time.time())},
                        }
                    }
                ),
                requested_predicates=IndyProofRequestRequestedPredicates(),
            ),
        ),
    )
    time.sleep(5)
    result = describe("List presentations", get_present_proof_records)(client=issuer)
    # }}}


if __name__ == "__main__":
    main()
