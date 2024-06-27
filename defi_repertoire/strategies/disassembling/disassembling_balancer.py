from decimal import Decimal
from typing import Optional

from defabipedia.balancer import Abis
from typing_extensions import TypedDict
from web3.exceptions import ContractLogicError

from roles_royce.generic_method import Transactable
from roles_royce.protocols import balancer
from roles_royce.protocols.base import Address
from roles_royce.utils import to_checksum_address

from ..base import GenericTxContext, WithdrawOperation, register


class Exit11ArgumentElement(TypedDict):
    bpt_address: str
    max_slippage: float
    amount: int


class Exit12ArgumemntElement(TypedDict):
    bpt_address: str
    max_slippage: float
    token_out_address: str
    amount: int


class Exit13ArgumentElement(TypedDict):
    bpt_address: str
    amount: int


class Exit21ArgumentElement(TypedDict):
    gauge_address: str
    max_slippage: float
    amount: int


class Exit22ArgumentElement(TypedDict):
    gauge_address: str
    max_slippage: float
    token_out_address: str
    amount: int


class Exit23ArgumentElement(TypedDict):
    gauge_address: str
    max_slippage: float
    amount: int


def get_bpt_amount_to_redeem_from_gauge(ctx: GenericTxContext, gauge_address: Address,
                                        fraction: float | Decimal) -> int:
    gauge_contract = ctx.w3.eth.contract(address=gauge_address, abi=Abis[ctx.blockchain].Gauge.abi)
    return int(Decimal(gauge_contract.functions.balanceOf(ctx.avatar_safe_address).call()) * Decimal(fraction))


def get_bpt_amount_to_redeem(ctx: GenericTxContext, bpt_address: Address, fraction: float | Decimal) -> int:
    bpt_contract = ctx.w3.eth.contract(address=bpt_address, abi=Abis[ctx.blockchain].UniversalBPT.abi)

    return int(Decimal(bpt_contract.functions.balanceOf(ctx.avatar_safe_address).call()) * Decimal(fraction))


@register
class WithdrawAllAssetsProportional:
    """
    Withdraw funds from the Balancer pool withdrawing all assets in proportional way (not used for pools in recovery mode!).
    """
    op_type = WithdrawOperation
    kind = "disassembly"
    protocol = "balancer"

    @classmethod
    def get_txns(cls, ctx: GenericTxContext, arguments: list[Exit11ArgumentElement]) -> list[Transactable]:

        txns = []

        for element in arguments:
            bpt_address = to_checksum_address(element["bpt_address"])
            max_slippage = element["max_slippage"] / 100
            amount = element["amount"]
            if amount == 0:
                continue

            bpt_contract = ctx.w3.eth.contract(address=bpt_address, abi=Abis[ctx.blockchain].UniversalBPT.abi)

            bpt_pool_id = "0x" + bpt_contract.functions.getPoolId().call().hex()
            bpt_pool_paused_state = bpt_contract.functions.getPausedState().call()
            # TODO: Not all pools have recovery mode, the following has to be improved
            try:
                bpt_pool_recovery_mode = bpt_contract.functions.inRecoveryMode().call()
            except ContractLogicError:
                bpt_pool_recovery_mode = False

            if bpt_pool_paused_state[0]:
                raise ValueError("Pool is in paused state, no withdrawing is accepted.")
            if bpt_pool_recovery_mode:
                raise ValueError(
                    "This pool is in recovery mode, only proportional recovery mode exit possible, try that option."
                )

            withdraw_balancer = balancer.ExactBptProportionalExitSlippage(
                w3=ctx.w3,
                pool_id=bpt_pool_id,
                avatar=ctx.avatar_safe_address,
                bpt_amount_in=amount,
                max_slippage=max_slippage,
            )
            txns.append(withdraw_balancer)
        return txns


@register
class WithdrawSingle:
    """
    Withdraw funds from the Balancer pool withdrawing a single asset specified by the token index.
    """
    op_type = WithdrawOperation
    kind = "disassembly"
    protocol = "balancer"

    @classmethod
    def get_txns(cls, ctx: GenericTxContext, arguments: list[Exit12ArgumemntElement],
                 ) -> list[Transactable]:

        txns = []

        for element in arguments:
            bpt_address = to_checksum_address(element["bpt_address"])
            max_slippage = element["max_slippage"] / 100
            token_out_address = to_checksum_address(element["token_out_address"])
            amount = element["amount"]

            bpt_contract = ctx.w3.eth.contract(address=bpt_address, abi=Abis[ctx.blockchain].UniversalBPT.abi)

            if amount == 0:
                continue

            bpt_pool_id = "0x" + bpt_contract.functions.getPoolId().call().hex()
            bpt_pool_paused_state = bpt_contract.functions.getPausedState().call()
            # TODO: Not all pools have recovery mode, the following has to be improved
            try:
                bpt_pool_recovery_mode = bpt_contract.functions.inRecoveryMode().call()
            except ContractLogicError:
                bpt_pool_recovery_mode = False

            if bpt_pool_paused_state[0]:
                raise ValueError("Pool is in paused state, no withdrawing is accepted.")
            if bpt_pool_recovery_mode:
                raise ValueError("This pool is in recovery mode, only proportional exit possible, try that option.")
            withdraw_balancer = balancer.ExactBptSingleTokenExitSlippage(
                w3=ctx.w3,
                pool_id=bpt_pool_id,
                avatar=ctx.avatar_safe_address,
                bpt_amount_in=amount,
                token_out_address=token_out_address,
                max_slippage=max_slippage,
            )
            txns.append(withdraw_balancer)
        return txns


