from dataclasses import dataclass
from decimal import Decimal
from defabipedia.maker import ContractSpecs
from roles_royce.generic_method import Transactable
from roles_royce.protocols.base import Address
from roles_royce.protocols.eth import maker

from .disassembler import GenericTxContext, validate_percentage


def get_amount_to_redeem(ctx: GenericTxContext, fraction: Decimal | float, proxy_address: Address = None) -> int:
    pot_contract = ContractSpecs[ctx.blockchain].Pot.contract(ctx.w3)
    dsr_contract = ContractSpecs[ctx.blockchain].DsrManager.contract(ctx.w3)
    if proxy_address:
        pie = pot_contract.functions.pie(proxy_address).call()
    else:
        pie = dsr_contract.functions.pieOf(ctx.avatar_safe_address).call()
    chi = pot_contract.functions.chi().call() / (10 ** 27)
    amount_to_redeem = pie * chi
    return int(Decimal(amount_to_redeem) * Decimal(fraction))

class WithdrawWithProxy:
    """Withdraw funds from DSR with proxy.

    Args:
        percentage (float): Percentage of liquidity to remove from DSR.
        exit_arguments (list[str]): List of DSR token addresses to withdraw from.
        amount_to_redeem (int, optional): Amount of DSR tokens to withdraw. Defaults to None.

    Returns
        list[Transactable]: List of transactions to exit DSR.
    """
    inputs = ["??"]
    outputs = ["DAI??"]
    op_type = WithdrawOperation

    @classmethod
    def get_txns(cls, ctx: GenericTxContext, percentage: float, exit_arguments: list[dict] = None,
                 amount_to_redeem: int = None) -> list[Transactable]:

            fraction = validate_percentage(percentage)

            txns = []

            proxy_registry = ContractSpecs[ctx.blockchain].ProxyRegistry.contract(ctx.w3)
            proxy_address = proxy_registry.functions.proxies(ctx.avatar_safe_address).call()

            if amount_to_redeem is None:
                amount_to_redeem = get_amount_to_redeem(ctx, fraction, proxy_address)

            approve_dai = maker.ApproveDAI(spender=proxy_address, amount=amount_to_redeem)
            exit_dai = maker.ProxyActionExitDsr(proxy=proxy_address, wad=amount_to_redeem)

            txns.append(approve_dai)
            txns.append(exit_dai)

            return txns

class WithdrawWithProxy:
    """Withdraw funds from DSR without proxy.

    Args:
        percentage (float): Percentage of liquidity to remove from DSR.
        exit_arguments (list[str]): List of DSR token addresses to withdraw from.
        amount_to_redeem (int, optional): Amount of DSR tokens to withdraw. Defaults to None.

    Returns
        list[Transactable]: List of transactions to exit DSR.
    """
    inputs = ["?? DSR TOKENS ?"]
    outputs = ["DAI??"]
    op_type = WithdrawOperation
    @classmethod
    def get_txns(cls, ctx: GenericTxContext, percentage: float, exit_arguments: list[dict] = None,
                 amount_to_redeem: int = None) -> list[Transactable]:

        fraction = validate_percentage(percentage)

        txns = []

        if amount_to_redeem is None:
            amount_to_redeem = get_amount_to_redeem(ctx, fraction, proxy_address=None)
        dsr_manager_address = ContractSpecs[ctx.blockchain].DsrManager.contract(ctx.w3).address
        approve_dai = maker.ApproveDAI(spender=dsr_manager_address, amount=amount_to_redeem)
        exit_dai = maker.ExitDsr(avatar=ctx.avatar_safe_address, wad=amount_to_redeem)

        txns.append(approve_dai)
        txns.append(exit_dai)

        return txns
