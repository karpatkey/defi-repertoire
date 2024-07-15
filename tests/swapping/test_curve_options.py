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
    assert "token_in" in opts
    assert len(opts["token_in"]) == 14

    assert opts["token_in"][0]["address"] == wxdai

    opts2 = await SwapOnCurve.get_options(
        blockchain, SwapOnCurve.OptArgs(token_in_address=wxdai)
    )
    assert "token_out" in opts2
    assert [p["symbol"] for p in opts2["token_out"]] == [
        "USDT",
        "USDC",
        "BREAD",
        "crvUSD",
        "sDAI",
    ]