@register
class WithdrawAllAssetsProportionalPoolsInRecovery:
    """
    Withdraw funds from the Balancer pool withdrawing all assets in proportional way for pools in recovery mode.
    """
    op_type = WithdrawOperation
    kind = "disassembly"
    protocol = "balancer"

    @classmethod
    def get_txns(cls, ctx: GenericTxContext, arguments: list[Exit13ArgumentElement],
                 ) -> list[Transactable]:

        txns = []
        for element in arguments:
            bpt_address = to_checksum_address(element["bpt_address"])
            amount = element["amount"]
            if amount == 0:
                continue

            bpt_contract = ctx.w3.eth.contract(address=bpt_address, abi=Abis[ctx.blockchain].UniversalBPT.abi)

            try:
                bpt_pool_recovery_mode = bpt_contract.functions.inRecoveryMode().call()
            except ContractLogicError:
                bpt_pool_recovery_mode = False
            if bpt_pool_recovery_mode is False:
                raise ValueError("This pool is not in recovery mode.")

            bpt_pool_id = "0x" + bpt_contract.functions.getPoolId().call().hex()

            withdraw_balancer = balancer.ExactBptRecoveryModeExit(
                w3=ctx.w3, pool_id=bpt_pool_id, avatar=ctx.avatar_safe_address, bpt_amount_in=amount
            )

            txns.append(withdraw_balancer)

        return txns


@register
class Exit21:
    """
    Unstake from gauge and withdraw funds from the Balancer pool withdrawing all assets
    in proportional way (not used for pools in recovery mode!).
    """
    op_type = WithdrawOperation  # unstake ? ??
    kind = "disassembly"
    protocol = "balancer"

    @classmethod
    def get_txns(cls, ctx: GenericTxContext, arguments: list[Exit21ArgumentElement]) -> list[Transactable]:
        txns = []
        for element in arguments:
            gauge_address = to_checksum_address(element["gauge_address"])
            max_slippage = element["max_slippage"] / 100
            amount = element["amount"]
            if amount == 0:
                continue

            unstake_gauge = balancer.UnstakeFromGauge(
                blockchain=ctx.blockchain,
                gauge_address=gauge_address,
                amount=amount,
            )
            txns.append(unstake_gauge)

            # gauge_address to bpt_address conversion
            gauge_contract = ctx.w3.eth.contract(address=gauge_address, abi=Abis[ctx.blockchain].Gauge.abi)
            bpt_address = gauge_contract.functions.lp_token().call()

            withdraw_balancer = WithdrawAllAssetsProportional.get_txns(ctx=ctx,
                                                                       arguments=[{"bpt_address": bpt_address,
                                                                                   "max_slippage": max_slippage,
                                                                                   "amount": amount}],
                                                                       )
            for transactable in withdraw_balancer:
                txns.append(transactable)

        return txns


@register
class Exit22:
    """
    Unstake from gauge and withdraw funds from the Balancer pool withdrawing a single asset specified by the token index.
    """
    op_type = WithdrawOperation  # unstake ? ??
    kind = "disassembly"
    protocol = "balancer"

    @classmethod
    def get_txns(cls, ctx: GenericTxContext, arguments: list[Exit22ArgumentElement]) -> list[Transactable]:

        txns = []
        for element in arguments:
            gauge_address = to_checksum_address(element["gauge_address"])
            token_out_address = to_checksum_address(element["token_out_address"])
            amount = element["amount"]

            max_slippage = element["max_slippage"] / 100

            if amount == 0:
                continue

            unstake_gauge = balancer.Unstake(w3=ctx.w3, gauge_address=gauge_address, amount=amount)
            txns.append(unstake_gauge)

            gauge_contract = ctx.w3.eth.contract(address=gauge_address, abi=Abis[ctx.blockchain].Gauge.abi)
            bpt_address = gauge_contract.functions.lp_token().call()

            withdraw_balancer = WithdrawSingle.get_txns(
                ctx=ctx,
                arguments=[
                    {"bpt_address": bpt_address, "token_out_address": token_out_address, "max_slippage": max_slippage, "amount": amount}
                ],
            )
            for transactable in withdraw_balancer:
                txns.append(transactable)

        return txns


@register
class Exit23:
    """
    Unstake from gauge and withdraw funds from the Balancer pool withdrawing all assets
    in proportional way for pools in recovery mode.
    """

    op_type = WithdrawOperation  # unstake ? ??
    kind = "disassembly"
    protocol = "balancer"

    @classmethod
    def get_txns(cls, ctx: GenericTxContext, arguments: list[Exit23ArgumentElement]) -> list[Transactable]:
        txns = []
        for element in arguments:
            gauge_address = to_checksum_address(element["gauge_address"])
            amount = element["amount"]

            if amount == 0:
                return []

            unstake_gauge = balancer.Unstake(w3=ctx.w3, gauge_address=gauge_address, amount=amount)
            txns.append(unstake_gauge)

            gauge_contract = ctx.w3.eth.contract(address=gauge_address, abi=Abis[ctx.blockchain].Gauge.abi)
            bpt_address = gauge_contract.functions.lp_token().call()

            withdraw_balancer = WithdrawAllAssetsProportionalPoolsInRecovery.get_txns(
                ctx=ctx,
                arguments=[{"bpt_address": bpt_address, "amount": amount}]
            )
            for transactable in withdraw_balancer:
                txns.append(transactable)

        return txns
