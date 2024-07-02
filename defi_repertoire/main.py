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
    ChecksumAddress,
)
from defi_repertoire.strategies import disassembling, swaps
from roles_royce.generic_method import Operation
from roles_royce.protocols.roles_modifier.contract_methods import (
    get_exec_transaction_with_role_method,
)
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
    contract_address: ChecksumAddress
    data: str
    operation: Operation
    value: int

    @classmethod
    def from_transactable(cls, transactable):
        """Build a TransactableData from a Transactable-like object"""
        return cls(
            operation=transactable.operation,
            data=transactable.data,
            value=transactable.value,
            contract_address=transactable.contract_address,
        )


def get_endpoint_for_blockchain(blockchain: Blockchain):
    if blockchain == Chain.ETHEREUM:
        url = ENDPOINTS[blockchain][0]
    else:
        raise NotImplementedError("Blockchain not supported.")
    return Web3(Web3.HTTPProvider(url))


def strategies_to_transactions(
    blockchain: Blockchain,
    avatar_safe_address: ChecksumAddress,
    strategy_calls: list[StrategyCall],
):
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
    return txns


app = FastAPI()


@app.get("/")
async def root():
    return {"message": "DeFi Repertoire API"}


@app.get("/status")
async def status():
    return {"message": "Ok"}


@app.get(f"/strategies")
def list_strategies():
    return {"strategies": [strategy_as_dict(s) for s in STRATEGIES.values()]}


@app.post(f"/strategies-to-transactions")
def strategy_transactions(
    blockchain: BlockchainOption,
    avatar_safe_address: ChecksumAddress,
    strategy_calls: list[StrategyCall],
    multisend: bool = False,
):
    blockchain = Chain.get_blockchain_by_name(blockchain)
    txns = strategies_to_transactions(blockchain, avatar_safe_address, strategy_calls)
    if multisend:
        txns = [multi_or_one(txs=txns, blockchain=blockchain)]
    return {"txns": txns}


@app.post(f"/strategies-to-exec-with-role")
def strategies_to_exec_with_role(
    blockchain: BlockchainOption,
    avatar_safe_address: ChecksumAddress,
    roles_mod_address: ChecksumAddress,
    role: int | str,
    strategy_calls: list[StrategyCall],
):
    blockchain = Chain.get_blockchain_by_name(blockchain)
    txns = strategies_to_transactions(blockchain, avatar_safe_address, strategy_calls)
    txn = multi_or_one(txs=txns, blockchain=blockchain)
    role_method = get_exec_transaction_with_role_method(
        roles_mod_address=roles_mod_address,
        operation=txn.operation,
        role=role,
        to=txn.contract_address,
        value=txn.value,
        data=txn.data,
        should_revert=True,
    )

    return {"txn": TransactableData.from_transactable(role_method)}


@app.post(
    f"/multisend-transactions",
    description="Build one multisend call from multiple Transactables",
)
def multisend_transactions(blockchain: BlockchainOption, txns: list[TransactableData]):
    blockchain = Chain.get_blockchain_by_name(blockchain)
    txn = multi_or_one(txs=txns, blockchain=blockchain)
    return {"txn": dataclasses.asdict(txn)}


def generate_strategy_endpoints():
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
            url = f"/txns/{kind}/{protocol}/{strategy_name}"

            # @app.get(url)
            @app.post(url, description=strategy.__doc__)
            def transaction_data(
                blockchain: BlockchainOption,
                avatar_safe_address: ChecksumAddress,
                arguments: arg_type,
            ):
                blockchain = Chain.get_blockchain_by_name(blockchain)
                strategy = STRATEGIES_BY_PROTOCOL_AND_NAME.get(protocol).get(
                    strategy_name
                )
                w3 = get_endpoint_for_blockchain(blockchain)
                ctx = GenericTxContext(w3=w3, avatar_safe_address=avatar_safe_address)
                txns = strategy.get_txns(ctx=ctx, arguments=arguments)

                return {
                    "txns": [TransactableData.from_transactable(txn) for txn in txns]
                }

        make_closure(kind, strategy.protocol, strategy.name, arguments_type)


generate_strategy_endpoints()
