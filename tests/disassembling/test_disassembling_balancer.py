from decimal import Decimal

import pytest
from defabipedia.balancer import Abis
from defabipedia.tokens import EthereumTokenAddr as EthTokAdd
from defabipedia.tokens import erc20_contract
from defabipedia.types import Chain
from karpatkit.test_utils.fork import (
    accounts,
    create_simple_safe,
    local_node_eth,
    steal_token,
)
from pytest import approx
from roles_royce.roles_modifier import GasStrategies, set_gas_strategy
from roles_royce.toolshed.test_utils.roles_fork_utils import (
    apply_roles_presets,
    deploy_roles,
    setup_common_roles,
)

from defi_repertoire.strategies.base import GenericTxContext
from defi_repertoire.strategies.disassembling import disassembling_balancer as balancer
from defi_repertoire.strategies.disassembling.disassembler import Disassembler

# Preset with the permission to call the exit() function in the Balancer vault (the avatar address is
# 0xc01318bab7ee1f5ba734172bf7718b5dc6ec90e1)
preset = (
    '{"version":"1.0","chainId":"1","meta":{"name":null,"description":"","txBuilderVersion":"1.8.0"},'
    '"createdAt":1695826823729,"transactions":[{"to":"0x1ffAdc16726dd4F91fF275b4bF50651801B06a86",'
    '"data":"0x5e8266950000000000000000000000000000000000000000000000000000000000000001000000000000000000000000ba12222222228d8ba445958a75a0704d566bf2c8","value":"0"},{"to":"0x1ffAdc16726dd4F91fF275b4bF50651801B06a86","data":"0x33a0480c0000000000000000000000000000000000000000000000000000000000000001000000000000000000000000ba12222222228d8ba445958a75a0704d566bf2c88bdb3913000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000100000000000000000000000000000000000000000000000000000000000000018000000000000000000000000000000000000000000000000000000000000002000000000000000000000000000000000000000000000000000000000000000280000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000030000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000100000000000000000000000000000000000000000000000000000000000000010000000000000000000000000000000000000000000000000000000000000003000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000300000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000030000000000000000000000000000000000000000000000000000000000000060000000000000000000000000000000000000000000000000000000000000008000000000000000000000000000000000000000000000000000000000000000c000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000020000000000000000000000000c01318bab7ee1f5ba734172bf7718b5dc6ec90e10000000000000000000000000000000000000000000000000000000000000020000000000000000000000000c01318bab7ee1f5ba734172bf7718b5dc6ec90e1","value":"0"}]}'
)


