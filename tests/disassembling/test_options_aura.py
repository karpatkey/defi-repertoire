import pytest
from defabipedia import Chain

from defi_repertoire.strategies.disassembling import disassembling_aura as aura
from tests.vcr import my_vcr


@my_vcr.use_cassette()
@pytest.mark.asyncio
async def test_aura_options_gnosis():
    blockchain = Chain.get_blockchain_by_chain_id(100)
    weth_wsteth_address = "0x026d163c28cc7dbf57d6ed57f14208ee412ca526"

    opts = await aura.Withdraw.get_base_options(blockchain)
    assert str.lower(weth_wsteth_address) in opts["rewards_address"]

    opts2 = await aura.Withdraw.get_options(
        blockchain, aura.Withdraw.OptArgs(rewards_address=weth_wsteth_address)
    )
    assert str.lower(weth_wsteth_address) in opts2["rewards_address"]
    assert len(opts2["rewards_address"]) == 1


@my_vcr.use_cassette()
@pytest.mark.asyncio
async def test_aura_options_ethereum():
    blockchain = Chain.get_blockchain_by_chain_id(1)

    cow_gno_pool_address = "0x82feb430d9d14ee5e635c41807e03fd8f5fffdec"

    opts = await aura.Withdraw.get_base_options(blockchain)
    assert str.lower(cow_gno_pool_address) in opts["rewards_address"]

    opts2 = await aura.Withdraw.get_options(
        blockchain, aura.Withdraw.OptArgs(rewards_address=cow_gno_pool_address)
    )
    assert str.lower(cow_gno_pool_address) in opts2["rewards_address"]
    assert len(opts2["rewards_address"]) == 1


@my_vcr.use_cassette()
@pytest.mark.asyncio
async def test_aura_options_ethereum_single_out():
    blockchain = Chain.get_blockchain_by_chain_id(1)

    cow_gno_pool_address = "0x82feb430d9d14ee5e635c41807e03fd8f5fffdec"

    opts = await aura.WithdrawSingle.get_base_options(blockchain)
    assert str.lower(cow_gno_pool_address) in opts["rewards_address"]

    opts2 = await aura.WithdrawSingle.get_options(
        blockchain,
        aura.WithdrawSingle.OptArgs(rewards_address=cow_gno_pool_address),
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
