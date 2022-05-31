"""A set of scenarios to be executed by the demo scripts."""

from os import getenv
import random
import string
import asyncio
from typing import Optional

from .agent import Agent, Connection

ISSUER = getenv("ISSUER", "http://host.docker.internal:8021")
VERIFIER = getenv("VERIFIER", "http://host.docker.internal:8031")
HOLDER = getenv("HOLDER", "http://host.docker.internal:8041")


def random_string(size):
    """Generate a random string."""
    return "".join(
        random.choice(string.ascii_letters + string.digits) for _ in range(size)
    )


async def connected(lhs: Agent, rhs: Agent):
    """Connect two agents."""
    async with lhs.listening(), rhs.listening():
        lhs_conn, invite = await lhs.create_invitation()
        lhs.clear_events()

        rhs_conn = await rhs.receive_invitation(invite, auto_accept=False)

        await rhs_conn.accept_invitation()
        rhs.clear_events()

        await lhs_conn.request_received()
        await lhs_conn.accept_request()

        await rhs_conn.response_received()
        await rhs_conn.send_trust_ping()

        await lhs_conn.active()
        await rhs_conn.active()

        print(f"{lhs.name} connection id: {lhs_conn.connection_id}")
        print(f"{rhs.name} connection id: {rhs_conn.connection_id}")
        return lhs_conn, rhs_conn


async def connected_issuer_holder(
    issuer_url: Optional[str] = None, holder_url: Optional[str] = None
):
    """Connect issuer and holder."""
    issuer = Agent("issuer", issuer_url or ISSUER)
    holder = Agent("holder", holder_url or HOLDER)
    return await connected(issuer, holder)


async def connected_verifier_holder(
    verifier_url: Optional[str] = None, holder_url: Optional[str] = None
):
    """Connect verifier and holder."""
    verifier = Agent("verifier", verifier_url or VERIFIER)
    holder = Agent("holder", holder_url or HOLDER)
    return await connected(verifier, holder)


async def prepare_ledger_artifacts(issuer: Agent, *, revocable: bool = False):
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

    async with issuer.agent.listening(), holder.agent.listening():
        _, cred_def_id = await prepare_ledger_artifacts(
            issuer.agent, revocable=revocable
        )
        issuer_cred_ex = await issuer.issue_credential(
            cred_def_id,
            attr0="test0",
            attr1="test1",
            attr2="test2",
        )
        holder_cred_ex = await holder.get_received_cred_ex()
        assert holder_cred_ex.record.state == "offer_received"
        await holder_cred_ex.send_request()
        await issuer_cred_ex.request_received()
        # Issuer automatically issues
        await holder_cred_ex.credential_received()
        await holder_cred_ex.store()
        await issuer_cred_ex.credential_acked()
        await holder_cred_ex.credential_acked()
        print(issuer_cred_ex.summary())
        print(holder_cred_ex.summary())
        return issuer_cred_ex, holder_cred_ex


async def revoked_credential(issuer: Connection, holder: Connection):
    issuer_cred_ex, holder_cred_ex = await issued_credential(
        issuer, holder, revocable=True
    )

    async with issuer.agent.listening(), holder.agent.listening():
        await issuer_cred_ex.revoke(comment="revoked by demo script", publish=False)
        holder.agent.clear_events()
        await issuer.agent.publish_revocations()
        await holder_cred_ex.receive_revocation_notification()


async def main():
    issuer, holder = await connected_issuer_holder()
    await connected_verifier_holder()
    await revoked_credential(issuer, holder)


if __name__ == "__main__":
    asyncio.run(main())
