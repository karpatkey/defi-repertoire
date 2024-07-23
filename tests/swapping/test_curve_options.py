import pytest
from defabipedia import Chain

from defi_repertoire.strategies.swapping.curve import SwapOnCurve
from tests.vcr import my_vcr


@my_vcr.use_cassette()
@pytest.mark.asyncio
async def test_curve_options_gnosis():
    blockchain = Chain.get_blockchain_by_chain_id(100)
    wxdai = "0xe91D153E0b41518A2Ce8Dd3D7944Fa863463a97d"

    opts = await SwapOnCurve.get_base_options(blockchain)
    assert "token_in_address" in opts
    assert len(opts["token_in_address"]) == 14

    assert opts["token_in_address"][0]["address"] == wxdai

    opts2 = await SwapOnCurve.get_options(
        blockchain, SwapOnCurve.OptArgs(token_in_address=wxdai)
    )
    assert "token_out_address" in opts2
    assert opts2["token_out_address"] == [
        {
            "address": "0x4ECaBa5870353805a9F068101A40E0f32ed605C6",
            "label": "USDT",
        },
        {
            "address": "0xDDAfbb505ad214D7b80b1f830fcCc89B60fb7A83",
            "label": "USDC",
        },
        {
            "address": "0xa555d5344f6FB6c65da19e403Cb4c1eC4a1a5Ee3",
            "label": "BREAD",
        },
        {
            "address": "0xaBEf652195F98A91E490f047A5006B71c85f058d",
            "label": "crvUSD",
        },
        {
            "address": "0xaf204776c7245bF4147c2612BF6e5972Ee483701",
            "label": "sDAI",
        },
    ]
