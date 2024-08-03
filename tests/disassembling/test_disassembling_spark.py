import json
from decimal import Decimal

from defabipedia.spark import ContractSpecs
from defabipedia.types import Chain
from karpatkit.test_utils.fork import (
    accounts,
    create_simple_safe,
    local_node_eth,
    steal_token,
)
from roles_royce.constants import ETHAddr
from roles_royce.protocols.eth import spark as rr_spark
from roles_royce.toolshed.protocol_utils.spark.utils import SparkUtils
from roles_royce.toolshed.test_utils.roles_fork_utils import (
    apply_roles_presets,
    deploy_roles,
    setup_common_roles,
)

from defi_repertoire.strategies.base import GenericTxContext
from defi_repertoire.strategies.disassembling import disassembling_spark as spark
from defi_repertoire.strategies.disassembling.disassembler import Disassembler


def test_integration_1(local_node_eth, accounts):
    w3 = local_node_eth.w3
    block = 19917381
    local_node_eth.set_block(block)

    avatar_safe = create_simple_safe(w3=w3, owner=accounts[0])
    roles_contract = deploy_roles(avatar=avatar_safe.address, w3=w3)
    setup_common_roles(avatar_safe, roles_contract)
    blockchain = Chain.get_blockchain_from_web3(w3)
    presets = """{"version": "1.0","chainId": "1","meta":{ "description": "","txBuilderVersion": "1.8.0"},"createdAt": 1695904723785,"transactions": [
        {"to": "0x1ffAdc16726dd4F91fF275b4bF50651801B06a86",
        "data": "0x5e826695000000000000000000000000000000000000000000000000000000000000000400000000000000000000000083F20F44975D03b1b09e64809B757c47f942BEeA",
        "value": "0"},
        {"to": "0x1ffAdc16726dd4F91fF275b4bF50651801B06a86",
        "data": "0x2fcf52d1000000000000000000000000000000000000000000000000000000000000000400000000000000000000000083F20F44975D03b1b09e64809B757c47f942BEeAba087652000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000",
        "value": "0"}
    ]}"""

    apply_roles_presets(
        avatar_safe,
        roles_contract,
        json_data=presets,
        replaces=[
            ("c01318bab7ee1f5ba734172bf7718b5dc6ec90e1", avatar_safe.address[2:])
        ],
    )
    DAIER = "0xfE9fE2eF61faF6E291b06903dFf85DF25a989498"
    steal_token(w3, ETHAddr.DAI, holder=DAIER, to=avatar_safe.address, amount=1_000)
    # Deposit DAI, get sDAI
    avatar_safe.send(
        [
            rr_spark.ApproveDAIforSDAI(amount=1_000),
            rr_spark.DepositDAIforSDAI(
                blockchain=blockchain, amount=1_000, avatar=avatar_safe.address
            ),
        ]
    )

    sdai_contract = ContractSpecs[blockchain].sDAI.contract(w3)
    chi = SparkUtils.get_chi(w3)
    assert sdai_contract.functions.balanceOf(avatar_safe.address).call() == int(
        Decimal(1_000) / (Decimal(chi) / Decimal(1e27))
    )  # 976

    private_key = accounts[4].key
    role = 4

    ctx = GenericTxContext(w3=w3, avatar_safe_address=avatar_safe.address)
    disassembler_instance = Disassembler()

    txn_transactable = spark.WithdrawWithProxy.get_txns(
        ctx=ctx,
        arguments=spark.StrategyAmountArguments(amount=int(Decimal(976) / Decimal(2))),
    )

    disassembler_instance.send(
        ctx=ctx,
        roles_mod_address=roles_contract.address,
        role=role,
        txns=txn_transactable,
        private_key=private_key,
    )

    assert sdai_contract.functions.balanceOf(avatar_safe.address).call() == 434