# @pytest.mark.skip("Not working yet")
def test_integration_proportional(local_node_eth, accounts):
    w3 = local_node_eth.w3
    block = 18421437
    local_node_eth.set_block(block)

    avatar_safe = create_simple_safe(w3=w3, owner=accounts[0])
    roles_contract = deploy_roles(avatar=avatar_safe.address, w3=w3)
    setup_common_roles(avatar_safe, roles_contract)

    apply_roles_presets(
        avatar_safe,
        roles_contract,
        json_data=preset,
        replaces=[
            ("c01318bab7ee1f5ba734172bf7718b5dc6ec90e1", avatar_safe.address[2:])
        ],
    )

    blockchain = Chain.get_blockchain_from_web3(w3)

    avatar_safe_address = avatar_safe.address
    disassembler_address = accounts[1].address
    private_key = accounts[1].key
    role = 1

    ctx = GenericTxContext(w3=w3, avatar_safe_address=avatar_safe.address)
    disassembler_instance = Disassembler()
    # ----------------------------------------------------------------------------------------------------------------
    # Composable
    GHO_USDT_USDC_bpt_address = "0x8353157092ED8Be69a9DF8F95af097bbF33Cb2aF"
    # Initial data
    bpt_contract = w3.eth.contract(
        address=GHO_USDT_USDC_bpt_address, abi=Abis[blockchain].UniversalBPT.abi
    )
    steal_token(
        w3=w3,
        token=GHO_USDT_USDC_bpt_address,
        holder="0x854B004700885A61107B458f11eCC169A019b764",
        to=avatar_safe.address,
        amount=8_999_999_999_999_000_000,
    )
    bpt_token_balance = bpt_contract.functions.balanceOf(avatar_safe.address).call()
    assert bpt_token_balance == 8_999_999_999_999_000_000

    txn_transactable = balancer.WithdrawAllAssetsProportional.get_txns(
        ctx=ctx,
        arguments=balancer.WithdrawAllAssetsProportional.Args(
            bpt_address=GHO_USDT_USDC_bpt_address,
            max_slippage=0.01,
            amount=int(Decimal(bpt_token_balance) / Decimal(2)),
        ),
    )

    disassembler_instance.send(
        ctx=ctx,
        roles_mod_address=roles_contract.address,
        role=role,
        txns=txn_transactable,
        private_key=private_key,
    )

    bpt_token_balance_after = bpt_contract.functions.balanceOf(
        avatar_safe_address
    ).call()
    assert bpt_token_balance_after == 4499999999999500000
    assert bpt_token_balance_after == int(Decimal(bpt_token_balance) / Decimal(2))

    # ----------------------------------------------------------------------------------------------------------------
    # Metastable
    rETH_WETH_bpt_address = "0x1E19CF2D73a72Ef1332C882F20534B6519Be0276"
    # Initial data
    bpt_contract = w3.eth.contract(
        address=rETH_WETH_bpt_address, abi=Abis[blockchain].UniversalBPT.abi
    )

    steal_token(
        w3=w3,
        token=rETH_WETH_bpt_address,
        holder="0xa7dB55e153C0c71Ff35432a9aBe2A853f886Ce0D",
        to=avatar_safe.address,
        amount=80_999_999,
    )
    bpt_token_balance = bpt_contract.functions.balanceOf(avatar_safe.address).call()
    assert bpt_token_balance == 80_999_999

    txn_transactable = balancer.WithdrawAllAssetsProportional.get_txns(
        ctx=ctx,
        arguments=balancer.WithdrawAllAssetsProportional.Args(
            bpt_address=rETH_WETH_bpt_address,
            max_slippage=1,
            amount=int(Decimal(bpt_token_balance) / Decimal(2)),
        ),
    )

    disassembler_instance.send(
        ctx=ctx,
        roles_mod_address=roles_contract.address,
        role=role,
        txns=txn_transactable,
        private_key=private_key,
    )

    bpt_token_balance_after = bpt_contract.functions.balanceOf(
        avatar_safe_address
    ).call()
    assert bpt_token_balance_after == 40500000 or bpt_token_balance_after == 40499999
    assert bpt_token_balance_after == approx(
        int(Decimal(bpt_token_balance) / Decimal(2))
    )

    # ----------------------------------------------------------------------------------------------------------------
    # Weighted Pool
    BAL_WETH_bpt_address = "0x5c6Ee304399DBdB9C8Ef030aB642B10820DB8F56"
    # Initial data
    bpt_contract = w3.eth.contract(
        address=BAL_WETH_bpt_address, abi=Abis[blockchain].UniversalBPT.abi
    )

    steal_token(
        w3=w3,
        token=BAL_WETH_bpt_address,
        holder="0x6724F3FBb16F542401BfC42C464CE91b6C31001E",
        to=avatar_safe.address,
        amount=80_999_999,
    )
    bpt_token_balance = bpt_contract.functions.balanceOf(avatar_safe.address).call()
    assert bpt_token_balance == 80_999_999

    txn_transactable = balancer.WithdrawAllAssetsProportional.get_txns(
        ctx=ctx,
        arguments=balancer.WithdrawAllAssetsProportional.Args(
            bpt_address=BAL_WETH_bpt_address,
            max_slippage=1,
            amount=int(Decimal(bpt_token_balance) / Decimal(2)),
        ),
    )

    disassembler_instance.send(
        ctx=ctx,
        roles_mod_address=roles_contract.address,
        role=role,
        txns=txn_transactable,
        private_key=private_key,
    )

    bpt_token_balance_after = bpt_contract.functions.balanceOf(
        avatar_safe_address
    ).call()
    assert bpt_token_balance_after == 40500000 or bpt_token_balance_after == 40499999
    assert bpt_token_balance_after == approx(
        int(Decimal(bpt_token_balance) / Decimal(2))
    )

    # ----------------------------------------------------------------------------------------------------------------
    # Stable Pool v1
    DAI_USDC_USDT_bpt_address = "0x06Df3b2bbB68adc8B0e302443692037ED9f91b42"
    # Initial data
    bpt_contract = w3.eth.contract(
        address=DAI_USDC_USDT_bpt_address, abi=Abis[blockchain].UniversalBPT.abi
    )

    steal_token(
        w3=w3,
        token=DAI_USDC_USDT_bpt_address,
        holder="0x21DE646963b5A3bA6D88396D7d68F3A05f44A709",
        to=avatar_safe.address,
        amount=80_999_999,
    )
    bpt_token_balance = bpt_contract.functions.balanceOf(avatar_safe.address).call()
    assert bpt_token_balance == 80_999_999

    txn_transactable = balancer.WithdrawAllAssetsProportional.get_txns(
        ctx=ctx,
        arguments=balancer.WithdrawAllAssetsProportional.Args(
            bpt_address=DAI_USDC_USDT_bpt_address,
            max_slippage=1,
            amount=int(Decimal(bpt_token_balance) / Decimal(2)),
        ),
    )

    disassembler_instance.send(
        ctx=ctx,
        roles_mod_address=roles_contract.address,
        role=role,
        txns=txn_transactable,
        private_key=private_key,
    )

    bpt_token_balance_after = bpt_contract.functions.balanceOf(
        avatar_safe_address
    ).call()
    assert bpt_token_balance_after == 40500000 or bpt_token_balance_after == 40499999
    assert bpt_token_balance_after == approx(
        int(Decimal(bpt_token_balance) / Decimal(2))
    )

    # ----------------------------------------------------------------------------------------------------------------
    # Stable Pool v2
    auraBAL_STABLE_bpt_address = "0x3dd0843A028C86e0b760b1A76929d1C5Ef93a2dd"
    # Initial data
    bpt_contract = w3.eth.contract(
        address=auraBAL_STABLE_bpt_address, abi=Abis[blockchain].UniversalBPT.abi
    )

    steal_token(
        w3=w3,
        token=auraBAL_STABLE_bpt_address,
        holder="0xAAb2670EC34A393F4F13C63469068a82A1210d64",
        to=avatar_safe.address,
        amount=80_999_999,
    )
    bpt_token_balance = bpt_contract.functions.balanceOf(avatar_safe.address).call()
    assert bpt_token_balance == 80_999_999

    txn_transactable = balancer.WithdrawAllAssetsProportional.get_txns(
        ctx=ctx,
        arguments=balancer.WithdrawAllAssetsProportional.Args(
            bpt_address=auraBAL_STABLE_bpt_address,
            max_slippage=1,
            amount=int(Decimal(bpt_token_balance) / Decimal(2)),
        ),
    )

    disassembler_instance.send(
        ctx=ctx,
        roles_mod_address=roles_contract.address,
        role=role,
        txns=txn_transactable,
        private_key=private_key,
    )

    bpt_token_balance_after = bpt_contract.functions.balanceOf(
        avatar_safe_address
    ).call()
    assert bpt_token_balance_after == 40500000 or bpt_token_balance_after == 40499999
    assert bpt_token_balance_after == approx(
        int(Decimal(bpt_token_balance) / Decimal(2))
    )


