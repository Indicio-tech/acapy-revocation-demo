"""Run the demo."""

import asyncio
import json
import os
import time
from typing import Optional, Union, cast

from acapy_client import Client
from acapy_client.api.connection import create_invitation, receive_invitation
from acapy_client.api.credential_definition import publish_cred_def
from acapy_client.api.issue_credential_v10 import (
    issue_credential_automated,
)
from acapy_client.api.revocation import publish_revocations, revoke_credential
from acapy_client.api.ledger import accept_taa, fetch_taa
from acapy_client.api.present_proof_v10 import (
    get_present_proof_records,
    send_proof_request,
)
from acapy_client.api.schema import publish_schema
from acapy_client.api.wallet import create_did, set_public_did
from acapy_client.models import (
    CreateInvitationRequest,
    CredAttrSpec,
    CredentialDefinitionSendRequest,
    CredentialPreview,
    DIDCreate,
    IndyProofRequest,
    IndyProofRequestRequestedAttributes,
    IndyProofRequestRequestedPredicates,
    PublishRevocations,
    ReceiveInvitationRequest,
    RevokeRequest,
    SchemaSendRequest,
    SchemaSendResult,
    TAAAccept,
    TxnOrSchemaSendResult,
    V10CredentialExchange,
    V10CredentialProposalRequestMand,
    V10PresentationSendRequestRequest,
)
from acapy_client.models.indy_proof_request_non_revoked import IndyProofRequestNonRevoked
from acapy_client.models.v10_presentation_exchange import V10PresentationExchange
from acapy_client.models.v10_presentation_exchange_list import V10PresentationExchangeList
from acapy_client.types import Response
import httpx


HOLDER_URL = os.environ.get("HOLDER", "http://localhost:3001")
ISSUER_URL = os.environ.get("ISSUER", "http://localhost:3003")


def describe(description: str, api):
    def _describe(**kwargs):
        print(description)
        request = api._get_kwargs(**kwargs)
        print("Request:", json.dumps(request, sort_keys=True, indent=2))
        result: Response = api.sync_detailed(**kwargs)
        if result.status_code == 200:
            print(
                "Response:",
                json.dumps(
                    result.parsed.to_dict() if result.parsed else {},
                    indent=2,
                    sort_keys=True,
                ),
            )
        else:
            raise Exception("Request failed!", result.status_code, result.content)
        return result.parsed

    return _describe

def presentation_result_summary(pres: V10PresentationExchange):
    print(f"Presentation identified by {pres.presentation_request.name}: {pres.presentation_request_dict.id}")
    print(json.dumps({
        "state": pres.state or None,
        "verified": pres.verified or None,
        "presentation_request": pres.presentation_request.to_dict(),
        "comment": pres.presentation_request_dict.comment,
    }, indent=2))


