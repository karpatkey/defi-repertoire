import pytest
from pydantic import BaseModel, ValidationError

from defi_repertoire.strategies.base import ChecksumAddress


def test_checkum_address():
    class DemoModel(BaseModel):
        address: ChecksumAddress

    good_checksumed_address = "0x8353157092ED8Be69a9DF8F95af097bbF33Cb2aF"
    bad_checksumed_address = "0x8353157092ED8Be69a9DF8F95af097bbF33Cb2af"

    # input is checksumed
    assert DemoModel(address=good_checksumed_address).address == good_checksumed_address

    # input is not checksumed then the output is checksumed
    assert (
        DemoModel(address=str.lower(good_checksumed_address)).address
        == good_checksumed_address
    )

    # input has a wrong cheksum
    with pytest.raises(ValidationError):
        DemoModel(address=bad_checksumed_address)

    # Wrong length
    with pytest.raises(ValidationError):
        DemoModel(address="0xaf20477")

    # must start with 0x
    with pytest.raises(ValidationError):
        DemoModel(address="8353157092ED8Be69a9DF8F95af097bbF33Cb2aF")