def test_integration_exit_1_2(local_node_eth, accounts):
    w3 = local_node_eth.w3
    block = 18421437
    local_node_eth.set_block(block)
    avatar_safe = create_simple_safe(w3=w3, owner=accounts[0])
    roles_contract = deploy_roles(avatar=avatar_safe.address, w3=w3)
    setup_common_roles(avatar_safe, roles_contract)

    apply_roles_presets(
        avatar_safe,
        roles_contract,
        json_data=preset,
        replaces=[
            ("c01318bab7ee1f5ba734172bf7718b5dc6ec90e1", avatar_safe.address[2:])
        ],
    )

    blockchain = Chain.get_blockchain_from_web3(w3)

    avatar_safe_address = avatar_safe.address
    disassembler_address = accounts[1].address
    private_key = accounts[1].key
    role = 1

    local_node_eth.unlock_account(disassembler_address)

    ctx = GenericTxContext(w3=w3, avatar_safe_address=avatar_safe.address)
    disassembler_instance = Disassembler()
    # ----------------------------------------------------------------------------------------------------------------
    # Composable
    GHO_USDT_USDC_bpt_address = "0x8353157092ED8Be69a9DF8F95af097bbF33Cb2aF"

    bpt_contract = w3.eth.contract(
        address=GHO_USDT_USDC_bpt_address, abi=Abis[blockchain].UniversalBPT.abi
    )
    steal_token(
        w3=w3,
        token=GHO_USDT_USDC_bpt_address,
        holder="0x854B004700885A61107B458f11eCC169A019b764",
        to=avatar_safe.address,
        amount=8_999_999_999_999_000_000,
    )
    bpt_token_balance = bpt_contract.functions.balanceOf(avatar_safe.address).call()
    assert bpt_token_balance == 8999999999999000000

    USDT_contract = erc20_contract(w3, EthTokAdd.USDT)
    USDT_balance = USDT_contract.functions.balanceOf(avatar_safe_address).call()
    assert USDT_balance == 0

    txn_transactable = balancer.WithdrawSingle.get_txns(
        ctx=ctx,
        arguments=balancer.WithdrawSingle.Args(
            bpt_address=GHO_USDT_USDC_bpt_address,
            token_out_address=EthTokAdd.USDT,
            max_slippage=1,
            amount=int(Decimal(bpt_token_balance) * Decimal(0.7)),
        ),
    )

    disassembler_instance.send(
        ctx=ctx,
        roles_mod_address=roles_contract.address,
        role=role,
        txns=txn_transactable,
        private_key=private_key,
    )

    bpt_token_balance_after = bpt_contract.functions.balanceOf(
        avatar_safe_address
    ).call()
    assert bpt_token_balance_after == 2699999999999700400
    assert bpt_token_balance_after == approx(
        int(Decimal(bpt_token_balance) * Decimal(0.3))
    )

    new_USDT_balance = USDT_contract.functions.balanceOf(avatar_safe_address).call()
    assert new_USDT_balance == 6163899

    # ----------------------------------------------------------------------------------------------------------------
    # Metastable
    rETH_WETH_bpt_address = "0x1E19CF2D73a72Ef1332C882F20534B6519Be0276"
    # Initial data
    bpt_contract = w3.eth.contract(
        address=rETH_WETH_bpt_address, abi=Abis[blockchain].UniversalBPT.abi
    )

    steal_token(
        w3=w3,
        token=rETH_WETH_bpt_address,
        holder="0xa7dB55e153C0c71Ff35432a9aBe2A853f886Ce0D",
        to=avatar_safe.address,
        amount=80_999_999,
    )
    bpt_token_balance = bpt_contract.functions.balanceOf(avatar_safe.address).call()
    assert bpt_token_balance == 80_999_999

    WETH_contract = erc20_contract(w3, EthTokAdd.WETH)
    WETH_balance = WETH_contract.functions.balanceOf(avatar_safe_address).call()
    assert WETH_balance == 0

    txn_transactable = balancer.WithdrawSingle.get_txns(
        ctx=ctx,
        arguments=balancer.WithdrawSingle.Args(
            bpt_address=rETH_WETH_bpt_address,
            token_out_address=EthTokAdd.WETH,
            max_slippage=1,
            amount=int(Decimal(bpt_token_balance) * Decimal(0.7)),
        ),
    )

    disassembler_instance.send(
        ctx=ctx,
        roles_mod_address=roles_contract.address,
        role=role,
        txns=txn_transactable,
        private_key=private_key,
    )

    bpt_token_balance_after = bpt_contract.functions.balanceOf(
        avatar_safe_address
    ).call()
    assert bpt_token_balance_after == approx(
        int(Decimal(bpt_token_balance) * Decimal(0.3))
    )
    new_WETH_balance = WETH_contract.functions.balanceOf(avatar_safe_address).call()
    assert new_WETH_balance == 58177885

    # ----------------------------------------------------------------------------------------------------------------
    # Weighted Pool
    BAL_WETH_bpt_address = "0x5c6Ee304399DBdB9C8Ef030aB642B10820DB8F56"
    # Initial data
    bpt_contract = w3.eth.contract(
        address=BAL_WETH_bpt_address, abi=Abis[blockchain].UniversalBPT.abi
    )

    steal_token(
        w3=w3,
        token=BAL_WETH_bpt_address,
        holder="0x6724F3FBb16F542401BfC42C464CE91b6C31001E",
        to=avatar_safe.address,
        amount=80_999_999_999_999_999_999,
    )
    bpt_token_balance = bpt_contract.functions.balanceOf(avatar_safe.address).call()
    assert bpt_token_balance == 80_999_999_999_999_999_999

    BAL_contract = erc20_contract(w3, EthTokAdd.BAL)
    BAL_balance = BAL_contract.functions.balanceOf(avatar_safe_address).call()
    assert BAL_balance == 0

    txn_transactable = balancer.WithdrawSingle.get_txns(
        ctx=ctx,
        arguments=balancer.WithdrawSingle.Args(
            bpt_address=BAL_WETH_bpt_address,
            token_out_address=EthTokAdd.BAL,
            max_slippage=1,
            amount=int(Decimal(bpt_token_balance) * Decimal(0.7)),
        ),
    )

    disassembler_instance.send(
        ctx=ctx,
        roles_mod_address=roles_contract.address,
        role=role,
        txns=txn_transactable,
        private_key=private_key,
    )

    bpt_token_balance_after = bpt_contract.functions.balanceOf(
        avatar_safe_address
    ).call()

    assert bpt_token_balance_after == approx(
        int(Decimal(bpt_token_balance) * Decimal(0.3))
    )
    new_BAL_balance = BAL_contract.functions.balanceOf(avatar_safe_address).call()
    assert new_BAL_balance == 168107659416775815189

    # ----------------------------------------------------------------------------------------------------------------
    # Stable Pool v1
    DAI_USDC_USDT_bpt_address = "0x06Df3b2bbB68adc8B0e302443692037ED9f91b42"
    # Initial data
    bpt_contract = w3.eth.contract(
        address=DAI_USDC_USDT_bpt_address, abi=Abis[blockchain].UniversalBPT.abi
    )

    steal_token(
        w3=w3,
        token=DAI_USDC_USDT_bpt_address,
        holder="0x21DE646963b5A3bA6D88396D7d68F3A05f44A709",
        to=avatar_safe.address,
        amount=80_999_999,
    )
    bpt_token_balance = bpt_contract.functions.balanceOf(avatar_safe.address).call()
    assert bpt_token_balance == 80_999_999

    DAI_contract = erc20_contract(w3, EthTokAdd.DAI)
    DAI_balance = DAI_contract.functions.balanceOf(avatar_safe_address).call()
    assert DAI_balance == 0

    txn_transactable = balancer.WithdrawSingle.get_txns(
        ctx=ctx,
        arguments=balancer.WithdrawSingle.Args(
            bpt_address=DAI_USDC_USDT_bpt_address,
            token_out_address=EthTokAdd.DAI,
            max_slippage=1,
            amount=int(Decimal(bpt_token_balance) * Decimal(0.7)),
        ),
    )

    disassembler_instance.send(
        ctx=ctx,
        roles_mod_address=roles_contract.address,
        role=role,
        txns=txn_transactable,
        private_key=private_key,
    )

    bpt_token_balance_after = bpt_contract.functions.balanceOf(
        avatar_safe_address
    ).call()

    assert bpt_token_balance_after == approx(
        int(Decimal(bpt_token_balance) * Decimal(0.3))
    )
    new_DAI_balance = DAI_contract.functions.balanceOf(avatar_safe_address).call()
    assert new_DAI_balance == 57917845

    # ----------------------------------------------------------------------------------------------------------------
    # Stable Pool v2
    auraBAL_STABLE_bpt_address = "0x3dd0843A028C86e0b760b1A76929d1C5Ef93a2dd"
    # Initial data
    bpt_contract = w3.eth.contract(
        address=auraBAL_STABLE_bpt_address, abi=Abis[blockchain].UniversalBPT.abi
    )

    steal_token(
        w3=w3,
        token=auraBAL_STABLE_bpt_address,
        holder="0xF89bb80788a728688015765c8F4b75f96a87A5b3",
        to=avatar_safe.address,
        amount=80_999_999,
    )
    bpt_token_balance = bpt_contract.functions.balanceOf(avatar_safe.address).call()
    assert bpt_token_balance == 80_999_999

    AURABAL_contract = erc20_contract(w3, EthTokAdd.AURABAL)
    AURABAL_balance = AURABAL_contract.functions.balanceOf(avatar_safe_address).call()
    assert AURABAL_balance == 0

    txn_transactable = balancer.WithdrawSingle.get_txns(
        ctx=ctx,
        arguments=balancer.WithdrawSingle.Args(
            bpt_address=auraBAL_STABLE_bpt_address,
            token_out_address=EthTokAdd.AURABAL,
            max_slippage=1,
            amount=int(Decimal(bpt_token_balance) * Decimal(0.7)),
        ),
    )

    disassembler_instance.send(
        ctx=ctx,
        roles_mod_address=roles_contract.address,
        role=role,
        txns=txn_transactable,
        private_key=private_key,
    )

    bpt_token_balance_after = bpt_contract.functions.balanceOf(
        avatar_safe_address
    ).call()
    assert bpt_token_balance_after == approx(
        int(Decimal(bpt_token_balance) * Decimal(0.3))
    )
    new_AURABAL_balance = AURABAL_contract.functions.balanceOf(
        avatar_safe_address
    ).call()
    assert new_AURABAL_balance == 58400033


