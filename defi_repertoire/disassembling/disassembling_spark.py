from decimal import Decimal
from typing import TypedDict
from defabipedia.spark import ContractSpecs
from defabipedia.tokens import Addresses
from roles_royce.generic_method import Transactable
from roles_royce.protocols.eth import spark
from roles_royce.protocols import cowswap

from .disassembler import GenericTxContext, validate_percentage, RedeemOperation, SwapOperation


def get_amount_to_redeem_sdai(ctx: GenericTxContext, fraction: Decimal | float) -> int:
    sdai = ContractSpecs[ctx.blockchain].sDAI.contract(ctx.w3)
    balance = sdai.functions.balanceOf(ctx.avatar_safe_address).call()
    return int(Decimal(balance) * Decimal(fraction))


class Exit1:
    op_type = RedeemOperation  #

    @classmethod
    def get_txns(cls, ctx: GenericTxContext, percentage: float, arguments: list[dict] = None,
                 amount_to_redeem: int = None) -> list[Transactable]:
        """Withdraw funds from Spark with proxy.

        Args:
            percentage (float): Percentage of liquidity to remove from Spark.
            arguments (list[str]): List of Spark token addresses to withdraw from.
            amount_to_redeem (int, optional): Amount of Spark tokens to withdraw. Defaults to None.

        Returns
            list[Transactable]: List of transactions to exit Spark.
        """

        fraction = validate_percentage(percentage)

        if amount_to_redeem is None:
            amount_to_redeem = get_amount_to_redeem_sdai(ctx, fraction)

        exit_sdai = spark.RedeemSDAIforDAI(blockchain=ctx.blockchain,
                                           amount=amount_to_redeem,
                                           avatar=ctx.avatar_safe_address, )
        return [exit_sdai]


class Exit2Arguments(TypedDict):
    max_slippage: float

class Exit2:
    op_type = SwapOperation

    @classmethod
    def get_txns(cls, ctx: GenericTxContext, percentage: float, arguments: list[Exit2Arguments],
                 amount_to_redeem: int = None) -> list[Transactable]:

        """
        Swaps sDAI for USDC. Approves the Cowswap relayer to spend the sDAI if needed, then creates the order using
        the Cow's order API and creates the sign_order transaction.
        Args:
            percentage (float): Percentage of the total sDAI holdings to swap.
            arguments (list[dict]):  List with one single dictionary with the order parameters from an already
             created order:
                arg_dicts = [
                    {
                        "max_slippage": 11.25
                    }
                ]
            amount_to_redeem (int, optional): Amount of sDAI to swap. Defaults to None. If None, the 'percentage' of
                the total sDAI holdings are swapped
        Returns:
            list[ Transactable]: List of transactions to execute.
        """

        max_slippage = arguments[0]["max_slippage"] / 100
        fraction = validate_percentage(percentage)

        if amount_to_redeem is None:
            amount_to_redeem = get_amount_to_redeem_sdai(ctx, fraction)

        if amount_to_redeem == 0:
            return []

        if 'anvil' in ctx.w3.client_version:
            fork = True
        else:
            fork = False

        return cowswap.create_order_and_swap(w3=ctx.w3,
                                             avatar=ctx.avatar_safe_address,
                                             sell_token=ContractSpecs[ctx.blockchain].sDAI.address,
                                             buy_token=Addresses[ctx.blockchain].USDC,
                                             amount=amount_to_redeem,
                                             kind=cowswap.SwapKind.SELL,
                                             max_slippage=max_slippage,
                                             valid_duration=20 * 60,
                                             fork=fork)


operations = [
    Exit1,
    Exit2
]
