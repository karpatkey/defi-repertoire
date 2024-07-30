from decimal import Decimal

from defabipedia.maker import Abis, ContractSpecs
from defabipedia.types import Chain
from pytest import approx
from roles_royce import roles
from roles_royce.constants import ETHAddr
from roles_royce.protocols.eth import maker
from roles_royce.toolshed.disassembling import DSRDisassembler
from roles_royce.utils import to_checksum_address

from defi_repertoire.strategies.base import GenericTxContext
from defi_repertoire.strategies.disassembling import disassembling_dsr as dsr
from defi_repertoire.strategies.disassembling.disassembler import Disassembler
from tests.fork_fixtures import accounts
from tests.fork_fixtures import local_node_eth_replay as local_node_eth
from tests.roles import apply_presets, deploy_roles, setup_common_roles
from tests.utils import create_simple_safe, get_balance, steal_token, top_up_address


def test_integration_exit_1(local_node_eth, accounts):
    w3 = local_node_eth.w3
    block = 19917381
    local_node_eth.set_block(block)

    avatar_safe = create_simple_safe(w3=w3, owner=accounts[0])
    roles_contract = deploy_roles(avatar=avatar_safe.address, w3=w3)
    setup_common_roles(avatar_safe, roles_contract)

    # Build proxy
    build_receipt = avatar_safe.send([maker.Build()]).receipt
    for log in build_receipt["logs"]:
        if (
            log["topics"][0].hex()
            == "0x259b30ca39885c6d801a0b5dbc988640f3c25e2f37531fe138c5c5af8955d41b"
        ):  # Created
            proxy_address = to_checksum_address("0x" + log["data"].hex()[26:66])
            break

    presets = """{"version": "1.0","chainId": "1","meta":{ "description": "","txBuilderVersion": "1.8.0"},"createdAt": 1695904723785,"transactions": [
        {"to": "0x1ffAdc16726dd4F91fF275b4bF50651801B06a86",
        "data": "0x5e82669500000000000000000000000000000000000000000000000000000000000000040000000000000000000000006b175474e89094c44da98b954eedeac495271d0f",
        "value": "0"},
        {"to": "0x1ffAdc16726dd4F91fF275b4bF50651801B06a86",
        "data": "0x2fcf52d100000000000000000000000000000000000000000000000000000000000000040000000000000000000000006b175474e89094c44da98b954eedeac495271d0f095ea7b3000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000",
        "value": "0"},
        {"to": "0x1ffAdc16726dd4F91fF275b4bF50651801B06a86",
        "data": "0x5e8266950000000000000000000000000000000000000000000000000000000000000004000000000000000000000000d758500ddec05172aaa035911387c8e0e789cf6a",
        "value": "0"},
        {"to": "0x1ffAdc16726dd4F91fF275b4bF50651801B06a86",
        "data": "0x2fcf52d10000000000000000000000000000000000000000000000000000000000000004000000000000000000000000d758500ddec05172aaa035911387c8e0e789cf6a1cff79cd000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000",
        "value": "0"}
    ]}"""

    apply_presets(
        avatar_safe,
        roles_contract,
        json_data=presets,
        replaces=[
            ("c01318bab7ee1f5ba734172bf7718b5dc6ec90e1", avatar_safe.address[2:]),
            ("d758500ddec05172aaa035911387c8e0e789cf6a", proxy_address[2:]),
        ],
    )

    # steal DAI
    steal_token(
        w3,
        token=ETHAddr.DAI,
        holder="0x60FaAe176336dAb62e284Fe19B885B095d29fB7F",
        to=avatar_safe.address,
        amount=100_000_000_000_000_000_000,
    )

    pot_contract = ContractSpecs[Chain.ETHEREUM].Pot.contract(w3)

    avatar_safe_address = avatar_safe.address
    disassembler_address = accounts[4].address
    private_key = accounts[4].key
    role = 4

    # approve DAI
    approve_dai = maker.ApproveDAI(
        spender=proxy_address, amount=100_000_000_000_000_000_000
    )
    roles.send(
        [approve_dai],
        role=4,
        private_key=accounts[4].key,
        roles_mod_address=roles_contract.address,
        web3=w3,
    )
    join_dai = maker.ProxyActionJoinDsr(
        proxy=proxy_address, wad=100_000_000_000_000_000_000
    )
    roles.send(
        [join_dai],
        role=4,
        private_key=accounts[4].key,
        roles_mod_address=roles_contract.address,
        web3=w3,
    )
    pie = pot_contract.functions.pie(proxy_address).call()
    chi = pot_contract.functions.chi().call() / (10**27)
    assert pie * chi == approx(100_000_000_000_000_000_000)

    ctx = GenericTxContext(w3=w3, avatar_safe_address=avatar_safe.address)
    disassembler_instance = Disassembler()

    txn_transactable = dsr.WithdrawWithProxy.get_txns(
        ctx=ctx,
        arguments=dsr.StrategyAmountArguments(
            amount=int(Decimal(100_000_000_000_000_000_000) / Decimal(2)),
        ),
    )

    disassembler_instance.send(
        ctx=ctx,
        roles_mod_address=roles_contract.address,
        role=role,
        txns=txn_transactable,
        private_key=private_key,
    )

    pie = pot_contract.functions.pie(proxy_address).call()
    chi = pot_contract.functions.chi().call() / (10**27)
    assert pie * chi == approx(50_000_000_000_000_000_000)