def test_integration_exit_2_1(local_node_eth, accounts):
    w3 = local_node_eth.w3
    block = 18612383
    local_node_eth.set_block(block)
    avatar_safe = create_simple_safe(w3=w3, owner=accounts[0])
    roles_contract = deploy_roles(avatar=avatar_safe.address, w3=w3)
    setup_common_roles(avatar_safe, roles_contract)

    presets = """{"version":"1.0","chainId":"1","meta":{"name":null,"description":"","txBuilderVersion":"1.8.0"},"createdAt":1695826823729,"transactions":
                [{"to":"0x1ffAdc16726dd4F91fF275b4bF50651801B06a86","data":"0x5e8266950000000000000000000000000000000000000000000000000000000000000004000000000000000000000000ba12222222228d8ba445958a75a0704d566bf2c8","value":"0"},
                 {"to":"0x1ffAdc16726dd4F91fF275b4bF50651801B06a86","data":"0x33a0480c0000000000000000000000000000000000000000000000000000000000000004000000000000000000000000ba12222222228d8ba445958a75a0704d566bf2c88bdb391300000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000010000000000000000000000000000000000000000000000000000000000000001800000000000000000000000000000000000000000000000000000000000000200000000000000000000000000000000000000000000000000000000000000028000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000003000000000000000000000000000000000000000000000000000000000000000100000000000000000000000000000000000000000000000000000000000000010000000000000000000000000000000000000000000000000000000000000001000000000000000000000000000000000000000000000000000000000000000300000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000030000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000003000000000000000000000000000000000000000000000000000000000000006000000000000000000000000000000000000000000000000000000000000000a000000000000000000000000000000000000000000000000000000000000000e00000000000000000000000000000000000000000000000000000000000000020ff4ce5aaab5a627bf82f4a571ab1ce94aa365ea60000000000000000000005d90000000000000000000000000000000000000000000000000000000000000020000000000000000000000000c01318bab7ee1f5ba734172bf7718b5dc6ec90e10000000000000000000000000000000000000000000000000000000000000020000000000000000000000000c01318bab7ee1f5ba734172bf7718b5dc6ec90e1","value":"0"},
                 {"to":"0x1ffAdc16726dd4F91fF275b4bF50651801B06a86","data":"0x5e82669500000000000000000000000000000000000000000000000000000000000000040000000000000000000000005c0f23a5c1be65fa710d385814a7fd1bda480b1c","value": "0"},
                 {"to":"0x1ffAdc16726dd4F91fF275b4bF50651801B06a86","data":"0x2fcf52d100000000000000000000000000000000000000000000000000000000000000040000000000000000000000005c0f23a5c1be65fa710d385814a7fd1bda480b1c2e1a7d4d000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000001","value": "0"}]}"""

    apply_roles_presets(
        avatar_safe,
        roles_contract,
        json_data=presets,
        replaces=[
            ("c01318bab7ee1f5ba734172bf7718b5dc6ec90e1", avatar_safe.address[2:]),
            (
                "5c0f23a5c1be65fa710d385814a7fd1bda480b1c",
                "79eF6103A513951a3b25743DB509E267685726B7",
            ),
            (
                "ff4ce5aaab5a627bf82f4a571ab1ce94aa365ea60000000000000000000005d9",
                "1e19cf2d73a72ef1332c882f20534b6519be0276000200000000000000000112",
            ),
        ],
    )

    blockchain = Chain.get_blockchain_from_web3(w3)

    avatar_safe_address = avatar_safe.address
    disassembler_address = accounts[4].address
    private_key = accounts[4].key
    role = 4

    emergency = "0xA29F61256e948F3FB707b4b3B138C5cCb9EF9888"
    ctx = GenericTxContext(w3=w3, avatar_safe_address=avatar_safe.address)
    disassembler_instance = Disassembler()

    RETH_WETH_BPT_gauge = "0x79eF6103A513951a3b25743DB509E267685726B7"
    RETH_WETH_bpt_address = "0x1E19CF2D73a72Ef1332C882F20534B6519Be0276"

    bpt_gauge_contract = w3.eth.contract(
        address=RETH_WETH_BPT_gauge, abi=Abis[blockchain].Gauge.abi
    )
    steal_token(
        w3=w3,
        token=RETH_WETH_BPT_gauge,
        holder="0xa19ed0aE46e89461e56063f1eD268a0dc225745f",
        to=avatar_safe.address,
        amount=4_000_000_000,
    )

    RETH_contract = erc20_contract(w3, EthTokAdd.rETH)
    RETH_balance_before = RETH_contract.functions.balanceOf(avatar_safe_address).call()
    assert RETH_balance_before == 0

    bpt_gauge_balance = bpt_gauge_contract.functions.balanceOf(
        avatar_safe.address
    ).call()
    assert bpt_gauge_balance == 4_000_000_000

    txn_transactable = balancer.UnstakeAndWithdrawProportional.get_txns(
        ctx=ctx,
        arguments=balancer.UnstakeAndWithdrawProportional.Args(
            gauge_address=RETH_WETH_BPT_gauge,
            max_slippage=1,
            amount=int(Decimal(bpt_gauge_balance) / Decimal(2)),
        ),
    )

    set_gas_strategy(GasStrategies.AGGRESIVE)
    disassembler_instance.send(
        ctx=ctx,
        roles_mod_address=roles_contract.address,
        role=role,
        txns=txn_transactable,
        private_key=private_key,
    )

    RETH_balance_after = RETH_contract.functions.balanceOf(avatar_safe_address).call()
    assert RETH_balance_after == 867203606

    bpt_gauge_balance_after = bpt_gauge_contract.functions.balanceOf(
        avatar_safe_address
    ).call()
    assert bpt_gauge_balance_after == int(Decimal(bpt_gauge_balance) / Decimal(2))


