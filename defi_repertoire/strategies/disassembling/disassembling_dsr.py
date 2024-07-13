from decimal import Decimal

from defabipedia.maker import ContractSpecs
from roles_royce.generic_method import Transactable
from roles_royce.protocols.base import Address
from roles_royce.protocols.eth import maker

from ..base import GenericTxContext, StrategyAmountArguments, register


@register
class WithdrawWithProxy:
    """Withdraw DSR tokens from DSR with proxy."""

    kind = "disassembly"
    protocol = "dsr"
    id = "withdraw_with_proxy"
    name = "Withdraw with Proxy"

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
    id = "withdraw_without_proxy"
    name = "Withdraw without Proxy"

    @classmethod
    def get_txns(
        cls, ctx: GenericTxContext, arguments: StrategyAmountArguments
    ) -> list[Transactable]:
        txns = []
        dsr_manager_address = (
            ContractSpecs[ctx.blockchain].DsrManager.contract(ctx.w3).address
        )
        approve_dai = maker.ApproveDAI(
            spender=dsr_manager_address, amount=arguments.amount
        )
        exit_dai = maker.ExitDsr(avatar=ctx.avatar_safe_address, wad=arguments.amount)

        txns.append(approve_dai)
        txns.append(exit_dai)

        return txns
