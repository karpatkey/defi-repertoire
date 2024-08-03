from defabipedia import Chain
from defabipedia.lido import ContractSpecs
from roles_royce.generic_method import Transactable
from roles_royce.protocols.eth import lido

from ..base import GenericTxContext, StrategyAmountArguments, register


@register
class LidoUnstakeStETH:
    """
    Unstakes stETH from Lido
    """

    kind = "disassembly"
    protocol = "lido"
    id = "unstake_stETH"
    name = "Unstake stETH"
    chains = [Chain.ETHEREUM]

    @classmethod
    def get_txns(
        cls, ctx: GenericTxContext, arguments: StrategyAmountArguments
    ) -> list[Transactable]:
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

        return [set_allowance, request_withdrawal]


@register
class LidoUnwrapAndUnstakeWstETH:
    """
    Unwraps wstETH and unstakes for ETH on Lido
    """

    kind = "disassembly"
    protocol = "lido"
    id = "unwrap_and_unstake_wstETH"
    name = "Unwrap + Unstake wstETH"
    chains = [Chain.ETHEREUM]

    @classmethod
    def get_txns(
        cls, ctx: GenericTxContext, arguments: StrategyAmountArguments
    ) -> list[Transactable]:

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

        return [set_allowance, request_withdrawal]