def test_integration_exit_2_2(local_node_eth, accounts):
    w3 = local_node_eth.w3
    block = 18612383
    local_node_eth.set_block(block)
    avatar_safe = create_simple_safe(w3=w3, owner=accounts[0])
    roles_contract = deploy_roles(avatar=avatar_safe.address, w3=w3)
    setup_common_roles(avatar_safe, roles_contract)

    presets = """{"version":"1.0","chainId":"1","meta":{"name":null,"description":"","txBuilderVersion":"1.8.0"},"createdAt":1695826823729,"transactions":
                [{"to":"0x1ffAdc16726dd4F91fF275b4bF50651801B06a86","data":"0x5e8266950000000000000000000000000000000000000000000000000000000000000004000000000000000000000000ba12222222228d8ba445958a75a0704d566bf2c8","value":"0"},
                 {"to":"0x1ffAdc16726dd4F91fF275b4bF50651801B06a86","data":"0x33a0480c0000000000000000000000000000000000000000000000000000000000000004000000000000000000000000ba12222222228d8ba445958a75a0704d566bf2c88bdb391300000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000010000000000000000000000000000000000000000000000000000000000000001800000000000000000000000000000000000000000000000000000000000000200000000000000000000000000000000000000000000000000000000000000028000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000003000000000000000000000000000000000000000000000000000000000000000100000000000000000000000000000000000000000000000000000000000000010000000000000000000000000000000000000000000000000000000000000001000000000000000000000000000000000000000000000000000000000000000300000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000030000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000003000000000000000000000000000000000000000000000000000000000000006000000000000000000000000000000000000000000000000000000000000000a000000000000000000000000000000000000000000000000000000000000000e00000000000000000000000000000000000000000000000000000000000000020ff4ce5aaab5a627bf82f4a571ab1ce94aa365ea60000000000000000000005d90000000000000000000000000000000000000000000000000000000000000020000000000000000000000000c01318bab7ee1f5ba734172bf7718b5dc6ec90e10000000000000000000000000000000000000000000000000000000000000020000000000000000000000000c01318bab7ee1f5ba734172bf7718b5dc6ec90e1","value":"0"},
                 {"to":"0x1ffAdc16726dd4F91fF275b4bF50651801B06a86","data":"0x5e82669500000000000000000000000000000000000000000000000000000000000000040000000000000000000000005c0f23a5c1be65fa710d385814a7fd1bda480b1c","value": "0"},
                 {"to":"0x1ffAdc16726dd4F91fF275b4bF50651801B06a86","data":"0x2fcf52d100000000000000000000000000000000000000000000000000000000000000040000000000000000000000005c0f23a5c1be65fa710d385814a7fd1bda480b1c2e1a7d4d000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000001","value": "0"}]}"""

    apply_roles_presets(
        avatar_safe,
        roles_contract,
        json_data=presets,
        replaces=[
            ("c01318bab7ee1f5ba734172bf7718b5dc6ec90e1", avatar_safe.address[2:]),
            (
                "5c0f23a5c1be65fa710d385814a7fd1bda480b1c",
                "79eF6103A513951a3b25743DB509E267685726B7",
            ),
            (
                "ff4ce5aaab5a627bf82f4a571ab1ce94aa365ea60000000000000000000005d9",
                "1e19cf2d73a72ef1332c882f20534b6519be0276000200000000000000000112",
            ),
        ],
    )

    blockchain = Chain.get_blockchain_from_web3(w3)

    avatar_safe_address = avatar_safe.address
    disassembler_address = accounts[4].address
    private_key = accounts[4].key
    role = 4

    emergency = "0xA29F61256e948F3FB707b4b3B138C5cCb9EF9888"

    ctx = GenericTxContext(w3=w3, avatar_safe_address=avatar_safe.address)
    disassembler_instance = Disassembler()

    RETH_WETH_BPT_gauge = "0x79eF6103A513951a3b25743DB509E267685726B7"
    RETH_WETH_bpt_address = "0x1E19CF2D73a72Ef1332C882F20534B6519Be0276"

    bpt_gauge_contract = w3.eth.contract(
        address=RETH_WETH_BPT_gauge, abi=Abis[blockchain].Gauge.abi
    )
    steal_token(
        w3=w3,
        token=RETH_WETH_BPT_gauge,
        holder="0xa19ed0aE46e89461e56063f1eD268a0dc225745f",
        to=avatar_safe.address,
        amount=4_000_000_000,
    )

    RETH_contract = erc20_contract(w3, EthTokAdd.rETH)
    RETH_balance_before = RETH_contract.functions.balanceOf(avatar_safe_address).call()
    assert RETH_balance_before == 0

    bpt_gauge_balance = bpt_gauge_contract.functions.balanceOf(
        avatar_safe.address
    ).call()
    assert bpt_gauge_balance == 4_000_000_000

    txn_transactable = balancer.UnstakeAndWithdrawProportional.get_txns(
        ctx=ctx,
        arguments=balancer.UnstakeAndWithdrawProportional.Args(
            gauge_address=RETH_WETH_BPT_gauge,
            max_slippage=1,
            amount=int(Decimal(bpt_gauge_balance) / Decimal(2)),
        ),
    )

    set_gas_strategy(GasStrategies.AGGRESIVE)
    disassembler_instance.send(
        ctx=ctx,
        roles_mod_address=roles_contract.address,
        role=role,
        txns=txn_transactable,
        private_key=private_key,
    )

    RETH_balance_after = RETH_contract.functions.balanceOf(avatar_safe_address).call()
    assert RETH_balance_after == 867203606

    bpt_gauge_balance_after = bpt_gauge_contract.functions.balanceOf(
        avatar_safe_address
    ).call()
    assert bpt_gauge_balance_after == int(Decimal(bpt_gauge_balance) / Decimal(2))


