import pytest

from defi_repertoire.strategies.base import GenericTxContext
from defi_repertoire.strategies.disassembling import disassembling_balancer as balancer
from tests.utils import web3_eth, web3_gnosis
from tests.vcr import my_vcr


@my_vcr.use_cassette()
@pytest.mark.asyncio
async def test_balancer_options_gnosis(web3_gnosis, accounts):
    w3 = web3_gnosis

    cow_gno_pool_address = "0x21d4c792Ea7E38e0D0819c2011A2b1Cb7252Bd99"

    ctx = GenericTxContext(w3=w3, avatar_safe_address=accounts[0].address)
    arguments = balancer.OptExit12Arguments(
        bpt_address=None, max_slippage=None, token_out_address=None, amount=None
    )
    opts = await balancer.WithdrawSingle.get_options(ctx, arguments)
    assert str.lower(cow_gno_pool_address) in opts["bpt_address"]

    arguments = balancer.OptExit12Arguments(
        bpt_address=cow_gno_pool_address,
        max_slippage=None,
        token_out_address=None,
        amount=None,
    )
    opts2 = await balancer.WithdrawSingle.get_options(ctx, arguments)
    assert str.lower(cow_gno_pool_address) in opts2["bpt_address"]
    assert len(opts2["bpt_address"]) == 1
    assert opts2["token_out_address"] == [
        {
            "address": "0x177127622c4a00f3d409b75571e12cb3c8973d3c",
            "name": "CoW Protocol Token from Mainnet",
            "symbol": "COW",
        },
        {
            "address": "0x9c58bacc331c9aa871afd802db6379a98e80cedb",
            "name": "Gnosis Token on xDai",
            "symbol": "GNO",
        },
    ]


@my_vcr.use_cassette()
@pytest.mark.asyncio
async def test_balancer_options_eth(web3_eth, accounts):
    w3 = web3_eth

    cow_gno_pool_address = "0x92762b42a06dcdddc5b7362cfb01e631c4d44b40"

    ctx = GenericTxContext(w3=w3, avatar_safe_address=accounts[0].address)
    arguments = balancer.OptExit12Arguments(
        bpt_address=None, max_slippage=None, token_out_address=None, amount=None
    )
    opts = await balancer.WithdrawSingle.get_options(ctx, arguments)
    assert str.lower(cow_gno_pool_address) in opts["bpt_address"]

    arguments = balancer.OptExit12Arguments(
        bpt_address=cow_gno_pool_address,
        max_slippage=None,
        token_out_address=None,
        amount=None,
    )
    opts2 = await balancer.WithdrawSingle.get_options(ctx, arguments)
    assert str.lower(cow_gno_pool_address) in opts2["bpt_address"]
    assert len(opts2["bpt_address"]) == 1
    assert opts2["token_out_address"] == [
        {
            "address": "0x6810e776880c02933d47db1b9fc05908e5386b96",
            "name": "Gnosis Token",
            "symbol": "GNO",
        },
        {
            "address": "0xdef1ca1fb7fbcdc777520aa7f396b4e015f497ab",
            "name": "CoW Protocol Token",
            "symbol": "COW",
        },
    ]