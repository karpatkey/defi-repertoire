import pytest
from defabipedia import Chain

from defi_repertoire.strategies.disassembling import disassembling_aura as aura
from tests.vcr import my_vcr


@my_vcr.use_cassette()
@pytest.mark.asyncio
async def test_aura_options_gnosis():
    blockchain = Chain.get_blockchain_by_chain_id(100)

    opts = await aura.Withdraw.get_base_options(blockchain)
    assert len(opts["rewards_address"]) == 20


@my_vcr.use_cassette()
@pytest.mark.asyncio
async def test_aura_options_ethereum():
    blockchain = Chain.get_blockchain_by_chain_id(1)

    opts = await aura.Withdraw.get_base_options(blockchain)
    assert len(opts["rewards_address"]) == 142


@my_vcr.use_cassette()
@pytest.mark.asyncio
async def test_aura_options_ethereum_single_out():
    blockchain = Chain.get_blockchain_by_chain_id(1)

    bpt_address = "0x82feb430d9d14ee5e635c41807e03fd8f5fffdec"

    opts = await aura.WithdrawSingle.get_base_options(blockchain)
    assert len(opts["rewards_address"]) == 142

    opts2 = await aura.WithdrawSingle.get_options(
        blockchain,
        aura.WithdrawSingle.OptArgs(rewards_address=bpt_address),
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