# possible use for testing recovery mode:
# def test_integration_exit_1_3(local_node_eth, accounts):
#     w3 = local_node_eth.w3
#     block = 18193307
#     local_node_eth.set_block(block)
#     avatar_safe = create_simple_safe(w3=w3, owner=accounts[0])
#     roles_contract = deploy_roles(avatar=avatar_safe.address, w3=w3)
#     setup_common_roles(avatar_safe, roles_contract)

#     apply_presets(
#         avatar_safe,
#         roles_contract,
#         json_data=preset,
#         replaces=[("c01318bab7ee1f5ba734172bf7718b5dc6ec90e1", avatar_safe.address[2:])],
#     )

#     blockchain = Chain.get_blockchain_from_web3(w3)

#     avatar_safe_address = avatar_safe.address
#     disassembler_address = accounts[1].address
#     private_key = accounts[1].key
#     role = 1

#     emergency = "0xA29F61256e948F3FB707b4b3B138C5cCb9EF9888"

#     top_up_address(w3, emergency, 100)
#     local_node_eth.unlock_account(emergency)

#     balancer_disassembler = BalancerDisassembler(
#         w3=w3,
#         avatar_safe_address=avatar_safe.address,
#         roles_mod_address=roles_contract.address,
#         role=role,
#         signer_address=disassembler_address,
#     )

