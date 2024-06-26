from dataclasses import dataclass
from decimal import Decimal
from defabipedia.lido import ContractSpecs
from defabipedia.tokens import EthereumTokenAddr
from roles_royce.generic_method import Transactable
from roles_royce.protocols.base import Address
from roles_royce.protocols import cowswap
from roles_royce.protocols.eth import lido
from .disassembling_swaps import SwapCurve

from .disassembler import UnstakeOperation, UnwrapOperation, SwapOperation, validate_percentage, GenericTxContext


def get_amount_to_redeem(ctx: GenericTxContext, address: Address, fraction: float | Decimal) -> int:
    """
    Calculates the amount of tokens to redeem based on the percentage of the total holdings.

    Args:
        address (Address): Token address; can be stETH or wstETH.
        fraction (float): Percentage of the total holdings to redeem.

    Returns:
        int: Amount of tokens to redeem.
    """
    if address == ContractSpecs[ctx.blockchain].wstETH.address:
        contract = ContractSpecs[ctx.blockchain].wstETH.contract(ctx.w3)
    elif address == ContractSpecs[ctx.blockchain].stETH.address:
        contract = ContractSpecs[ctx.blockchain].stETH.contract(ctx.w3)
    else:
        raise ValueError("Invalid token address")

    return int(Decimal(contract.functions.balanceOf(ctx.avatar_safe_address).call()) * Decimal(fraction))


class LidoUnstakeStETH:
    inputs = ["stETH"]
    outputs = ["ETH"]  # is ETH the output? or there is a wait period?
    op_type = UnstakeOperation

    @classmethod
    def get_txns(cls, ctx: GenericTxContext, percentage: float, arguments: list[dict] = None,
                 amount_to_redeem: int = None) -> list[Transactable]:
        """
        Unstakes stETH from Lido

        Args:
            percentage (float): Percentage of the total stETH holdings to redeem.
            amount_to_redeem (int, optional):Amount of stETH to redeem. Defaults to None. If None, the 'percentage' of
                the balance of stETH will be redeemed.

        Returns:
            list[Transactable]: List of transactions to execute.
        """

        fraction = validate_percentage(percentage)

        txns = []
        address = ContractSpecs[ctx.blockchain].stETH.address

        if amount_to_redeem is None:
            amount_to_redeem = get_amount_to_redeem(ctx, address, fraction)

        chunk_amount = amount_to_redeem
        if chunk_amount > 1000_000_000_000_000_000_000:
            chunks = []
            while chunk_amount >= 1000_000_000_000_000_000_000:
                chunks.append(1000_000_000_000_000_000_000)
                chunk_amount -= 1000_000_000_000_000_000_000
            if chunk_amount > 0:
                chunks.append(chunk_amount)

            set_allowance = lido.ApproveWithdrawalStETHWithUnstETH(amount=amount_to_redeem)
            request_withdrawal = lido.RequestWithdrawalsStETH(amounts=chunks, avatar=ctx.avatar_safe_address)

        else:
            set_allowance = lido.ApproveWithdrawalStETHWithUnstETH(amount=amount_to_redeem)
            request_withdrawal = lido.RequestWithdrawalsStETH(
                amounts=[amount_to_redeem], avatar=ctx.avatar_safe_address
            )

        txns.append(set_allowance)
        txns.append(request_withdrawal)
        return txns


