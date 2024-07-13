from decimal import Decimal

from defabipedia.tokens import NATIVE
from roles_royce.generic_method import Transactable
from roles_royce.protocols.swap_pools.swap_methods import ApproveCurve, SwapCurve

from defi_repertoire.strategies.base import (
    GenericTxContext,
    OptSwapArguments,
    SwapArguments,
    register,
)

from .swapper import get_quote, get_swap_pools


@register
class SwapOnCurve:
    """Make a swap on Curve with best amount out"""

    kind = "swap"
    protocol = "balancer"
    id = "swap_on_curve"
    name = "Swap on Curve"

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
