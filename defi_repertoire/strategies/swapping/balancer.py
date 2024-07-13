from decimal import Decimal
from time import time

from defabipedia.tokens import NATIVE
from roles_royce.generic_method import Transactable
from roles_royce.protocols import balancer
from roles_royce.protocols.balancer.methods_general import ApproveForVault
from roles_royce.protocols.balancer.types_and_enums import SwapKind
from roles_royce.protocols.swap_pools.swap_methods import WrapNativeToken

from defi_repertoire.strategies.base import (
    GenericTxContext,
    OptSwapArguments,
    SwapArguments,
    register,
)

from .swapper import get_pool_id, get_quote, get_swap_pools, get_wrapped_token


@register
class SwapBalancer:
    """Make a swap on Balancer with best amount out."""

    kind = "swap"
    protocol = "balancer"
    id = "swap_on_balancer"
    name = "Swap on Balancer"

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
        pools = get_swap_pools(ctx.blockchain, "Balancer", token_in, token_out)
        quotes = []
        if len(pools) == 0:
            raise ValueError("No pools found with the specified tokens")
        else:
            for pool in pools:
                swap_pool, quote = get_quote(ctx, pool, token_in, token_out, amount)
                quotes.append(quote)

        # TODO: here swap_pool is the latest defined swap_pool, is that correct?
        pool_id = get_pool_id(ctx.w3, ctx.blockchain, swap_pool.address)
        best_quote = max(quotes)
        amount_out_min_slippage = int(Decimal(best_quote) * Decimal(1 - max_slippage))
        if token_in == NATIVE:
            wraptoken = WrapNativeToken(blockchain=ctx.blockchain, eth_amount=amount)
            txns.append(wraptoken)
            token_in = get_wrapped_token(ctx.blockchain)
        elif token_out == NATIVE:
            token_out = get_wrapped_token(ctx.blockchain)
        approve_vault = ApproveForVault(token=token_in, amount=amount)
        swap_balancer = balancer.methods_swap.SingleSwap(
            blockchain=ctx.blockchain,
            pool_id=pool_id,
            avatar=ctx.avatar_safe_address,
            kind=SwapKind.OutGivenExactIn,
            token_in_address=token_in,
            token_out_address=token_out,
            amount_in=amount,
            min_amount_out=amount_out_min_slippage,
            deadline=int(int(time()) + 600),
        )

        txns.append(approve_vault)
        txns.append(swap_balancer)
        return txns
