from collections import defaultdict
import enum
import os
from typing import get_type_hints
from fastapi import FastAPI
from defi_repertoire.strategies.base import GenericTxContext, STRATEGIES
from defi_repertoire.strategies import disassembling, swaps
from defabipedia.types import Chain, Blockchain
from web3 import Web3

Protocols = enum.StrEnum('Protocols', {s.protocol: s.protocol for s in STRATEGIES})
StrategyKinds = enum.StrEnum('StrategyKinds', {s.kind: s.kind for s in STRATEGIES})
BlockchainOption = enum.StrEnum('BlockchainOption', {name: name for name in Chain._by_name.values()})

ENDPOINTS = {
    Chain.ETHEREUM: [os.getenv("RPC_MAINNET_URL")]
}

REGISTERED_OPS = defaultdict(dict)


def get_endpoint_for_blockchain(blockchain: Blockchain):
    if blockchain == Chain.ETHEREUM:
        url = ENDPOINTS[blockchain][0]
    else:
        raise NotImplementedError("Blockchain not supported.")
    return Web3(Web3.HTTPProvider(url))


def get_transactables(blockchain: Blockchain,
                      protocol,
                      op_name,
                      arguments: dict,
                      avatar_safe_address):
    w3 = get_endpoint_for_blockchain(blockchain)
    op = REGISTERED_OPS.get(protocol).get(op_name)
    ctx = GenericTxContext(w3=w3, avatar_safe_address=avatar_safe_address)
    txns = op.get_txns(ctx=ctx,
                       arguments=arguments)

    return [txn.data for txn in txns]


app = FastAPI()


@app.get("/")
async def root():
    return {"message": "DeFi Repertoire API"}


@app.get("/status")
async def status():
    return {"message": "Ok"}


for strategy in STRATEGIES:
    function = strategy.get_txns
    function_name = str.lower(strategy.__name__)
    protocol = strategy.protocol
    kind = strategy.kind
    REGISTERED_OPS[protocol][function_name] = strategy

    arguments_type = get_type_hints(function)["arguments"]

    def make_closure(kind, protocol, function_name, arg_type):
        # As exit arguments is a custom type (a dict) and FastAPI does not support complex types
        # in the querystring (https://github.com/tiangolo/fastapi/discussions/7919)
        # We have mainly two options:
        #  1) Use a json string in the querystring, but we will not have the schema documentation and validation.
        #  2) Use a request body. As GET requests body are not supported in all the languages, then we also let POST for the endpoint
        #     even if the semantic is of a GET.
        #  3) Just use POST.
        #
        # For the time being the option 3) is implemented
        url = f"/txn_data/{kind}/{protocol}/{function_name}/"

        # @app.get(url)
        @app.post(url)
        def transaction_data(blockchain: BlockchainOption,
                             avatar_safe_address: str,
                             arguments: arg_type):
            blockchain = Chain.get_blockchain_by_name(blockchain)
            transactables = get_transactables(blockchain=blockchain,
                                              protocol=protocol,
                                              avatar_safe_address=avatar_safe_address,
                                              op_name=function_name,
                                              arguments=arguments,
                                              )
            return {"data": transactables}

    make_closure(kind, protocol, function_name, arguments_type)
