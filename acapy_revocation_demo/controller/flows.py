"""Definitions of protocol flows."""

from typing import Any, Dict, List, Optional, Tuple

from .invitation import OOBInvitation

from .connection import Connection
from .controller import Controller
from .credential_exchange import CredentialExchange
from .presentation_exchange import PresentationExchange


Pair = Tuple[Controller, Controller]
ConnectedPair = Tuple[Connection, Connection]
CredExPair = Tuple[CredentialExchange, CredentialExchange]
PresExPair = Tuple[PresentationExchange, PresentationExchange]


async def connect(pair: Pair):
    lhs, rhs = pair
    async with lhs.listening(), rhs.listening():
        invite = await lhs.create_invitation()
        lhs_conn = await invite.connection_from_event()
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

        return lhs_conn, rhs_conn


async def didexchange(
    pair: Pair,
    use_public_did: Optional[bool] = False,
    auto_accept: Optional[bool] = False,
    multi_use: Optional[bool] = False,
    invite: Optional[OOBInvitation] = None,
    use_existing_connection: Optional[bool] = False,
):
    lhs, rhs = pair
    async with lhs.listening(), rhs.listening():
        if not invite:
            invite = await lhs.create_oob_invitation(
                use_public_did=use_public_did,
                auto_accept=auto_accept,
                multi_use=multi_use,
            )
        lhs_conn = await lhs.get_connection_from_invitation(
            invitation_msg_id=invite.invitation_id
        )
        lhs.clear_events()

        rhs_invite = await rhs.receive_oob_invitation(
            invite.invitation,
            auto_accept=auto_accept,
            use_existing_connection=use_existing_connection,
        )
        rhs_oob = await rhs_invite.oob_from_event()

        if use_existing_connection and rhs_oob.state == "reuse-accepted":
            lhs_oob = await invite.oob_from_event()
            await rhs_oob.reuse_accepted()
            return lhs.get_connection(lhs_oob.connection_id), rhs.get_connection(
                rhs_oob.connection_id
            )

        if not auto_accept:
            rhs_conn = await rhs_oob.accept_invitation()
            rhs.clear_events()

            await lhs_conn.request_received()
            await lhs_conn.accept_request()

            await rhs_conn.response_received()
            await rhs_conn.send_trust_ping()

            await lhs_conn.active()
            await rhs_conn.active()
        else:
            rhs_conn = await rhs.get_connection(rhs_oob.connection_id)

        return lhs_conn, rhs_conn


async def issue_credential(pair: ConnectedPair, *, cred_def_id: str, **attributes):
    issuer, holder = pair
    async with issuer.listening(), holder.listening():
        issuer_cred_ex = await issuer.send_credential_offer(cred_def_id, **attributes)
        holder_cred_ex = await holder.receive_cred_ex()
        assert holder_cred_ex.record.state == "offer_received"
        await holder_cred_ex.send_request()
        await issuer_cred_ex.request_received()
        await issuer_cred_ex.issue()
        await holder_cred_ex.credential_received()
        await holder_cred_ex.store()
        await issuer_cred_ex.credential_acked()
        await holder_cred_ex.credential_acked()
        return issuer_cred_ex, holder_cred_ex


async def revoke_credential(
    pair: CredExPair, *, comment: Optional[str] = None, publish: bool = False
):
    issuer_cred_ex, holder_cred_ex = pair
    async with issuer_cred_ex.listening(), holder_cred_ex.listening():
        await issuer_cred_ex.revoke(comment=comment, publish=False)
        if publish:
            await issuer_cred_ex.controller.publish_revocations()
            await holder_cred_ex.receive_revocation_notification()
        return issuer_cred_ex, holder_cred_ex


async def present_proof(
    pair: ConnectedPair,
    *,
    name: Optional[str] = None,
    version: Optional[str] = None,
    comment: Optional[str] = None,
    requested_attributes: Optional[List[Dict[str, Any]]] = None,
    requested_predicates: Optional[List[Dict[str, Any]]] = None,
    non_revoked: Optional[Dict[str, int]] = None,
):
    verifier, holder = pair
    async with verifier.listening(), holder.listening():
        verifier_pres = await verifier.request_presentation(
            name=name,
            version=version,
            comment=comment,
            requested_attributes=requested_attributes,
            requested_predicates=requested_predicates,
            non_revoked=non_revoked,
        )
        holder_pres = await holder.receive_pres_ex()
        relevant_creds = await holder_pres.fetch_relevant_credentials()
        pres_spec = await holder_pres.auto_prepare_presentation(relevant_creds)
        await holder_pres.send_presentation(pres_spec)

        await verifier_pres.presentation_received()
        await verifier_pres.verify_presentation()
        await verifier_pres.verified()
        await holder_pres.presentation_acked()
        return verifier_pres, holder_pres