#     # ----------------------------------------------------------------------------------------------------------------
#     # Stable Pool v2

#     DOLA_USDC_BPT = "0xFf4ce5AAAb5a627bf82f4A571AB1cE94Aa365eA6"

#     bpt_contract = w3.eth.contract(address=DOLA_USDC_BPT, abi=Abis[blockchain].UniversalBPT.abi)
#     steal_token(
#         w3=w3,
#         token=DOLA_USDC_BPT,
#         holder="0xF59b324Cb65258DC52B5DB8ac4f991286603B7e1",
#         to=avatar_safe.address,
#         amount=4_000_000_000,
#     )
#     bpt_balance = bpt_contract.functions.balanceOf(avatar_safe.address).call()
#     assert bpt_balance == 4_000_000_000

#     bpt_contract.functions.enableRecoveryMode().transact({"from": emergency})
#     assert bpt_contract.functions.inRecoveryMode().call()

#     DOLA_contract = w3.eth.contract(address="0x865377367054516e17014CcdED1e7d814EDC9ce4", abi=erc20_abi)
#     DOLA_balance = DOLA_contract.functions.balanceOf(avatar_safe_address).call()
#     assert DOLA_balance == 0

#     USDC_contract = w3.eth.contract(address=ETHAddr.USDC, abi=erc20_abi)
#     USDC_balance = USDC_contract.functions.balanceOf(avatar_safe_address).call()
#     assert USDC_balance == 0

#     txn_transactable = balancer_disassembler.exit_1_3(percentage=50, arguments=[{"bpt_address": DOLA_USDC_BPT}])

#     balancer_disassembler.send(txns=txn_transactable, private_key=private_key)

