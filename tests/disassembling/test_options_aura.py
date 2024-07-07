import pytest

from defi_repertoire.strategies.base import GenericTxContext
from defi_repertoire.strategies.disassembling import disassembling_aura as aura
from tests.utils import web3_eth, web3_gnosis
from tests.vcr import my_vcr


@my_vcr.use_cassette()
@pytest.mark.asyncio
async def test_aura_options_gnosis(web3_gnosis, accounts):
    w3 = web3_gnosis

    weth_wsteth_address = "0x026d163c28cc7dbf57d6ed57f14208ee412ca526"

    ctx = GenericTxContext(w3=w3, avatar_safe_address=accounts[0].address)
    opts = await aura.Withdraw.get_options(ctx, aura.Withdraw.OptArgs(**{}))
    assert str.lower(weth_wsteth_address) in opts["rewards_address"]

    opts2 = await aura.Withdraw.get_options(
        ctx, aura.Withdraw.OptArgs(**{"rewards_address": weth_wsteth_address})
    )
    assert str.lower(weth_wsteth_address) in opts2["rewards_address"]
    assert len(opts2["rewards_address"]) == 1


@my_vcr.use_cassette()
@pytest.mark.asyncio
async def test_aura_options_ethereum(web3_eth, accounts):
    w3 = web3_eth

    cow_gno_pool_address = "0x82feb430d9d14ee5e635c41807e03fd8f5fffdec"

    ctx = GenericTxContext(w3=w3, avatar_safe_address=accounts[0].address)
    opts = await aura.Withdraw.get_options(ctx, aura.Withdraw.OptArgs(**{}))
    assert str.lower(cow_gno_pool_address) in opts["rewards_address"]

    opts2 = await aura.Withdraw.get_options(
        ctx, aura.Withdraw.OptArgs(**{"rewards_address": cow_gno_pool_address})
    )
    assert str.lower(cow_gno_pool_address) in opts2["rewards_address"]
    assert len(opts2["rewards_address"]) == 1


@my_vcr.use_cassette()
@pytest.mark.asyncio
async def test_aura_options_ethereum_single_out(web3_eth, accounts):
    w3 = web3_eth

    cow_gno_pool_address = "0x82feb430d9d14ee5e635c41807e03fd8f5fffdec"

    ctx = GenericTxContext(w3=w3, avatar_safe_address=accounts[0].address)
    opts = await aura.WithdrawSingle.get_options(ctx, aura.WithdrawSingle.OptArgs(**{}))
    assert str.lower(cow_gno_pool_address) in opts["rewards_address"]

    opts2 = await aura.WithdrawSingle.get_options(
        ctx, aura.WithdrawSingle.OptArgs(**{"rewards_address": cow_gno_pool_address})
    )
    assert str.lower(cow_gno_pool_address) in opts2["rewards_address"]
    assert len(opts2["rewards_address"]) == 1
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
