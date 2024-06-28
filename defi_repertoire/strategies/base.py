from collections import defaultdict
from typing import NewType, TypedDict, get_type_hints, Protocol, Any

from eth_typing import Address, ChecksumAddress, AnyAddress
from pydantic import BaseModel
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


class Strategy(Protocol):
    """
    This is the protocol specification reference for Strategy classes.
    """
    kind: str
    protocol: str
    name: str

    @classmethod
    def get_txns(cls, ctx: GenericTxContext, arguments: BaseModel) -> list[Transactable]:
        ...


class StrategyDefinitionModel(BaseModel):
    """
    Strategy model to serialize and deserialize a Strategy
    """
    kind: str
    protocol: str
    name: str
    id: str
    arguments: dict[str, Any]


class StrategyAmountArguments(BaseModel):
    amount: int


class StrategyAmountWithSlippageArguments(BaseModel):
    amount: int
    max_slippage: float


class SwapArguments(BaseModel):
    token_in_address: AnyAddress
    token_out_address: AnyAddress
    amount: int
    max_slippage: float


STRATEGIES = {}

def _register_strategy(strategy):
    STRATEGIES[get_strategy_id(strategy)] = strategy

def register(cls):
    _register_strategy(cls)
    return cls


def get_strategy_arguments_type(strategy):
    return get_type_hints(strategy.get_txns)["arguments"]


def get_strategy_id(strategy):
    return f"{strategy.protocol}__{strategy.name}"

def get_strategy_by_id(strategy_id):

    return

def strategy_as_dict(strategy):
    data = StrategyDefinitionModel(
        kind=strategy.kind,
        protocol=strategy.protocol,
        name=strategy.name,
        id=get_strategy_id(strategy),
        arguments=get_strategy_arguments_type(strategy).model_json_schema())
    return data
