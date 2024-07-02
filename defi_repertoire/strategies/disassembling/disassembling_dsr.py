from decimal import Decimal
from defabipedia.maker import ContractSpecs
from roles_royce.generic_method import Transactable
from roles_royce.protocols.base import Address
from roles_royce.protocols.eth import maker

from ..base import (
    GenericTxContext,
    register,
    StrategyAmountArguments,
)


def get_amount_to_redeem(
    ctx: GenericTxContext, fraction: Decimal | float, proxy_address: Address = None
) -> int:
    pot_contract = ContractSpecs[ctx.blockchain].Pot.contract(ctx.w3)
    dsr_contract = ContractSpecs[ctx.blockchain].DsrManager.contract(ctx.w3)
    if proxy_address:
        pie = pot_contract.functions.pie(proxy_address).call()
    else:
        pie = dsr_contract.functions.pieOf(ctx.avatar_safe_address).call()
    chi = pot_contract.functions.chi().call() / (10**27)
    amount_to_redeem = pie * chi
    return int(Decimal(amount_to_redeem) * Decimal(fraction))


@register
class WithdrawWithProxy:
    """Withdraw DSR tokens from DSR with proxy."""

    kind = "disassembly"
    protocol = "dsr"
    name = "withdraw_with_proxy"

    @classmethod
    def get_txns(
        cls, ctx: GenericTxContext, arguments: StrategyAmountArguments
    ) -> list[Transactable]:
        txns = []
        proxy_registry = ContractSpecs[ctx.blockchain].ProxyRegistry.contract(ctx.w3)
        proxy_address = proxy_registry.functions.proxies(ctx.avatar_safe_address).call()

        approve_dai = maker.ApproveDAI(spender=proxy_address, amount=arguments.amount)
        exit_dai = maker.ProxyActionExitDsr(proxy=proxy_address, wad=arguments.amount)

        txns.append(approve_dai)
        txns.append(exit_dai)

        return txns


@register
class WithdrawWithoutProxy:
    """Withdraw funds from DSR without proxy."""

    kind = "disassembly"
    protocol = "dsr"
    name = "withdraw_without_proxy"

    @classmethod
    def get_txns(
        cls, ctx: GenericTxContext, arguments: StrategyAmountArguments
    ) -> list[Transactable]:
        txns = []
        dsr_manager_address = (
            ContractSpecs[ctx.blockchain].DsrManager.contract(ctx.w3).address
        )
        approve_dai = maker.ApproveDAI(spender=dsr_manager_address, amount=arguments.amount)
        exit_dai = maker.ExitDsr(avatar=ctx.avatar_safe_address, wad=arguments.amount)

        txns.append(approve_dai)
        txns.append(exit_dai)

        return txns
