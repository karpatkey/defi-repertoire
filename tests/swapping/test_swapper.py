import pytest
from defabipedia.balancer import Chain

from defi_repertoire.strategies.swapping.swapper import find_reachable_tokens


def test_find_reachable_token():
    curvePairs = [
        [
            {
                "address": "0xe91D153E0b41518A2Ce8Dd3D7944Fa863463a97d",
                "symbol": "WXDAI",
            },
            {
                "address": "0xDDAfbb505ad214D7b80b1f830fcCc89B60fb7A83",
                "symbol": "USDC",
            },
            {
                "address": "0x4ECaBa5870353805a9F068101A40E0f32ed605C6",
                "symbol": "USDT",
            },
        ],
        [
            {
                "address": "0xA4eF9Da5BA71Cc0D2e5E877a910A37eC43420445",
                "symbol": "sGNO",
            },
            {
                "address": "0x9C58BAcC331c9aa871AFD802DB6379a98e80CEdb",
                "symbol": "GNO",
            },
        ],
        [
            {
                "address": "0x6aC78efae880282396a335CA2F79863A1e6831D4",
                "symbol": "rGNO",
            },
            {
                "address": "0xA4eF9Da5BA71Cc0D2e5E877a910A37eC43420445",
                "symbol": "sGNO",
            },
        ],
        [
            {
                "address": "0xcB444e90D8198415266c6a2724b7900fb12FC56E",
                "symbol": "EURe",
            },
            {
                "address": "0x1337BedC9D22ecbe766dF105c9623922A27963EC",
                "symbol": "x3CRV",
            },
        ],
        [
            {
                "address": "0x5Cb9073902F2035222B9749F8fB0c9BFe5527108",
                "symbol": "GBPe",
            },
            {
                "address": "0x1337BedC9D22ecbe766dF105c9623922A27963EC",
                "symbol": "x3CRV",
            },
        ],
        [
            {
                "address": "0xcB444e90D8198415266c6a2724b7900fb12FC56E",
                "symbol": "EURe",
            },
            {
                "address": "0x712b3d230F3C1c19db860d80619288b1F0BDd0Bd",
                "symbol": "CRV",
            },
        ],
        [
            {
                "address": "0xaBEf652195F98A91E490f047A5006B71c85f058d",
                "symbol": "crvUSD",
            },
            {
                "address": "0xaf204776c7245bF4147c2612BF6e5972Ee483701",
                "symbol": "sDAI",
            },
        ],
        [
            {
                "address": "0xaBEf652195F98A91E490f047A5006B71c85f058d",
                "symbol": "crvUSD",
            },
            {
                "address": "0xDDAfbb505ad214D7b80b1f830fcCc89B60fb7A83",
                "symbol": "USDC",
            },
        ],
    ]

    assert find_reachable_tokens(curvePairs, "0xnot_and_address") == []

    assert find_reachable_tokens(
        curvePairs, "0xcB444e90D8198415266c6a2724b7900fb12FC56E", 1
    ) == [
        {
            "address": "0x1337BedC9D22ecbe766dF105c9623922A27963EC",
            "symbol": "x3CRV",
        },
        {
            "address": "0x712b3d230F3C1c19db860d80619288b1F0BDd0Bd",
            "symbol": "CRV",
        },
    ]

    assert find_reachable_tokens(
        curvePairs, "0xcB444e90D8198415266c6a2724b7900fb12FC56E"
    ) == [
        {
            "address": "0x1337BedC9D22ecbe766dF105c9623922A27963EC",
            "symbol": "x3CRV",
        },
        {
            "address": "0x5Cb9073902F2035222B9749F8fB0c9BFe5527108",
            "symbol": "GBPe",
        },
        {
            "address": "0x712b3d230F3C1c19db860d80619288b1F0BDd0Bd",
            "symbol": "CRV",
        },
    ]

    assert find_reachable_tokens(
        curvePairs, "0xe91D153E0b41518A2Ce8Dd3D7944Fa863463a97d", 1
    ) == [
        {
            "address": "0x4ECaBa5870353805a9F068101A40E0f32ed605C6",
            "symbol": "USDT",
        },
        {
            "address": "0xDDAfbb505ad214D7b80b1f830fcCc89B60fb7A83",
            "symbol": "USDC",
        },
    ]

    assert find_reachable_tokens(
        curvePairs, "0xe91D153E0b41518A2Ce8Dd3D7944Fa863463a97d"
    ) == [
        {
            "address": "0x4ECaBa5870353805a9F068101A40E0f32ed605C6",
            "symbol": "USDT",
        },
        {
            "address": "0xDDAfbb505ad214D7b80b1f830fcCc89B60fb7A83",
            "symbol": "USDC",
        },
        {
            "address": "0xaBEf652195F98A91E490f047A5006B71c85f058d",
            "symbol": "crvUSD",
        },
    ]
