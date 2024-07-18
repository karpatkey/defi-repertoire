import os
from decimal import Decimal

from defabipedia.tokens import NATIVE
from roles_royce.generic_method import Transactable
from roles_royce.protocols.swap_pools import swap_methods

from defi_repertoire.strategies.base import GenericTxContext, SwapArguments, register
from defi_repertoire.strategies.swapping.swapper import (
    get_quote,
    get_swap_pools,
    get_wrapped_token,
)

API_KEY = os.getenv("THEGRAPH_API_KEY", "MOCK_KEY")
GRAPH_URL = f"https://gateway-arbitrum.network.thegraph.com/api/{API_KEY}/subgraphs/id/5zvR82QoaXYFyDEKLZ9t6v9adgnptxYpKpSbxtgVENFV"


@register
class SwapUniswapV3:
    """Make a swap on UniswapV3 with best amount out."""

    kind = "swap"
    protocol = "uniswapv3"
    id = "swap_on_uniswapv3"
    name = "Swap on UniswapV3"

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
        pools = get_swap_pools(ctx.blockchain, "UniswapV3", token_in, token_out)
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
            wraptoken = swap_methods.WrapNativeToken(
                blockchain=ctx.blockchain, eth_amount=amount
            )
            txns.append(wraptoken)
            token_in = get_wrapped_token(ctx.blockchain)
        elif token_out == NATIVE:
            token_out = get_wrapped_token(ctx.blockchain)

        approve_uniswapV3 = swap_methods.ApproveUniswapV3(
            blockchain=ctx.blockchain,
            token_address=token_in,
            amount=amount,
        )

        swap_uniswapV3 = swap_methods.SwapUniswapV3(
            blockchain=ctx.blockchain,
            token_in=token_in,
            token_out=token_out,
            avatar=ctx.avatar_safe_address,
            amount_in=amount,
            min_amount_out=amount_out_min_slippage,
            fee=swap_pool.uni_fee,
        )

        txns.append(approve_uniswapV3)
        txns.append(swap_uniswapV3)
        return txns
