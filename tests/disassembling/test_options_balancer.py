import pytest
from defabipedia import Chain

from defi_repertoire.strategies.disassembling import disassembling_balancer as balancer
from tests.vcr import my_vcr


@my_vcr.use_cassette()
@pytest.mark.asyncio
async def test_balancer_withdraw_single_options_gnosis():
    blockchain = Chain.get_blockchain_by_chain_id(100)

    bpt_address = "0x21d4c792ea7e38e0d0819c2011a2b1cb7252bd99"

    opts = await balancer.WithdrawSingle.get_base_options(blockchain)

    assert len(opts["bpt_address"]) > 10

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
async def test_balancer_withdraw_single_options_eth():
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


@my_vcr.use_cassette()
@pytest.mark.asyncio
async def test_balancer_unstake_withdraw_single_options_gnosis():
    blockchain = Chain.get_blockchain_by_chain_id(100)

    gauge_address = "0x49b7c059bf0a71583918928d33c84dcb2aa001f8"

    opts = await balancer.UnstakeAndWithdrawSingleToken.get_base_options(blockchain)

    assert len(opts["gauge_address"]) > 40

    assert next(
        o for o in opts["gauge_address"] if o["label"] == "stEUR/EURe-gauge"
    ) == {
        "address": gauge_address,
        "label": "stEUR/EURe-gauge",
    }

    opts2 = await balancer.UnstakeAndWithdrawSingleToken.get_options(
        blockchain,
        balancer.UnstakeAndWithdrawSingleToken.OptArgs(gauge_address=gauge_address),
    )
    assert opts2["token_out_address"] == [
        {
            "address": "0x004626a008b1acdc4c74ab51644093b155e59a23",
            "label": "stEUR",
        },
        {
            "address": "0x06135a9ae830476d3a941bae9010b63732a055f4",
            "label": "stEUR/EURe",
        },
        {
            "address": "0xcb444e90d8198415266c6a2724b7900fb12fc56e",
            "label": "EURe",
        },
    ]
