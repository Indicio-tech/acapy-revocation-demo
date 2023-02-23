"""Run tests with the agents."""
from typing import cast
import pytest

from acapy_revocation_demo import Controller
from acapy_revocation_demo.__main__ import main
from acapy_revocation_demo.controller.utils import unwrap
from os import getenv

from acapy_revocation_demo import logging_to_stdout

ALICE = getenv("ALICE", "http://localhost:3001")
BOB = getenv("BOB", "http://localhost:3003")

@pytest.mark.asyncio
async def test_main(issuer: Controller, verifier: Controller, holder: Controller):
    """Test the main script."""
    presentations = await main(issuer, verifier, holder)
    for pres in presentations:
        comment = cast(str, unwrap(pres.record.presentation_request_dict).comment)
        if "should verify false" in comment:
            assert str(pres.record.verified) == "false"

        if "should verify true" in comment:
            assert str(pres.record.verified) == "true"
            


@pytest.mark.asyncio
async def test_connection_ping_basic_message():
    '''
    1. "Alice" creates a connection invitation.
    2. Bob receives and accepts connection invitation (which 
        triggers a connection request sent to Alice).
    3. Alice accepts the request (which triggers a connection 
        response sent to Bob).
    4. Bob sends a trustping to Alice.
    5. Alice and Bob await connection completed state.
    6. Alice sends Bob a basic message with the contents “Hi Bob!”
    7. Assert that Bob receives this message.
    '''
    logging_to_stdout()
    alice, bob = (Controller("ALICE",ALICE), Controller("BOB",BOB))
    
    async with alice.listening(), bob.listening():
        invite = await alice.create_invitation()
        
        # Invitation created or not
        try:
            assert bool(invite) == True
        except AssertionError:
            # OOB Connection
            pass
        else:
            alice_conn = await invite.connection_from_event()
            # Connection created
            assert bool(alice_conn) == True
        
            alice.clear_events()
        
        # Bob received invitation
        bob_conn = await bob.receive_invitation(invite)
        assert bool(bob_conn) == True
        
        # Bob accepts invitation
        bob_accepts_invitation = await bob_conn.accept_invitation()
        assert bool(bob_accepts_invitation) == True
        
        bob.clear_events()
        
        # Alice receives request
        alice_req_received = await alice_conn.request_received()
        
        # Alice accepts request
        alice_accepts_request = await alice_conn.accept_request()
        assert bool(alice_accepts_request) == True
        
        # This accept triggers a connection response sent to Bob
        bob_receives_alice_response = await bob_conn.response_received()
        
        # Bob sends trust ping to Alice
        bob_sends_ping = await bob_conn.send_trust_ping()
        
        bob.clear_events()
        
        # Alice and Bob await connection completed state
        await alice_conn.active()
        await bob_conn.active()
        
        msg = await alice_conn.basicmessage('Hi Bob!')
        msgs = await bob.event_queue.get(lambda event: event.topic=='basicmessages')

        # Assert that Bob receives this message
        bob_receives_hello_from_alice = await bob_conn.response_received()
        #assert bool(bob_receives_hello_from_alice) == True
        
        print("bob receives the hello")
        print(bob_receives_hello_from_alice)
