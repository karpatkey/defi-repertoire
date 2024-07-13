from decimal import Decimal

from defabipedia.lido import ContractSpecs
from defabipedia.tokens import EthereumTokenAddr
from roles_royce.generic_method import Transactable
from roles_royce.protocols import cowswap
from roles_royce.protocols.base import Address
from roles_royce.protocols.eth import lido

from ..base import (
    GenericTxContext,
    StrategyAmountArguments,
    StrategyAmountWithSlippageArguments,
    register,
)


@register
class LidoUnstakeStETH:
    """
    Unstakes stETH from Lido
    """

    kind = "disassembly"
    protocol = "lido"
    id = "unstake_stETH"
    name = "Unstake stETH"

    @classmethod
    def get_txns(
        cls, ctx: GenericTxContext, arguments: StrategyAmountArguments
    ) -> list[Transactable]:
        txns = []
        amount_to_redeem = arguments.amount
        chunk_amount = amount_to_redeem
        if chunk_amount > 1000_000_000_000_000_000_000:
            chunks = []
            while chunk_amount >= 1000_000_000_000_000_000_000:
                chunks.append(1000_000_000_000_000_000_000)
                chunk_amount -= 1000_000_000_000_000_000_000
            if chunk_amount > 0:
                chunks.append(chunk_amount)

            set_allowance = lido.ApproveWithdrawalStETHWithUnstETH(
                amount=amount_to_redeem
            )
            request_withdrawal = lido.RequestWithdrawalsStETH(
                amounts=chunks, avatar=ctx.avatar_safe_address
            )

        else:
            set_allowance = lido.ApproveWithdrawalStETHWithUnstETH(
                amount=amount_to_redeem
            )
            request_withdrawal = lido.RequestWithdrawalsStETH(
                amounts=[amount_to_redeem], avatar=ctx.avatar_safe_address
            )

        txns.append(set_allowance)
        txns.append(request_withdrawal)
        return txns


@register
class LidoUnwrapAndUnstakeWstETH:
    """
    Unwraps wstETH and unstakes for ETH on Lido
    """

    kind = "disassembly"
    protocol = "lido"
    id = "unwrap_and_unstake_wstETH"
    name = "Unwrap + Unstake wstETH"

    @classmethod
    def get_txns(
        cls, ctx: GenericTxContext, arguments: StrategyAmountArguments
    ) -> list[Transactable]:
        txns = []

        contract = ContractSpecs[ctx.blockchain].wstETH.contract(ctx.w3)
        amount_for_list = contract.functions.getWstETHByStETH(
            1_000_000_000_000_000_000_000
        ).call()  # just to be safe that the chunk size is too big
        amount_to_redeem = arguments.amount
        chunk_amount = amount_to_redeem
        if chunk_amount > amount_for_list:
            chunks = []
            while chunk_amount >= amount_for_list:
                chunks.append(amount_for_list)
                chunk_amount -= amount_for_list
            if chunk_amount > 0:
                chunks.append(chunk_amount)

            set_allowance = lido.ApproveWithdrawalWstETH(amount=amount_to_redeem)
            request_withdrawal = lido.RequestWithdrawalsWstETH(
                amounts=chunks, avatar=ctx.avatar_safe_address
            )

        else:
            set_allowance = lido.ApproveWithdrawalWstETH(amount=amount_to_redeem)
            request_withdrawal = lido.RequestWithdrawalsWstETH(
                amounts=[amount_to_redeem], avatar=ctx.avatar_safe_address
            )

        txns.append(set_allowance)
        txns.append(request_withdrawal)
        return txns


@register
class SwapStETHforETH:  # TODO: why to have a specific class ?
    """
    Swaps stETH for ETH. Approves the Cowswap relayer to spend the stETH if needed, then creates the order using the
    Cow's order API and creates the sign_order transaction.
    """

    kind = "disassembly"
    protocol = "lido"
    id = "swap_stETH_for_ETH"
    name = "Swap stETH for ETH"

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
            sell_token=EthereumTokenAddr.stETH,
            buy_token=EthereumTokenAddr.E,
            amount=amount,
            kind=cowswap.SwapKind.SELL,
            max_slippage=max_slippage,
            valid_duration=20 * 60,
            fork=fork,
        )
