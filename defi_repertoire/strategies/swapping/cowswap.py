import asyncio

from defabipedia.balancer import Chain
from defabipedia.tokens import NATIVE
from defabipedia.types import Blockchain
from pydantic import BaseModel
from roles_royce.generic_method import Transactable
from roles_royce.protocols import cowswap
from roles_royce.protocols.cowswap.utils import requests
from roles_royce.protocols.swap_pools.swap_methods import WrapNativeToken

from defi_repertoire.stale_while_revalidate import cache_af
from defi_repertoire.strategies.base import (
    AddressOption,
    GenericTxContext,
    OptSwapArguments,
    SwapArguments,
    register,
)
from defi_repertoire.utils import flatten, uniqBy

from .swapper import get_wrapped_token

GNOSIS_LISTS = [
    "https://raw.githubusercontent.com/cowprotocol/token-lists/main/src/public/GnosisUniswapTokensList.json",
    "https://raw.githubusercontent.com/cowprotocol/token-lists/main/src/public/GnosisCoingeckoTokensList.json",
    "https://tokens.honeyswap.org/",
    "https://files.cow.fi/tokens/CowSwap.json",
]

ETHEREUM_LISTS = [
    "https://files.cow.fi/tokens/CoinGecko.json",
    "https://files.cow.fi/tokens/CowSwap.json",
    "https://raw.githubusercontent.com/compound-finance/token-list/master/compound.tokenlist.json",
    "https://raw.githubusercontent.com/SetProtocol/uniswap-tokenlist/main/set.tokenlist.json",
    "https://raw.githubusercontent.com/opynfinance/opyn-tokenlist/master/opyn-squeeth-tokenlist.json",
    "https://app.tryroll.com/tokens.json",
]


@cache_af()
async def fetch_tokens(blockchain: Blockchain):
    lists = {"ethereum": ETHEREUM_LISTS, "gnosis": GNOSIS_LISTS}[blockchain]
    chainId = {"ethereum": 1, "gnosis": 100}[blockchain]

    async def fetch_list(url):
        resp = requests.get(url)
        tokens = resp.json()["tokens"]
        return [t for t in tokens if t["chainId"] == chainId]

    tokens = await asyncio.gather(*[fetch_list(url) for url in lists])

    return uniqBy(flatten(tokens), "address")


def tokens_to_options(tokens) -> list[AddressOption]:
    return [AddressOption(address=t["address"], label=t["symbol"]) for t in tokens]


@register
class SwapCowswap:
    """Make a swap on CowSwap with best amount out"""

    kind = "swap"
    protocol = "cowswap"
    id = "swap_on_cowswap"
    name = "Swap on CoWswap"

    class BaseOptions(BaseModel):
        token_in_address: list[AddressOption]

    @classmethod
    async def get_base_options(cls, blockchain: Blockchain) -> BaseOptions:
        tokens = await fetch_tokens(blockchain)
        return cls.BaseOptions(token_in_address=tokens_to_options(tokens))

    @classmethod
    def get_txns(
        cls, ctx: GenericTxContext, arguments: SwapArguments
    ) -> list[Transactable]:
        max_slippage = arguments.max_slippage / 100
        token_in = arguments.token_in_address
        token_out = arguments.token_out_address
        amount = arguments.amount

        txns = []

        if amount == 0:
            return []

        if "anvil" in ctx.w3.client_version:
            fork = True
        else:
            fork = False

        if token_in == NATIVE:
            wraptoken = WrapNativeToken(blockchain=ctx.blockchain, eth_amount=amount)
            txns.append(wraptoken)
            token_in = get_wrapped_token(ctx.blockchain)

        cow_txns = cowswap.create_order_and_swap(
            w3=ctx.w3,
            avatar=ctx.avatar_safe_address,
            sell_token=token_in,
            buy_token=token_out,
            amount=amount,
            kind=cowswap.SwapKind.SELL,
            max_slippage=max_slippage,
            valid_duration=20 * 60,
            fork=fork,
        )

        for cow_txn in cow_txns:
            txns.append(cow_txn)

        return txns
