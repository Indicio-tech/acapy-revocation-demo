import logging
from os import getenv
import sys


from blessings import Terminal

from .controller import flows
from .controller.connection import Connection
from .controller.controller import Controller
from .controller.credential_exchange import CredentialExchange
from .controller.presentation_exchange import PresentationExchange


LOG_LEVEL = getenv("LOG_LEVEL", "debug")
LOGGING_SET = False


class ColorFormatter(logging.Formatter):
    def __init__(self, fmt: str):
        self.default = logging.Formatter(fmt)
        term = Terminal()
        self.formats = {
            logging.DEBUG: logging.Formatter(f"{term.dim}{fmt}{term.normal}"),
            logging.ERROR: logging.Formatter(f"{term.red}{fmt}{term.normal}"),
        }

    def format(self, record):
        formatter = self.formats.get(record.levelno, self.default)
        return formatter.format(record)


def logging_to_stdout():
    global LOGGING_SET
    if LOGGING_SET:
        return

    if sys.stdout.isatty():
        logger = logging.getLogger("acapy_revocation_demo")
        logger.setLevel(LOG_LEVEL.upper())
        ch = logging.StreamHandler()
        ch.setLevel(LOG_LEVEL.upper())
        ch.setFormatter(ColorFormatter("%(message)s"))
        logger.addHandler(ch)
    else:
        logging.basicConfig(
            stream=sys.stdout, level=logging.WARNING, format="%(message)s"
        )
        logging.getLogger("acapy_revocation_demo").setLevel(LOG_LEVEL.upper())

    LOGGING_SET = True


__all__ = [
    "Controller",
    "Connection",
    "PresentationExchange",
    "CredentialExchange",
    "flows",
]
