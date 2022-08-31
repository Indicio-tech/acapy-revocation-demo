from os import getenv

import pytest
from acapy_revocation_demo import Controller

TIMEOUT = int(getenv("TIMEOUT", "30"))


def getenv_or_raise(var: str) -> str:
    value = getenv(var)
    if value is None:
        raise ValueError(f"Missing environmnet variable: {var}")

    return value


@pytest.fixture
def issuer():
    yield Controller("issuer", getenv_or_raise("ISSUER"), long_timeout=TIMEOUT)


@pytest.fixture
def verifier():
    yield Controller("issuer", getenv_or_raise("ISSUER"))


@pytest.fixture
def holder():
    yield Controller("issuer", getenv_or_raise("ISSUER"))
