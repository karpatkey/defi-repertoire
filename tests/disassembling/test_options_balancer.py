import pytest
from defabipedia import Chain

from defi_repertoire.strategies.disassembling import disassembling_balancer as balancer
from tests.vcr import my_vcr


@my_vcr.use_cassette()
@pytest.mark.asyncio
async def test_balancer_options_gnosis():
    blockchain = Chain.get_blockchain_by_chain_id(100)

    bpt_address = "0x21d4c792ea7e38e0d0819c2011a2b1cb7252bd99"

    opts = await balancer.WithdrawSingle.get_base_options(blockchain)

    assert len(opts["bpt_address"]) == 13

    assert next(o for o in opts["bpt_address"] if o["label"] == "50COW-50GNO") == {
        "address": bpt_address,
        "label": "50COW-50GNO",
    }

    opts2 = await balancer.WithdrawSingle.get_options(
        blockchain,
        balancer.WithdrawSingle.OptArgs(bpt_address=bpt_address),
    )
    assert opts2["token_out_address"] == [
        {
            "address": "0x177127622c4a00f3d409b75571e12cb3c8973d3c",
            "label": "COW",
        },
        {
            "address": "0x9c58bacc331c9aa871afd802db6379a98e80cedb",
            "label": "GNO",
        },
    ]


@my_vcr.use_cassette()
@pytest.mark.asyncio
async def test_balancer_options_eth():
    blockchain = Chain.get_blockchain_by_chain_id(1)

    cow_gno_pool_address = "0x92762b42a06dcdddc5b7362cfb01e631c4d44b40"

    opts = await balancer.WithdrawSingle.get_base_options(blockchain)

    assert len(opts["bpt_address"]) == 68

    opts2 = await balancer.WithdrawSingle.get_options(
        blockchain,
        balancer.WithdrawSingle.OptArgs(bpt_address=cow_gno_pool_address),
    )
    assert opts2["token_out_address"] == [
        {
            "address": "0x6810e776880c02933d47db1b9fc05908e5386b96",
            "label": "GNO",
        },
        {
            "address": "0xdef1ca1fb7fbcdc777520aa7f396b4e015f497ab",
            "label": "COW",
        },
    ]
