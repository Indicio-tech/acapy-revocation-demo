"""Interface for interacting with an agent."""
import logging
from typing import (
    Optional,
    TypeVar,
    Union,
)

from acapy_client.types import Unset


LOGGER = logging.getLogger(__name__)


T = TypeVar("T")


def unwrap(value: Union[Unset, T]) -> T:
    """Unwrap a potentially unset value."""
    assert not isinstance(value, Unset)
    return value


def unwrap_or(value: Union[Unset, T], default: Optional[T] = None) -> Optional[T]:
    """Unwrap a potentially unset value, returning a default if given."""
    if not isinstance(value, Unset):
        return value
    return default
