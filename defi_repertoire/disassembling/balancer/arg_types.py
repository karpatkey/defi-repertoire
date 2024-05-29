from typing_extensions import TypedDict
from roles_royce.protocols.base import Address


class ProportionalArgs(TypedDict):
    bpt_address: Address
    amount_to_redeem: int
    max_slippage: float


class SingleTokenArgs(TypedDict):
    bpt_address: Address
    max_slippage: float
    token_out_address: str


class Exit13ArgumentElement(TypedDict):
    bpt_address: Address


class Exit21ArgumentElement(TypedDict):
    gauge_address: Address
    max_slippage: float


class Exit22ArgumentElement(TypedDict):
    gauge_address: Address
    max_slippage: float
    token_out_address: str


class Exit23ArgumentElement(TypedDict):
    gauge_address: Address
    max_slippage: float
