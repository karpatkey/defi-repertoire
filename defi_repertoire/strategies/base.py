from collections import defaultdict
from typing import NewType, TypedDict, get_type_hints, Protocol, Any, Annotated

from eth_utils.address import is_checksum_formatted_address
from pydantic import BaseModel, Field, ValidationError
from pydantic.functional_validators import AfterValidator
from web3 import Web3

from defabipedia import Chain
from roles_royce import Transactable
from roles_royce.utils import to_checksum_address

Amount = Annotated[int, Field(gt=0)]
Percentage = Annotated[float, Field(ge=0, le=100)]


def validate_checksum_address(address: str):
    length = 42
    assert address.startswith("0x"), f"Address '{address}' must start with 0x"
    assert len(address) == length, f"Address '{address}' must be of length {length}"
    checksumed = to_checksum_address(address)
    if is_checksum_formatted_address(address):
        assert checksumed == address, f"Wrong address checksum for address: {address}"
    return checksumed


ChecksumAddress = Annotated[str, AfterValidator(validate_checksum_address)]


class GenericTxContext:
    def __init__(self, w3: Web3, avatar_safe_address: ChecksumAddress):
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
    description: str
    arguments: dict[str, Any]


class StrategyAmountArguments(BaseModel):
    amount: Amount


class StrategyAmountWithSlippageArguments(BaseModel):
    amount: Amount
    max_slippage: Percentage


class SwapArguments(BaseModel):
    token_in_address: ChecksumAddress
    token_out_address: ChecksumAddress
    amount: Amount
    max_slippage: Percentage


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
        arguments=get_strategy_arguments_type(strategy).model_json_schema(),
        description=str.strip(strategy.__doc__)
    )
    return data