def test_integration_exit_2(local_node_eth, accounts):
    w3 = local_node_eth.w3
    block = 19917381
    local_node_eth.set_block(block)

    avatar_safe = create_simple_safe(w3=w3, owner=accounts[0])
    roles_contract = deploy_roles(avatar=avatar_safe.address, w3=w3)
    setup_common_roles(avatar_safe, roles_contract)

    presets = """{"version": "1.0","chainId": "1","meta":{ "description": "","txBuilderVersion": "1.8.0"},"createdAt": 1695904723785,"transactions": [
        {"to": "0x1ffAdc16726dd4F91fF275b4bF50651801B06a86",
        "data": "0x5e82669500000000000000000000000000000000000000000000000000000000000000040000000000000000000000006b175474e89094c44da98b954eedeac495271d0f",
        "value": "0"},
        {"to": "0x1ffAdc16726dd4F91fF275b4bF50651801B06a86",
        "data": "0x33a0480c00000000000000000000000000000000000000000000000000000000000000040000000000000000000000006b175474e89094c44da98b954eedeac495271d0f095ea7b30000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000001000000000000000000000000000000000000000000000000000000000000000140000000000000000000000000000000000000000000000000000000000000018000000000000000000000000000000000000000000000000000000000000001c00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000100000000000000000000000000000000000000000000000000000000000000010000000000000000000000000000000000000000000000000000000000000001000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000010000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000100000000000000000000000000000000000000000000000000000000000000200000000000000000000000000000000000000000000000000000000000000020000000000000000000000000373238337bfe1146fb49989fc222523f83081ddb",
        "value": "0"},
        {"to": "0x1ffAdc16726dd4F91fF275b4bF50651801B06a86",
        "data": "0x5e8266950000000000000000000000000000000000000000000000000000000000000004000000000000000000000000373238337bfe1146fb49989fc222523f83081ddb",
        "value": "0"},
        {"to": "0x1ffAdc16726dd4F91fF275b4bF50651801B06a86",
        "data": "0x33a0480c0000000000000000000000000000000000000000000000000000000000000004000000000000000000000000373238337bfe1146fb49989fc222523f83081ddb3b4da69f0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000001000000000000000000000000000000000000000000000000000000000000000140000000000000000000000000000000000000000000000000000000000000018000000000000000000000000000000000000000000000000000000000000001c00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000100000000000000000000000000000000000000000000000000000000000000010000000000000000000000000000000000000000000000000000000000000001000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000010000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000100000000000000000000000000000000000000000000000000000000000000200000000000000000000000000000000000000000000000000000000000000020000000000000000000000000c01318bab7ee1f5ba734172bf7718b5dc6ec90e1",
        "value": "0"},
        {"to": "0x1ffAdc16726dd4F91fF275b4bF50651801B06a86",
        "data": "0x33a0480c0000000000000000000000000000000000000000000000000000000000000004000000000000000000000000373238337bfe1146fb49989fc222523f83081ddbef693bed0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000001000000000000000000000000000000000000000000000000000000000000000140000000000000000000000000000000000000000000000000000000000000018000000000000000000000000000000000000000000000000000000000000001c00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000100000000000000000000000000000000000000000000000000000000000000010000000000000000000000000000000000000000000000000000000000000001000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000010000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000100000000000000000000000000000000000000000000000000000000000000200000000000000000000000000000000000000000000000000000000000000020000000000000000000000000c01318bab7ee1f5ba734172bf7718b5dc6ec90e1",
        "value": "0"},
        {"to": "0x1ffAdc16726dd4F91fF275b4bF50651801B06a86",
        "data": "0x33a0480c0000000000000000000000000000000000000000000000000000000000000004000000000000000000000000373238337bfe1146fb49989fc222523f83081ddbeb0dff660000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000001000000000000000000000000000000000000000000000000000000000000000140000000000000000000000000000000000000000000000000000000000000018000000000000000000000000000000000000000000000000000000000000001c00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000100000000000000000000000000000000000000000000000000000000000000010000000000000000000000000000000000000000000000000000000000000001000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000010000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000100000000000000000000000000000000000000000000000000000000000000200000000000000000000000000000000000000000000000000000000000000020000000000000000000000000c01318bab7ee1f5ba734172bf7718b5dc6ec90e1",
        "value": "0"}
    ]}"""

    apply_presets(
        avatar_safe,
        roles_contract,
        json_data=presets,
        replaces=[
            ("c01318bab7ee1f5ba734172bf7718b5dc6ec90e1", avatar_safe.address[2:])
        ],
    )

    steal_token(
        w3,
        token=ETHAddr.DAI,
        holder="0x60FaAe176336dAb62e284Fe19B885B095d29fB7F",
        to=avatar_safe.address,
        amount=100_000_000_000_000_000_000,
    )
    dsr_manager_contract = ContractSpecs[Chain.ETHEREUM].DsrManager.contract(w3)
    pot_contract = ContractSpecs[Chain.ETHEREUM].Pot.contract(w3)

    avatar_safe_address = avatar_safe.address
    disassembler_address = accounts[4].address
    private_key = accounts[4].key
    role = 4

    # approve DAI
    approve_dai = maker.ApproveDAI(
        spender=ContractSpecs[Chain.ETHEREUM].DsrManager.address,
        amount=100_000_000_000_000_000_000,
    )
    roles.send(
        [approve_dai],
        role=4,
        private_key=accounts[4].key,
        roles_mod_address=roles_contract.address,
        web3=w3,
    )
    join_dai = maker.JoinDsr(
        avatar=avatar_safe_address, wad=100_000_000_000_000_000_000
    )
    roles.send(
        [join_dai],
        role=4,
        private_key=accounts[4].key,
        roles_mod_address=roles_contract.address,
        web3=w3,
    )
    pie = dsr_manager_contract.functions.pieOf(avatar_safe_address).call()
    chi = pot_contract.functions.chi().call() / (10**27)
    assert pie * chi == approx(100_000_000_000_000_000_000)

    ctx = GenericTxContext(w3=w3, avatar_safe_address=avatar_safe.address)
    disassembler_instance = Disassembler()

    txn_transactable = dsr.WithdrawWithoutProxy.get_txns(
        ctx=ctx,
        arguments=dsr.StrategyAmountArguments(
            amount=int(Decimal(100_000_000_000_000_000_000) / Decimal(2)),
        ),
    )

    disassembler_instance.send(
        ctx=ctx,
        roles_mod_address=roles_contract.address,
        role=role,
        txns=txn_transactable,
        private_key=private_key,
    )

    pie = dsr_manager_contract.functions.pieOf(avatar_safe_address).call()
    chi = pot_contract.functions.chi().call() / (10**27)
    assert pie * chi == approx(50_000_000_000_000_000_000)
