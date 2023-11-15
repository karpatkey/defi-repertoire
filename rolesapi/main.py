import enum
import os
from typing import Type, get_type_hints
from fastapi import FastAPI
from roles_royce.toolshed.disassembling import Disassembler, DISASSEMBLERS
from defabipedia.types import Chains
from web3 import Web3


DisassemblyProtocols = enum.StrEnum('DisassemblyProtocols', {name: name for name in DISASSEMBLERS.keys()})
BlockchainOption = enum.StrEnum('BlockchainOption', {name: name for name in Chains.names()})


ENDPOINTS = {
    Chains.Ethereum: [os.getenv("RPC_MAINNET_URL")]
}


def get_endpoint_for_blockchain(blockchain):
    if blockchain == Chains.Ethereum:
        url = ENDPOINTS[blockchain][0]
    else:
        raise NotImplementedError("Not supported blockchain")
    return Web3(Web3.HTTPProvider(url))


def disassembly(blockchain, protocol, exit_strategy, percentage, exit_arguments,
                avatar_safe_address, roles_mod_address, role, signer_address):
    w3 = get_endpoint_for_blockchain(blockchain)
    disassembler_class: Type[Disassembler] = DISASSEMBLERS.get(protocol)
    disassembler = disassembler_class(w3=w3,
                                      avatar_safe_address=avatar_safe_address,
                                      roles_mod_address=roles_mod_address,
                                      role=role,
                                      signer_address=signer_address)
    exit_strategy = getattr(disassembler, exit_strategy)
    txn_transactables = exit_strategy(percentage=percentage, exit_arguments=exit_arguments)
    return [txn.data for txn in txn_transactables]


app = FastAPI()


@app.get("/")
async def root():
    return {"message": "Roles API"}


@app.get("/status")
async def status():
    return {"message": "Ok"}


for protocol in DisassemblyProtocols:
    disassembly_class = DISASSEMBLERS[protocol]
    exit_function_names = [e for e in dir(disassembly_class) if e.startswith("exit_")]
    for exit_function_name in exit_function_names:
        exit_function = getattr(disassembly_class, exit_function_name)
        exit_arguments_type = get_type_hints(exit_function)['exit_arguments']

        def make_closure(proto, exit_fun_name, exit_arg_type):
            # As exit arguments is a custom type (a dict) and FastAPI does not support complex types
            # in the querystring (https://github.com/tiangolo/fastapi/discussions/7919)
            # We have mainly two options:
            #  1) Use a json string in the querystring, but we will not have the schema documentation and validation.
            #  2) Use a request body. As GET requests body are not supported in all the languages, then we also let POST for the endpoint
            #     even if the semantic is of a GET.
            #  3) Just use POST.
            #
            # For the time being the option 3) is implemented
            url = f"/txn_data/disassembly/{proto}/{exit_fun_name}/"
            # @app.get(url)
            @app.post(url)
            def transaction_data(blockchain: BlockchainOption, roles_mod_address: str, role: int, signer_address: str,
                                 avatar_safe_address: str,
                                 percentage: float,
                                 exit_arguments: exit_arg_type):
                blockchain = Chains.get_blockchain_by_name(blockchain)
                transactables = disassembly(blockchain=blockchain, protocol=proto, roles_mod_address=roles_mod_address,
                                            role=role, signer_address=signer_address, avatar_safe_address=avatar_safe_address,
                                            exit_strategy=exit_fun_name, exit_arguments=exit_arguments, percentage=percentage
                                            )
                return {"data": transactables}

        make_closure(protocol, exit_function_name, exit_arguments_type)
