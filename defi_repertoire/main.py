import enum
import os
from typing import Type, get_type_hints
from fastapi import FastAPI
from .disassembling import Disassembler, DISASSEMBLERS
from defabipedia.types import Chain, Blockchain
from web3 import Web3

FAKE_ADDRESS = "0x0000000000000000000000000000000000000000"

DisassemblyProtocols = enum.StrEnum('DisassemblyProtocols', {name: name for name in DISASSEMBLERS.keys()})
BlockchainOption = enum.StrEnum('BlockchainOption', {name: name for name in Chain._by_name.values()})

ENDPOINTS = {
    Chain.ETHEREUM: [os.getenv("RPC_MAINNET_URL")]
}


def get_endpoint_for_blockchain(blockchain: Blockchain):
    if blockchain == Chain.ETHEREUM:
        url = ENDPOINTS[blockchain][0]
    else:
        raise NotImplementedError("Blockchain not supported.")
    return Web3(Web3.HTTPProvider(url))


def disassembly(blockchain: Blockchain,
                protocol,
                exit_strategy,
                arguments: dict,
                avatar_safe_address,
                percentage,
                amount_to_redeem):
    w3 = get_endpoint_for_blockchain(blockchain)
    disassembler_class: Type[Disassembler] = DISASSEMBLERS.get(protocol)

    disassembler = disassembler_class(w3=w3,
                                      avatar_safe_address=avatar_safe_address,
                                      roles_mod_address=FAKE_ADDRESS,
                                      role=0,
                                      signer_address=FAKE_ADDRESS)
    exit_strategy = getattr(disassembler, exit_strategy)
    txn_transactables = exit_strategy(percentage=percentage,
                                      exit_arguments=arguments,
                                      amount_to_redeem=amount_to_redeem)
    return [txn.data for txn in txn_transactables]


app = FastAPI()


@app.get("/")
async def root():
    return {"message": "DeFi Repertoire API"}


@app.get("/status")
async def status():
    return {"message": "Ok"}


for protocol in DisassemblyProtocols:
    disassembly_class = DISASSEMBLERS[protocol]
    functions = []
    for attr_name in dir(disassembly_class):
        attr = getattr(disassembly_class, attr_name)
        if callable(attr) and not attr_name.startswith("_") and "exit_arguments" in get_type_hints(attr):
            functions.append((attr_name, attr))

    for function_name, function in functions:
        arguments_type = get_type_hints(function)["exit_arguments"]


        def make_closure(protocol, function_name, arg_type):
            # As exit arguments is a custom type (a dict) and FastAPI does not support complex types
            # in the querystring (https://github.com/tiangolo/fastapi/discussions/7919)
            # We have mainly two options:
            #  1) Use a json string in the querystring, but we will not have the schema documentation and validation.
            #  2) Use a request body. As GET requests body are not supported in all the languages, then we also let POST for the endpoint
            #     even if the semantic is of a GET.
            #  3) Just use POST.
            #
            # For the time being the option 3) is implemented
            url = f"/txn_data/disassembly/{protocol}/{function_name}/"

            # @app.get(url)
            @app.post(url)
            def transaction_data(blockchain: BlockchainOption,
                                 avatar_safe_address: str,
                                 percentage: float,
                                 exit_arguments: arg_type,
                                 amount_to_redeem: int | None = None):
                blockchain = Chain.get_blockchain_by_name(blockchain)
                transactables = disassembly(blockchain=blockchain,
                                            protocol=protocol,
                                            avatar_safe_address=avatar_safe_address,
                                            exit_strategy=function_name,
                                            arguments=exit_arguments,
                                            percentage=percentage,
                                            amount_to_redeem=amount_to_redeem,
                                            )
                return {"data": transactables}


        make_closure(protocol, function_name, arguments_type)
