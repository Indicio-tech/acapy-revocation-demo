from typing import Any, Dict, List, Type, TypeVar, Union

import attr

from ..models.did_posture import DIDPosture
from ..types import UNSET, Unset

T = TypeVar("T", bound="DID")


@attr.s(auto_attribs=True)
class DID:
    """ """

    did: str
    verkey: str
    posture: Union[Unset, DIDPosture] = UNSET
    additional_properties: Dict[str, Any] = attr.ib(init=False, factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        did = self.did
        verkey = self.verkey
        posture: Union[Unset, str] = UNSET
        if not isinstance(self.posture, Unset):
            posture = self.posture.value

        field_dict: Dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "did": did,
                "verkey": verkey,
            }
        )
        if posture is not UNSET:
            field_dict["posture"] = posture

        return field_dict

    @classmethod
    def from_dict(cls: Type[T], src_dict: Dict[str, Any]) -> T:
        d = src_dict.copy()
        did = d.pop("did")

        verkey = d.pop("verkey")

        posture: Union[Unset, DIDPosture] = UNSET
        _posture = d.pop("posture", UNSET)
        if not isinstance(_posture, Unset):
            posture = DIDPosture(_posture)

        did = cls(
            did=did,
            verkey=verkey,
            posture=posture,
        )

        did.additional_properties = d
        return did

    @property
    def additional_keys(self) -> List[str]:
        return list(self.additional_properties.keys())

    def __getitem__(self, key: str) -> Any:
        return self.additional_properties[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self.additional_properties[key] = value

    def __delitem__(self, key: str) -> None:
        del self.additional_properties[key]

    def __contains__(self, key: str) -> bool:
        return key in self.additional_properties
