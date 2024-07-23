from decimal import Decimal
from typing import Tuple

from defabipedia.balancer import Abis
from pydantic import BaseModel
from roles_royce.generic_method import Transactable
from roles_royce.protocols import balancer
from web3.exceptions import ContractLogicError

from ..base import Amount, ChecksumAddress, GenericTxContext, Percentage, register

# from roles_royce.protocols.base import Address


class Exit11ArgumentElement(BaseModel):
    bpt_address: ChecksumAddress
    max_slippage: Percentage
    amount: Amount


class Exit12ArgumemntElement(BaseModel):
    bpt_address: ChecksumAddress
    max_slippage: Percentage
    token_out_address: ChecksumAddress
    amount: Amount


class Exit13ArgumentElement(BaseModel):
    bpt_address: ChecksumAddress
    amount: Amount


class Exit21ArgumentElement(BaseModel):
    gauge_address: ChecksumAddress
    max_slippage: Percentage
    amount: Amount


class Exit22ArgumentElement(BaseModel):
    gauge_address: ChecksumAddress
    max_slippage: Percentage
    token_out_address: ChecksumAddress
    amount: Amount


class Exit23ArgumentElement(BaseModel):
    gauge_address: ChecksumAddress
    max_slippage: Percentage
    amount: Amount


def get_bpt_amount_to_redeem_from_gauge(
    ctx: GenericTxContext, gauge_address: ChecksumAddress, fraction: float | Decimal
) -> int:
    gauge_contract = ctx.w3.eth.contract(
        address=gauge_address, abi=Abis[ctx.blockchain].Gauge.abi
    )
    return int(
        Decimal(gauge_contract.functions.balanceOf(ctx.avatar_safe_address).call())
        * Decimal(fraction)
    )


def get_bpt_amount_to_redeem(
    ctx: GenericTxContext, bpt_address: ChecksumAddress, fraction: float | Decimal
) -> int:
    bpt_contract = ctx.w3.eth.contract(
        address=bpt_address, abi=Abis[ctx.blockchain].UniversalBPT.abi
    )

    return int(
        Decimal(bpt_contract.functions.balanceOf(ctx.avatar_safe_address).call())
        * Decimal(fraction)
    )


def get_contract_mode(ctx: GenericTxContext, bpt_address: ChecksumAddress) -> Tuple[bool, bool]:
    bpt_contract = ctx.w3.eth.contract(
        address=bpt_address, abi=Abis[ctx.blockchain].UniversalBPT.abi
    )
    paused = bpt_contract.functions.getPausedState().call()

    try:
        recovery = bpt_contract.functions.inRecoveryMode().call()
    except ContractLogicError:
        recovery = False

    return paused[0], recovery


@register
class WithdrawAllAssetsProportional:
    """
    Withdraw funds from the Balancer pool withdrawing all assets in proportional way (checks if pool is in recovery mode and acts accordingly).
    """

    kind = "disassembly"
    protocol = "balancer"
    name = "withdraw_all_assets_proportional"

    @classmethod
    def get_txns(
        cls, ctx: GenericTxContext, arguments: Exit11ArgumentElement
    ) -> list[Transactable]:

        txns = []

        bpt_address = arguments.bpt_address
        max_slippage = arguments.max_slippage / 100
        amount = arguments.amount

        bpt_contract = ctx.w3.eth.contract(
            address=bpt_address, abi=Abis[ctx.blockchain].UniversalBPT.abi
        )

        bpt_pool_id = "0x" + bpt_contract.functions.getPoolId().call().hex()

        paused, recovery = get_contract_mode(ctx, bpt_address)

        if paused:
            raise ValueError("Pool is in paused state, no withdrawing is accepted.")

        if recovery:
            withdraw_balancer = balancer.ExactBptRecoveryModeExit(
                w3=ctx.w3,
                pool_id=bpt_pool_id,
                avatar=ctx.avatar_safe_address,
                bpt_amount_in=amount,
            )

        else:
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

    kind = "disassembly"
    protocol = "balancer"
    name = "withdraw_single"

    @classmethod
    def get_txns(
        cls,
        ctx: GenericTxContext,
        arguments: Exit12ArgumemntElement,
    ) -> list[Transactable]:

        txns = []

        bpt_address = arguments.bpt_address
        max_slippage = arguments.max_slippage / 100
        token_out_address = arguments.token_out_address
        amount = arguments.amount

        bpt_contract = ctx.w3.eth.contract(
            address=bpt_address, abi=Abis[ctx.blockchain].UniversalBPT.abi
        )

        bpt_pool_id = "0x" + bpt_contract.functions.getPoolId().call().hex()
        paused, recovery = get_contract_mode(ctx, bpt_address)

        if paused:
            raise ValueError("Pool is in paused state, no withdrawing is accepted.")
        if recovery:
            raise ValueError(
                "This pool is in recovery mode, only proportional exit possible, try that option."
            )
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
class Exit21:
    """
    Unstake from gauge and withdraw funds from the Balancer pool withdrawing all assets
    in proportional way (checks if pool is in recovery mode and acts accordingly).
    """

    kind = "disassembly"
    protocol = "balancer"
    name = "exit_2_1"

    @classmethod
    def get_txns(
        cls, ctx: GenericTxContext, arguments: Exit21ArgumentElement
    ) -> list[Transactable]:

        txns = []
        gauge_address = arguments.gauge_address
        max_slippage = arguments.max_slippage / 100
        amount = arguments.amount

        unstake_gauge = balancer.UnstakeFromGauge(
            blockchain=ctx.blockchain,
            gauge_address=gauge_address,
            amount=amount,
        )
        txns.append(unstake_gauge)

        # gauge_address to bpt_address conversion
        gauge_contract = ctx.w3.eth.contract(
            address=gauge_address, abi=Abis[ctx.blockchain].Gauge.abi
        )
        bpt_address = str(gauge_contract.functions.lp_token().call())

        withdraw_balancer = WithdrawAllAssetsProportional.get_txns(
            ctx=ctx,
            arguments=Exit11ArgumentElement(
                **{
                    "bpt_address": bpt_address,
                    "max_slippage": max_slippage,
                    "amount": amount,
                }
            ),
        )
        for transactable in withdraw_balancer:
            txns.append(transactable)

        return txns


@register
class Exit22:
    """
    Unstake from gauge and withdraw funds from the Balancer pool withdrawing a single asset specified by the token index.
    """

    kind = "disassembly"
    protocol = "balancer"
    name = "exit_2_2"

    @classmethod
    def get_txns(
        cls, ctx: GenericTxContext, arguments: Exit22ArgumentElement
    ) -> list[Transactable]:

        txns = []

        gauge_address = arguments.gauge_address
        token_out_address = arguments.token_out_address
        amount = arguments.amount

        max_slippage = arguments.max_slippage / 100

        unstake_gauge = balancer.Unstake(
            w3=ctx.w3, gauge_address=gauge_address, amount=amount
        )
        txns.append(unstake_gauge)

        gauge_contract = ctx.w3.eth.contract(
            address=gauge_address, abi=Abis[ctx.blockchain].Gauge.abi
        )
        bpt_address = gauge_contract.functions.lp_token().call()

        withdraw_balancer = WithdrawSingle.get_txns(
            ctx=ctx,
            arguments=Exit12ArgumemntElement(
                **{
                    "bpt_address": bpt_address,
                    "token_out_address": token_out_address,
                    "max_slippage": max_slippage,
                    "amount": amount,
                }
            ),
        )
        for transactable in withdraw_balancer:
            txns.append(transactable)

        return txns
