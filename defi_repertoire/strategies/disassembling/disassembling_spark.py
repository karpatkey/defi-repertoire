from decimal import Decimal

from defabipedia.spark import ContractSpecs
from defabipedia.tokens import Addresses
from roles_royce.generic_method import Transactable
from roles_royce.protocols import cowswap
from roles_royce.protocols.eth import spark

from ..base import (
    GenericTxContext,
    StrategyAmountArguments,
    StrategyAmountWithSlippageArguments,
    register,
)


def get_amount_to_redeem_sdai(ctx: GenericTxContext, fraction: Decimal | float) -> int:
    sdai = ContractSpecs[ctx.blockchain].sDAI.contract(ctx.w3)
    balance = sdai.functions.balanceOf(ctx.avatar_safe_address).call()
    return int(Decimal(balance) * Decimal(fraction))


@register
class Exit1:
    """Withdraw funds from Spark with proxy."""

    kind = "disassembly"
    protocol = "spark"
    name = "exit_1"

    @classmethod
    def get_txns(
        cls, ctx: GenericTxContext, arguments: StrategyAmountArguments
    ) -> list[Transactable]:
        exit_sdai = spark.RedeemSDAIforDAI(
            blockchain=ctx.blockchain,
            amount=arguments.amount,
            avatar=ctx.avatar_safe_address,
        )
        return [exit_sdai]


@register
class Exit2:
    """
    Swaps sDAI for USDC. Approves the Cowswap relayer to spend the sDAI if needed, then creates the order using
    the Cow's order API and creates the sign_order transaction.
    """

    kind = "disassembly"
    protocol = "spark"
    name = "exit_2"

    @classmethod
    def get_txns(
        cls, ctx: GenericTxContext, arguments: StrategyAmountWithSlippageArguments
    ) -> list[Transactable]:
        max_slippage = arguments.max_slippage / 100
        amount = arguments.amount

        if "anvil" in ctx.w3.client_version:
            fork = True
        else:
            fork = False

        return cowswap.create_order_and_swap(
            w3=ctx.w3,
            avatar=ctx.avatar_safe_address,
            sell_token=ContractSpecs[ctx.blockchain].sDAI.address,
            buy_token=Addresses[ctx.blockchain].USDC,
            amount=amount,
            kind=cowswap.SwapKind.SELL,
            max_slippage=max_slippage,
            valid_duration=20 * 60,
            fork=fork,
        )