#     bpt_balance_after = bpt_contract.functions.balanceOf(avatar_safe_address).call()
#     assert bpt_balance_after == 2_000_000_000
#     assert bpt_balance_after == int(Decimal(bpt_balance) / Decimal(2))

#     new_DOLA_balance = DOLA_contract.functions.balanceOf(avatar_safe_address).call()
#     assert new_DOLA_balance == 1300986017

#     new_USDC_balance = USDC_contract.functions.balanceOf(avatar_safe_address).call()
#     assert new_USDC_balance == 0

#     # ----------------------------------------------------------------------------------------------------------------
#     # Composable Pool
#     GHO_USDT_USDC_bpt_address = "0x8353157092ED8Be69a9DF8F95af097bbF33Cb2aF"

#     bpt_contract = w3.eth.contract(address=GHO_USDT_USDC_bpt_address, abi=Abis[blockchain].UniversalBPT.abi)
#     steal_token(
#         w3=w3,
#         token=GHO_USDT_USDC_bpt_address,
#         holder="0x854B004700885A61107B458f11eCC169A019b764",
#         to=avatar_safe.address,
#         amount=8_999_999_999_999_000_000,
#     )
#     bpt_balance = bpt_contract.functions.balanceOf(avatar_safe.address).call()
#     assert bpt_balance == 8_999_999_999_999_000_000

#     bpt_contract.functions.enableRecoveryMode().transact({"from": emergency})
#     assert bpt_contract.functions.inRecoveryMode().call()

#     GHO_contract = w3.eth.contract(address=ETHAddr.GHO, abi=erc20_abi)
#     GHO_balance = GHO_contract.functions.balanceOf(avatar_safe_address).call()
#     assert GHO_balance == 0

#     USDC_contract = w3.eth.contract(address=ETHAddr.USDC, abi=erc20_abi)
#     USDC_balance = USDC_contract.functions.balanceOf(avatar_safe_address).call()
#     assert USDC_balance == 0

#     USDT_contract = w3.eth.contract(address=ETHAddr.USDT, abi=erc20_abi)
#     USDT_balance = USDC_contract.functions.balanceOf(avatar_safe_address).call()
#     assert USDT_balance == 0

#     txn_transactable = balancer_disassembler.exit_1_3(
#         percentage=50, arguments=[{"bpt_address": GHO_USDT_USDC_bpt_address}]
#     )

#     balancer_disassembler.send(txns=txn_transactable, private_key=private_key)

#     bpt_balance_after = bpt_contract.functions.balanceOf(avatar_safe_address).call()
#     assert bpt_balance_after == 4499999999999500000
#     assert bpt_balance_after == int(Decimal(bpt_balance) / Decimal(2))

#     new_GHO_balance = GHO_contract.functions.balanceOf(avatar_safe_address).call()
#     assert new_GHO_balance == 3222367741951859479

#     new_USDC_balance = USDC_contract.functions.balanceOf(avatar_safe_address).call()
#     assert new_USDC_balance == 643614

#     new_USDT_balance = USDT_contract.functions.balanceOf(avatar_safe_address).call()
#     assert new_USDT_balance == 649472

#     # ----------------------------------------------------------------------------------------------------------------
#     # Weighted Pool
#     RETH_BADGER_bpt_address = "0x1ee442b5326009Bb18F2F472d3e0061513d1A0fF"

#     bpt_contract = w3.eth.contract(address=RETH_BADGER_bpt_address, abi=Abis[blockchain].UniversalBPT.abi)
#     steal_token(
#         w3=w3,
#         token=RETH_BADGER_bpt_address,
#         holder="0x4A07a7c6fe412d14134DcE2Bb738B32757B968Fe",
#         to=avatar_safe.address,
#         amount=4_000_000_000,
#     )
#     bpt_balance = bpt_contract.functions.balanceOf(avatar_safe.address).call()
#     assert bpt_balance == 4_000_000_000

#     bpt_contract.functions.enableRecoveryMode().transact({"from": emergency})
#     assert bpt_contract.functions.inRecoveryMode().call()

#     BADGER_contract = w3.eth.contract(address="0x3472A5A71965499acd81997a54BBA8D852C6E53d", abi=erc20_abi)
#     BADGER_balance = BADGER_contract.functions.balanceOf(avatar_safe_address).call()
#     assert BADGER_balance == 0

#     RETH_contract = w3.eth.contract(address=ETHAddr.rETH, abi=erc20_abi)
#     RETH_balance = RETH_contract.functions.balanceOf(avatar_safe_address).call()
#     assert RETH_balance == 0

#     txn_transactable = balancer_disassembler.exit_1_3(
#         percentage=50, arguments=[{"bpt_address": RETH_BADGER_bpt_address}]
#     )

#     balancer_disassembler.send(txns=txn_transactable, private_key=private_key)

#     bpt_balance_after = bpt_contract.functions.balanceOf(avatar_safe_address).call()
#     assert bpt_balance_after == 2_000_000_000
#     assert bpt_balance_after == int(Decimal(bpt_balance) / Decimal(2))

#     new_BADGER_balance = BADGER_contract.functions.balanceOf(avatar_safe_address).call()
#     assert new_BADGER_balance == 29236985884

#     new_RETH_balance = RETH_contract.functions.balanceOf(avatar_safe_address).call()
#     assert new_RETH_balance == 33893683