async def main():
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
        auto_accept="true",
    )
    # }}}

    # Prepare for writing to ledger {{{
    did_info = describe(
        "Create new DID for publishing to ledger in issuer", create_did
    )(client=issuer, json_body=DIDCreate()).result

    print("Publishing DID through https://selfserve.indiciotech.io")
    response = httpx.post(
        url="https://selfserve.indiciotech.io/nym",
        json={
            "network": "testnet",
            "did": did_info.did,
            "verkey": did_info.verkey,
        },
        timeout=30,
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
    result: Optional[Union[TxnOrSchemaSendResult, SchemaSendResult]] = describe(
        "Publish schema to the ledger", publish_schema
    )(
        client=issuer,
        json_body=SchemaSendRequest(
            attributes=["firstname", "age"],
            schema_name="revocation_testing",
            schema_version="0.1.0",
        ),
    )

    assert result
    assert isinstance(result, SchemaSendResult)
    result = describe(
        "Publish credential definition with revocation support", publish_cred_def
    )(
        client=issuer.with_timeout(30),
        json_body=CredentialDefinitionSendRequest(
            revocation_registry_size=10,
            schema_id=result.schema_id,
            support_revocation=True,
        ),
    )
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
    print("Waiting 10 seconds for credential issuance to complete...")
    time.sleep(10)
    non_revoked_time = int(time.time())
    result = describe("Request proof from holder", send_proof_request)(
        client=issuer,
        json_body=V10PresentationSendRequestRequest(
            comment="Before revocation",
            connection_id=issuer_conn_record.connection_id,
            proof_request=IndyProofRequest(
                name="proof of name",
                version="0.1.0",
                requested_attributes=IndyProofRequestRequestedAttributes.from_dict(
                    {
                        "firstname": {
                            "name": "firstname",
                        }
                    }
                ),
                requested_predicates=IndyProofRequestRequestedPredicates(),
                non_revoked=IndyProofRequestNonRevoked.from_dict(
                    {"from": non_revoked_time, "to": non_revoked_time}
                ),
            ),
        ),
    )
    print("Waiting 5 seconds for presentation to complete...")
    time.sleep(5)
    # }}}

    # Revoke credential and request presentation {{{
    result = describe("Revoke credential", revoke_credential)(
        client=issuer,
        json_body=RevokeRequest(
            cred_ex_id=issue_result.credential_exchange_id,
            publish=False,
        ),
    )
    before_revoking_time = non_revoked_time
    result = describe("Publish revocations", publish_revocations)(
        client=issuer.with_timeout(30),
        json_body=PublishRevocations()
    )
    print("Waiting 10 seconds for revocation to propagate...")
    time.sleep(10)
    non_revoked_time = int(time.time())
    result = describe(
        "Request proof from holder again after revoking", send_proof_request
    )(
        client=issuer,
        json_body=V10PresentationSendRequestRequest(
            comment="After revocation (should verify false)",
            connection_id=issuer_conn_record.connection_id,
            proof_request=IndyProofRequest(
                name="proof of name",
                version="0.1.0",
                requested_attributes=IndyProofRequestRequestedAttributes.from_dict(
                    {
                        "firstname": {
                            "name": "firstname",
                        }
                    }
                ),
                requested_predicates=IndyProofRequestRequestedPredicates(),
                non_revoked=IndyProofRequestNonRevoked.from_dict(
                    {"from": non_revoked_time, "to": non_revoked_time}
                ),
            ),
        ),
    )
    print("Waiting 10 seconds for presentation to complete...")
    time.sleep(10)
    result = describe(
        "Attempt another proof with non_revoked interval to before revocation", send_proof_request
    )(
        client=issuer,
        json_body=V10PresentationSendRequestRequest(
            comment="After revocation, interval before revocation (should verify true)",
            connection_id=issuer_conn_record.connection_id,
            proof_request=IndyProofRequest(
                name="proof of name",
                version="0.1.0",
                requested_attributes=IndyProofRequestRequestedAttributes.from_dict(
                    {
                        "firstname": {
                            "name": "firstname",
                        }
                    }
                ),
                requested_predicates=IndyProofRequestRequestedPredicates(),
                non_revoked=IndyProofRequestNonRevoked.from_dict(
                    {"from": before_revoking_time, "to": before_revoking_time}
                ),
            ),
        ),
    )
    print("Waiting 10 seconds for presentation to complete...")
    time.sleep(10)
    result = describe(
        "Attempt another proof with no non_revoked interval", send_proof_request
    )(
        client=issuer,
        json_body=V10PresentationSendRequestRequest(
            comment="After revocation, no non_revoked interval provided (should verify true)",
            connection_id=issuer_conn_record.connection_id,
            proof_request=IndyProofRequest(
                name="proof of name",
                version="0.1.0",
                requested_attributes=IndyProofRequestRequestedAttributes.from_dict(
                    {
                        "firstname": {
                            "name": "firstname",
                        }
                    }
                ),
                requested_predicates=IndyProofRequestRequestedPredicates(),
            ),
        ),
    )
    print("Waiting 10 seconds for presentation to complete...")
    time.sleep(10)
    non_revoked_time = int(time.time())
    result = describe(
        "Attempt another proof with non_revoked interval and local non_revoked override", send_proof_request
    )(
        client=issuer,
        json_body=V10PresentationSendRequestRequest(
            comment="After revocation, non_revoked interval and local non_revoked override (should verify true)",
            connection_id=issuer_conn_record.connection_id,
            proof_request=IndyProofRequest(
                name="proof of name",
                version="0.1.0",
                requested_attributes=IndyProofRequestRequestedAttributes.from_dict(
                    {
                        "firstname": {
                            "name": "firstname",
                            "non_revoked": {"from": before_revoking_time, "to": before_revoking_time}
                        }
                    }
                ),
                requested_predicates=IndyProofRequestRequestedPredicates(),
                non_revoked=IndyProofRequestNonRevoked.from_dict(
                    {"from": non_revoked_time, "to": non_revoked_time}
                ),
            ),
        ),
    )
    print("Waiting 10 seconds for presentation to complete...")
    time.sleep(10)
    non_revoked_time = int(time.time())
    result = describe(
        "Attempt another proof with only local non_revoked interval", send_proof_request
    )(
        client=issuer,
        json_body=V10PresentationSendRequestRequest(
            comment="After revocation, local non_revoked interval only (should verify false)",
            connection_id=issuer_conn_record.connection_id,
            proof_request=IndyProofRequest(
                name="proof of name",
                version="0.1.0",
                requested_attributes=IndyProofRequestRequestedAttributes.from_dict(
                    {
                        "firstname": {
                            "name": "firstname",
                            "non_revoked": {"from": non_revoked_time, "to": non_revoked_time}
                        }
                    }
                ),
                requested_predicates=IndyProofRequestRequestedPredicates(),
            ),
        ),
    )
    print("Waiting 10 seconds for presentations to complete...")
    time.sleep(10)
    presentations = describe("List presentations", get_present_proof_records)(client=issuer)
    for pres in presentations.results:
        presentation_result_summary(pres)
    # }}}


if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())