class LidoUnwrapAndUnstakeWstETH:
    inputs = ["wstETH"]
    outputs = ["ETH"]  # is ETH the output? or there is a wait period?
    op_type = UnwrapOperation  # ??

    @classmethod
    def get_txns(cls, ctx: GenericTxContext, percentage: float, arguments: list[dict] = None,
                 amount_to_redeem: int = None) -> list[Transactable]:

        """
        Unwraps wstETH and unstakes for ETH on Lido

        Args:
            percentage (float): Percentage of the total wstETH holdings to redeem.
            amount_to_redeem (int, optional): Amount of wstETH to redeem. Defaults to None. If None, the 'percentage' of the balance of stETH will be redeemed.

        Returns:
            list[Transactable]: List of transactions to execute.
        """

        fraction = validate_percentage(percentage)

        txns = []
        address = ContractSpecs[ctx.blockchain].wstETH.address

        if amount_to_redeem is None:
            amount_to_redeem = get_amount_to_redeem(ctx, address, fraction)
        contract = ContractSpecs[ctx.blockchain].wstETH.contract(ctx.w3)
        amount_for_list = contract.functions.getWstETHByStETH(
            1_000_000_000_000_000_000_000).call()  # just to be safe that the chunk size is too big
        chunk_amount = amount_to_redeem
        if chunk_amount > amount_for_list:
            chunks = []
            while chunk_amount >= amount_for_list:
                chunks.append(amount_for_list)
                chunk_amount -= amount_for_list
            if chunk_amount > 0:
                chunks.append(chunk_amount)

            set_allowance = lido.ApproveWithdrawalWstETH(amount=amount_to_redeem)
            request_withdrawal = lido.RequestWithdrawalsWstETH(amounts=chunks, avatar=ctx.avatar_safe_address)

        else:
            set_allowance = lido.ApproveWithdrawalWstETH(amount=amount_to_redeem)
            request_withdrawal = lido.RequestWithdrawalsWstETH(
                amounts=[amount_to_redeem], avatar=ctx.avatar_safe_address
            )

        txns.append(set_allowance)
        txns.append(request_withdrawal)
        return txns


class SwapStETHforETH:  # TODO: why to have a specific class ?
    """
    Swaps stETH for ETH. Approves the Cowswap relayer to spend the stETH if needed, then creates the order using the
    Cow's order API and creates the sign_order transaction.
    Args:
        percentage (float): Percentage of the total stETH holdings to swap.
        arguments (list[dict]):  List with one single dictionary with the order parameters from an already
         created order:
            arg_dicts = [
                {
                    "max_slippage": 11.25
                }
            ]
        amount_to_redeem (int, optional): Amount of stETH to swap. Defaults to None. If None, the 'percentage' of
            the total stETH holdings are swapped
    Returns:
        list[ Transactable]: List of transactions to execute
    """
    inputs = ["wstETH"]
    outputs = ["ETH"]
    op_type = SwapOperation

    @classmethod
    def get_txns(cls, ctx: GenericTxContext, percentage: float, arguments: list[dict] = None,
                 amount_to_redeem: int = None) -> list[Transactable]:

        max_slippage = arguments[0]["max_slippage"] / 100
        fraction = validate_percentage(percentage)

        if amount_to_redeem is None:
            amount_to_redeem = get_amount_to_redeem(ctx, EthereumTokenAddr.stETH, fraction)

        if amount_to_redeem == 0:
            return []

        if 'anvil' in ctx.w3.client_version:
            fork = True
        else:
            fork = False

        return cowswap.create_order_and_swap(w3=ctx.w3,
                                             avatar=ctx.avatar_safe_address,
                                             sell_token=EthereumTokenAddr.stETH,
                                             buy_token=EthereumTokenAddr.E,
                                             amount=amount_to_redeem,
                                             kind=cowswap.SwapKind.SELL,
                                             max_slippage=max_slippage,
                                             valid_duration=20 * 60,
                                             fork=fork)


class CurveSwap:
    inputs = ["wstETH"]
    outputs = ["ETH"]
    op_type = SwapOperation

    @classmethod
    def get_txns(cls, ctx: GenericTxContext, percentage: float, arguments: list[dict] = None,
                 amount_to_redeem: int = None) -> list[Transactable]:
        """Make a swap on Curve with wsteth to ETH
        Args:
            percentage (float): Percentage of token to remove.
            arguments (list[dict], optional): List of dictionaries with the withdrawal parameters.
                arg_dicts = [
                    {
                        "token_in_address: "FillMewithTokenAddress",
                        "max_slippage": 0.01,
                        "token_out_address": "FillMewithTokenAddress"
                    }
                ]
            amount_to_redeem (int, optional): Amount of wallet token to redeem. Defaults to None.
        Returns:
            list[ Transactable]:  List of transactions to execute.
        """
        txns = SwapCurve.get_txns(
            ctx=ctx,
            percentage=percentage,
            arguments=arguments,
            amount_to_redeem=amount_to_redeem
        )

        return txns


operations = [
    LidoUnstakeStETH,
    LidoUnwrapAndUnstakeWstETH,
    CurveSwap,
    SwapStETHforETH,
]
