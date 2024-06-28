from collections import defaultdict
import dataclasses
import enum
import os

from fastapi import FastAPI
from pydantic import BaseModel

from defi_repertoire.strategies.base import (
    GenericTxContext,
    STRATEGIES,
    get_strategy_arguments_type,
    strategy_as_dict,
)
from defi_repertoire.strategies import disassembling, swaps
from roles_royce.generic_method import Operation
from roles_royce.utils import multi_or_one
from defabipedia.types import Chain, Blockchain
from web3 import Web3

Protocols = enum.StrEnum(
    "Protocols", {s.protocol: s.protocol for s in STRATEGIES.values()}
)
StrategyKinds = enum.StrEnum(
    "StrategyKinds", {s.kind: s.kind for s in STRATEGIES.values()}
)
BlockchainOption = enum.StrEnum(
    "BlockchainOption", {name: name for name in Chain._by_name.values()}
)

ENDPOINTS = {Chain.ETHEREUM: [os.getenv("RPC_MAINNET_URL")]}


class StrategyCall(BaseModel):
    id: str
    arguments: dict


class TransactableData(BaseModel):
    contract_address: str
    data: str
    operation: Operation
    value: int


def get_endpoint_for_blockchain(blockchain: Blockchain):
    if blockchain == Chain.ETHEREUM:
        url = ENDPOINTS[blockchain][0]
    else:
        raise NotImplementedError("Blockchain not supported.")
    return Web3(Web3.HTTPProvider(url))


def to_transactabledata(transactable):
    return TransactableData(
        operation=transactable.operation,
        data=transactable.data,
        value=transactable.value,
        contract_address=transactable.contract_address,
    )


app = FastAPI()


@app.get("/")
async def root():
    return {"message": "DeFi Repertoire API"}


@app.get("/status")
async def status():
    return {"message": "Ok"}


@app.get(f"/strategy/list")
def list_strategies():
    return {"strategies": [strategy_as_dict(s) for s in STRATEGIES.values()]}


@app.post(f"/strategy/txns/")
def txns(
    blockchain: BlockchainOption,
    avatar_safe_address: str,
    strategy_calls: list[StrategyCall],
):
    blockchain = Chain.get_blockchain_by_name(blockchain)
    w3 = get_endpoint_for_blockchain(blockchain)
    ctx = GenericTxContext(w3=w3, avatar_safe_address=avatar_safe_address)
    txns: list[TransactableData] = []
    for call in strategy_calls:
        strategy = STRATEGIES[call.id]
        arguments = get_strategy_arguments_type(strategy)(**call.arguments)
        strategy_txns = strategy.get_txns(ctx=ctx, arguments=arguments)
        for txn in strategy_txns:
            txns.append(
                TransactableData(
                    operation=txn.operation,
                    value=txn.value,
                    data=txn.data,
                    contract_address=txn.contract_address,
                )
            )

    return {"txns": txns}


@app.post(f"/multisend/")
def multisend(blockchain: BlockchainOption, txns: list[TransactableData]):
    blockchain = Chain.get_blockchain_by_name(blockchain)
    txn = multi_or_one(txs=txns, blockchain=blockchain)
    return {"txn": dataclasses.asdict(txn)}


# TODO
@app.post(f"/build_role_txn/")
# receives everything and build the payload needed for a later execution step with a specified safe,
# roles mod contract, and a role number
def build_role_txn(
    blockchain: BlockchainOption,
    txns: list[StrategyCall],
    role_mod_contract,
    role,
):
    blockchain = Chain.get_blockchain_by_name(blockchain)
    txn = multi_or_one(txs=txns, blockchain=blockchain)

    return {"txn": dataclasses.asdict(txn)}

# Endpoints for each strategy
STRATEGIES_BY_PROTOCOL_AND_NAME = defaultdict(dict)

for strategy_id, strategy in STRATEGIES.items():
    strategy_name = strategy.name
    kind = strategy.kind
    arguments_type = get_strategy_arguments_type(strategy)
    STRATEGIES_BY_PROTOCOL_AND_NAME[strategy.protocol][strategy_name] = strategy

    def make_closure(kind, protocol, strategy_name, arg_type):
        # As exit arguments is a custom type (a dict) and FastAPI does not support complex types
        # in the querystring (https://github.com/tiangolo/fastapi/discussions/7919)
        # We have mainly two options:
        #  1) Use a json string in the querystring, but we will not have the schema documentation and validation.
        #  2) Use a request body. As GET requests body are not supported in all the languages, then we also let POST for the endpoint
        #     even if the semantic is of a GET.
        #  3) Just use POST.
        #
        # For the time being the option 3) is implemented
        url = f"/txns/{kind}/{protocol}/{strategy_name}/"

        # @app.get(url)
        @app.post(url, description=strategy.__doc__)
        def transaction_data(
            blockchain: BlockchainOption, avatar_safe_address: str, arguments: arg_type
        ):
            blockchain = Chain.get_blockchain_by_name(blockchain)
            strategy = STRATEGIES_BY_PROTOCOL_AND_NAME.get(protocol).get(strategy_name)
            w3 = get_endpoint_for_blockchain(blockchain)
            ctx = GenericTxContext(w3=w3, avatar_safe_address=avatar_safe_address)
            txns = strategy.get_txns(ctx=ctx, arguments=arguments)

            return {"txns": [to_transactabledata(txn) for txn in txns]}

    make_closure(kind, strategy.protocol, strategy.name, arguments_type)
