"""A set of scenarios to be executed by the demo scripts."""

from os import getenv
import random
import string
import asyncio
import time
from typing import NamedTuple, Optional

from . import Controller, Connection, logging_to_stdout, flows

ISSUER = getenv("ISSUER", "http://host.docker.internal:8021")
VERIFIER = getenv("VERIFIER", "http://host.docker.internal:8031")
HOLDER = getenv("HOLDER", "http://host.docker.internal:8041")
ALICE = getenv("ALICE", "http://localhost:3001")
MEDIATOR = getenv("MEDIATOR", "http://localhost:3003")
BOB = getenv("BOB", "http://localhost:3005")


def random_string(size):
    """Generate a random string."""
    return "".join(
        random.choice(string.ascii_letters + string.digits) for _ in range(size)
    )


class IssuerHolder(NamedTuple):
    issuer: Connection
    holder: Connection


class VerifierHolder(NamedTuple):
    verifier: Connection
    holder: Connection


async def connected(lhs: Controller, rhs: Controller):
    """Connect two agents."""
    return await flows.connect((lhs, rhs))


async def exchanged_dids(lhs: Controller, rhs: Controller):
    """Connect two agents through OOB and did exchange."""
    return await flows.didexchange((lhs, rhs))


async def connected_issuer_holder(
    issuer_url: Optional[str] = None, holder_url: Optional[str] = None
):
    """Connect issuer and holder."""
    issuer = Controller("issuer", issuer_url or ISSUER)
    holder = Controller("holder", holder_url or HOLDER)
    return await connected(issuer, holder)


async def connected_verifier_holder(
    verifier_url: Optional[str] = None, holder_url: Optional[str] = None
):
    """Connect verifier and holder."""
    verifier = Controller("verifier", verifier_url or VERIFIER)
    holder = Controller("holder", holder_url or HOLDER)
    return await connected(verifier, holder)


async def prepare_ledger_artifacts(issuer: Controller, *, revocable: bool = False):
    """Prepare ledger artifacts for issuing a credential."""
    await issuer.onboard()
    schema_id = await issuer.publish_schema(
        random_string(8), "0.1", ["attr0", "attr1", "attr2"]
    )
    cred_def_id = await issuer.publish_cred_def(schema_id, support_revocation=revocable)
    return schema_id, cred_def_id


async def issued_credential(
    issuer: Connection, holder: Connection, *, revocable: bool = False
):
    """Issue credential to holder."""
    _, cred_def_id = await prepare_ledger_artifacts(
        issuer.controller, revocable=revocable
    )
    return await flows.issue_credential(
        (issuer, holder),
        cred_def_id=cred_def_id,
        attr0="test0",
        attr1="test1",
        attr2="test2",
    )


async def revoked_credential(issuer: Connection, holder: Connection):
    issuer_cred_ex, holder_cred_ex = await issued_credential(
        issuer, holder, revocable=True
    )
    return await flows.revoke_credential(
        (issuer_cred_ex, holder_cred_ex), comment="revoked by demo script", publish=True
    )


async def presented_proof(
    issuer_holder: flows.ConnectedPair, verifier_holder: flows.ConnectedPair
):
    """Proof presented to verifier from holder."""
    await issued_credential(*issuer_holder)
    pres_exes = await flows.present_proof(
        verifier_holder, requested_attributes=[{"name": "attr0"}]
    )
    for pres_ex in pres_exes:
        print(pres_ex.summary())

    return pres_exes


async def present_revoked_credential(
    issuer_holder: flows.ConnectedPair, verifier_holder: flows.ConnectedPair
):
    """Present a credential that has been revoked."""
    issuer_cred_ex, _ = await revoked_credential(*issuer_holder)
    now = int(time.time())
    pres_exes = await flows.present_proof(
        verifier_holder,
        comment="presentation after revocation",
        requested_attributes=[
            {
                "name": "attr0",
                "restrictions": [
                    {"cred_def_id": issuer_cred_ex.record.credential_definition_id}
                ],
            }
        ],
        non_revoked={"from": now, "to": now},
    )
    for pres_ex in pres_exes:
        print(pres_ex.summary())

    return pres_exes


async def revocation_demo(
    issuer: Controller,
    verifier: Controller,
    holder: Controller,
):
    """Run through revocation demo."""
    from .__main__ import main

    await main(issuer, verifier, holder)


async def mediated_connection(alice: Controller, mediator: Controller, bob: Controller):
    """Completed a mediated connection."""
    async with alice.listening(), bob.listening():
        alice_mediator, mediator_alice = await connected(alice, mediator)
        mediation = await alice_mediator.request_mediation()
        await mediation.granted()
        bob_alice, invite = await bob.create_invitation(auto_accept=True)
        alice_bob = await alice.receive_invitation(invite, mediation=mediation)
        await alice_bob.update_keylist()
        await alice_bob.accept_invitation()
        await alice_bob.response_received()
        await alice_bob.send_trust_ping()
        await alice_bob.active()

        # Other way around now
        alice_bob, invite = await alice.create_invitation(mediation=mediation)
        bob_alice = await bob.receive_invitation(invite, auto_accept=True)
        await alice_bob.request_received()
        await alice_bob.update_keylist()
        await alice_bob.accept_request()
        await bob_alice.response_received()
        await bob_alice.send_trust_ping()
        await alice_bob.active()


async def main():
    logging_to_stdout()
    alice = Controller("alice", ALICE)
    mediator = Controller("mediator", MEDIATOR)
    bob = Controller("bob", BOB)

    await mediated_connection(alice, mediator, bob)


if __name__ == "__main__":
    asyncio.run(main())
