import asyncio
import enum
import json
import os
from collections import defaultdict

from defabipedia.types import Blockchain, Chain
from fastapi import FastAPI
from pydantic import BaseModel, field_serializer
from roles_royce.generic_method import Operation
from roles_royce.protocols import ContractMethod
from roles_royce.protocols.roles_modifier.contract_methods import (
    get_exec_transaction_with_role_method,
)
from roles_royce.utils import multi_or_one
from web3 import Web3

from defi_repertoire.strategies import disassembling, swapping
from defi_repertoire.strategies.base import (
    STRATEGIES,
    ChecksumAddress,
    GenericTxContext,
    get_strategy_arguments_type,
    strategy_as_dict,
)

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


class DecodeNode(BaseModel):
    txn: TransactableData
    decoded: dict
    children: list["DecodeNode"] | None

    @field_serializer("decoded")
    def serialize_decoded(self, decoded: dict, _info):
        # Inefficient way to use the Web3 json normalizers
        return json.loads(Web3.to_json(decoded))

    @classmethod
    def from_contract_method(
        cls, method: ContractMethod, children: list["DecodeNode"] | None
    ) -> "DecodeNode":
        txn = TransactableData.from_transactable(method)
        decoded = {"name": method.name, "inputs": method.inputs}
        return DecodeNode(txn=txn, decoded=decoded, children=children)


def get_endpoint_for_blockchain(blockchain: Blockchain):
    if blockchain == Chain.ETHEREUM:
        url = ENDPOINTS[blockchain][0]
    else:
        raise NotImplementedError("Blockchain not supported.")
    return Web3(Web3.HTTPProvider(url))


def strategies_to_contract_methods(
    blockchain: Blockchain,
    avatar_safe_address: ChecksumAddress,
    strategy_calls: list[StrategyCall],
) -> list[ContractMethod]:
    w3 = get_endpoint_for_blockchain(blockchain)
    ctx = GenericTxContext(w3=w3, avatar_safe_address=avatar_safe_address)
    txns = []
    for call in strategy_calls:
        strategy = STRATEGIES[call.id]
        arguments = get_strategy_arguments_type(strategy)(**call.arguments)
        strategy_txns = strategy.get_txns(ctx=ctx, arguments=arguments)
        for txn in strategy_txns:
            txns.append(txn)
    return txns


app = FastAPI()


@app.get("/")
async def root():
    return {"message": "DeFi Repertoire API"}


@app.get("/status")
async def status():
    return {"message": "Ok"}


@app.get("/strategies/{blockchain}")
async def list_strategies(blockchain: BlockchainOption):
    coroutines = [strategy_as_dict(blockchain, s) for s in STRATEGIES.values()]
    strategies = await asyncio.gather(*coroutines)
    return {"strategies": list(filter(lambda v: v is not None, strategies))}


@app.post(f"/strategies-to-transactions")
def strategy_transactions(
    blockchain: BlockchainOption,
    avatar_safe_address: ChecksumAddress,
    strategy_calls: list[StrategyCall],
    multisend: bool = False,
):
    blockchain = Chain.get_blockchain_by_name(blockchain)
    txns = strategies_to_contract_methods(
        blockchain, avatar_safe_address, strategy_calls
    )
    if multisend:
        txns = [multi_or_one(txs=txns, blockchain=blockchain)]

    return {"txns": [TransactableData.from_transactable(txn) for txn in txns]}


@app.post(f"/strategies-to-exec-with-role")
def strategies_to_exec_with_role(
    blockchain: BlockchainOption,
    avatar_safe_address: ChecksumAddress,
    roles_mod_address: ChecksumAddress,
    role: int | str,
    strategy_calls: list[StrategyCall],
):
    blockchain = Chain.get_blockchain_by_name(blockchain)

    # strategy methods layer
    strategy_methods = strategies_to_contract_methods(
        blockchain, avatar_safe_address, strategy_calls
    )
    strategy_decode_nodes = [
        DecodeNode.from_contract_method(method, children=None)
        for method in strategy_methods
    ]

    # multisend layer
    multisend_method = multi_or_one(txs=strategy_methods, blockchain=blockchain)
    multisend_txn = TransactableData.from_transactable(multisend_method)
    multisend_decode_node = DecodeNode.from_contract_method(
        multisend_method, children=strategy_decode_nodes
    )

    # role layer
    role_method = get_exec_transaction_with_role_method(
        roles_mod_address=roles_mod_address,
        operation=multisend_txn.operation,
        role=role,
        to=multisend_txn.contract_address,
        value=multisend_txn.value,
        data=multisend_txn.data,
        should_revert=True,
    )
    role_txn = TransactableData.from_transactable(role_method)
    # build the decode tree
    role_txn_decode_tree = DecodeNode.from_contract_method(
        role_method, children=[multisend_decode_node]
    )
    return {"txn": role_txn, "decoded": role_txn_decode_tree}


@app.post(
    f"/multisend-transactions",
    description="Build one multisend call from multiple TransactableData",
)
def multisend_transactions(blockchain: BlockchainOption, txns: list[TransactableData]):
    blockchain = Chain.get_blockchain_by_name(blockchain)
    txn = multi_or_one(txs=txns, blockchain=blockchain)
    return {"txn": TransactableData.from_transactable(txn)}


def generate_strategy_endpoints():
    # Endpoints for each strategy
    for strategy_id, strategy in STRATEGIES.items():

        def make_closure(id, arg_type):
            # As exit arguments is a custom type (a dict) and FastAPI does not support complex types
            # in the querystring (https://github.com/tiangolo/fastapi/discussions/7919)
            # We have mainly two options:
            #  1) Use a json string in the querystring, but we will not have the schema documentation and validation.
            #  2) Use a request body. As GET requests body are not supported in all the languages, then we also let POST for the endpoint
            #     even if the semantic is of a GET.
            #  3) Just use POST.
            #
            # For the time being the option 3) is implemented
            url = f"/txns/{id}"

            @app.post(url, description=strategy.__doc__)
            def transaction_data(
                blockchain: BlockchainOption,
                avatar_safe_address: ChecksumAddress,
                arguments: arg_type,
            ):
                blockchain = Chain.get_blockchain_by_name(blockchain)
                strategy = STRATEGIES.get(id)
                if not strategy:
                    raise ValueError("Strategy not found")
                w3 = get_endpoint_for_blockchain(blockchain)
                ctx = GenericTxContext(w3=w3, avatar_safe_address=avatar_safe_address)
                txns = strategy.get_txns(ctx=ctx, arguments=arguments)

                return {
                    "txns": [TransactableData.from_transactable(txn) for txn in txns]
                }

            @app.post(url + "/options", description=strategy.__doc__)
            def transaction_options(
                blockchain: BlockchainOption,
                arguments: arg_type,
            ):
                blockchain = Chain.get_blockchain_by_name(blockchain)
                strategy = STRATEGIES.get(id)
                if not strategy:
                    raise ValueError("Strategy not found")
                if not hasattr(strategy, "get_options"):
                    return {"options": {}}
                else:
                    options = strategy.get_options(
                        blockchain=blockchain, arguments=arguments
                    )

                    return {"options": options}

        make_closure(strategy_id, get_strategy_arguments_type(strategy))


generate_strategy_endpoints()
