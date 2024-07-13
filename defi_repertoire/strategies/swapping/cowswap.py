from defabipedia.tokens import NATIVE
from roles_royce.generic_method import Transactable
from roles_royce.protocols import cowswap
from roles_royce.protocols.swap_pools.swap_methods import WrapNativeToken

from defi_repertoire.strategies.base import (
    GenericTxContext,
    OptSwapArguments,
    SwapArguments,
    register,
)

from .swapper import get_wrapped_token


@register
class SwapCowswap:
    """Make a swap on CowSwap with best amount out"""

    kind = "swap"
    protocol = "cowswap"
    id = "swap_on_cowswap"
    name = "Swap on CoWswap"

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
