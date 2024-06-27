from collections import defaultdict
from typing import NewType, TypedDict

from eth_typing import Address, ChecksumAddress, AnyAddress
from web3 import Web3

from defabipedia import Chain
from roles_royce import Transactable
from roles_royce.utils import to_checksum_address

BlockOperation = NewType("BlockOperation", str)
SwapOperation = NewType("SwapOperation", BlockOperation)
WithdrawOperation = NewType("WithdrawOperation", BlockOperation)
UnstakeOperation = NewType("UnstakeOperation", BlockOperation)
UnwrapOperation = NewType("UnwrapOperation", BlockOperation)
RedeemOperation = NewType("RedeemOperation", BlockOperation)
TransactableChain = NewType("TransactableChain", list[Transactable])


class GenericTxContext:
    def __init__(self, w3: Web3, avatar_safe_address: AnyAddress):
        self.w3 = w3
        self.avatar_safe_address = to_checksum_address(avatar_safe_address)
        self.blockchain = Chain.get_blockchain_from_web3(self.w3)
        self.ctx = defaultdict(dict)


class StrategyAmountArguments(TypedDict):
    amount: int


class StrategyAmountWithSlippageArguments(TypedDict):
    amount: int
    max_slippage: float


class SwapArguments(TypedDict):
    token_in_address: AnyAddress
    token_out_address: AnyAddress
    amount: int
    max_slippage: float


STRATEGIES = []


def _register_strategy(strategy):
    STRATEGIES.append(strategy)


def register(cls):
    _register_strategy(cls)
    return cls
