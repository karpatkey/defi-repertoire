from decimal import Decimal

import requests
from defabipedia.tokens import NATIVE
from defabipedia.types import Blockchain, Chain
from pydantic import BaseModel
from roles_royce.generic_method import Transactable
from roles_royce.protocols.swap_pools.swap_methods import ApproveCurve, SwapCurve

from defi_repertoire.stale_while_revalidate import stale_while_revalidate_cache
from defi_repertoire.strategies.base import (
    ChecksumAddress,
    GenericTxContext,
    OptSwapArguments,
    SwapArguments,
    register,
)
from defi_repertoire.utils import flatten, uniqBy

from .swapper import find_reachable_tokens, get_quote, get_swap_pools


@stale_while_revalidate_cache()
async def fetch_pools(blockchain: Blockchain):
    chain = {"ethereum": "ethereum", "gnosis": "xdai"}[blockchain]
    url = f"https://api.curve.fi/v1/getPools/big/{chain}"
    response = requests.get(url=url)
    return response.json()["data"]["poolData"]


def tokens_to_options(tokens):
    return [{"address": t["address"], "label": t["symbol"]} for t in tokens]


@register
class SwapOnCurve:
    """Make a swap on Curve with best amount out"""

    kind = "swap"
    protocol = "balancer"
    id = "swap_on_curve"
    name = "Swap on Curve"

    class OptArgs(BaseModel):
        token_in_address: ChecksumAddress

    @classmethod
    async def get_base_options(cls, blockchain: Blockchain):
        pools = await fetch_pools(blockchain)
        tokens = uniqBy(flatten([p["coins"] for p in pools]), "address")
        return {"token_in_address": tokens_to_options(tokens)}

    @classmethod
    async def get_options(cls, blockchain: Blockchain, arguments: OptArgs):
        pools = await fetch_pools(blockchain)
        poolPairs = [p["coins"] for p in pools]
        outs = find_reachable_tokens(poolPairs, arguments.token_in_address, 3)
        return {"token_out_address": tokens_to_options(outs)}

    @classmethod
    def get_txns(
        cls, ctx: GenericTxContext, arguments: SwapArguments
    ) -> list[Transactable]:
        max_slippage = arguments.max_slippage / 100
        token_in = arguments.token_in_address
        token_out = arguments.token_out_address
        amount = arguments.amount

        txns = []

        # get the pools where we get a quote from
        pools = get_swap_pools(ctx.blockchain, "Curve", token_in, token_out)
        quotes = []
        if len(pools) == 0:
            raise ValueError("No pools found with the specified tokens")
        else:
            for pool in pools:
                swap_pool, quote = get_quote(ctx, pool, token_in, token_out, amount)
                quotes.append(quote)

        # get the best quote
        best_quote = max(quotes)
        amount_out_min_slippage = int(Decimal(best_quote) * Decimal(1 - max_slippage))

        if token_in == NATIVE:
            eth_amount = amount
        else:
            eth_amount = 0
            approve_curve = ApproveCurve(
                blockchain=ctx.blockchain,
                token_address=token_in,
                spender=swap_pool.address,
                amount=amount,
            )
            txns.append(approve_curve)

        swap_curve = SwapCurve(
            blockchain=ctx.blockchain,
            pool_address=swap_pool.address,
            token_x=swap_pool.tokens.index(token_in),
            token_y=swap_pool.tokens.index(token_out),
            amount_x=amount,
            min_amount_y=amount_out_min_slippage,
            eth_amount=eth_amount,
        )

        txns.append(swap_curve)
        return txns
