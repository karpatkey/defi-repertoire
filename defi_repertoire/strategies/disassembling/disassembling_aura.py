from decimal import Decimal

from defabipedia.aura import Abis
from pydantic import BaseModel
from web3.types import ChecksumAddress

from roles_royce.generic_method import Transactable
from roles_royce.protocols.eth import aura

from roles_royce.utils import to_checksum_address
from ..base import GenericTxContext, WithdrawOperation
from . import disassembling_balancer as balancer
from defi_repertoire.strategies import register


class Exit1ArgumentElement(BaseModel):
    rewards_address: str
    amount: int


class Exit21ArgumentElement(BaseModel):
    rewards_address: str
    max_slippage: float
    amount: int


class Exit22ArgumentElement(BaseModel):
    rewards_address: str
    max_slippage: float
    token_out_address: str
    amount: int


def aura_contracts_helper(
        ctx: GenericTxContext,
        aura_rewards_address: ChecksumAddress,
        fraction: float | Decimal,
) -> (str, int):
    aura_rewards_contract = ctx.w3.eth.contract(
        address=aura_rewards_address, abi=Abis[ctx.blockchain].BaseRewardPool.abi
    )
    aura_token_amount = aura_rewards_contract.functions.balanceOf(
        ctx.avatar_safe_address
    ).call()
    bpt_address = aura_rewards_contract.functions.asset().call()

    amount_to_redeem = int(Decimal(aura_token_amount) * Decimal(fraction))

    return bpt_address, amount_to_redeem


def aura_to_bpt_address(
        ctx: GenericTxContext, aura_rewards_address: ChecksumAddress
) -> str:
    aura_rewards_contract = ctx.w3.eth.contract(
        address=aura_rewards_address, abi=Abis[ctx.blockchain].BaseRewardPool.abi
    )
    return aura_rewards_contract.functions.asset().call()


@register
class Withdraw:
    """Withdraw funds from Aura."""

    op_type = WithdrawOperation
    kind = "disassembly"
    protocol = "aura"
    name = "exit_1"

    @classmethod
    def get_txns(
            cls, ctx: GenericTxContext, arguments: Exit1ArgumentElement
    ) -> list[Transactable]:
        txns = []
        aura_rewards_address = to_checksum_address(arguments.rewards_address)
        bpt_address = aura_to_bpt_address(ctx, aura_rewards_address)
        ctx.ctx["aura"]["aura_to_bpt"][aura_rewards_address] = bpt_address

        withdraw_aura = aura.WithdrawAndUndwrapStakedBPT(
            reward_address=aura_rewards_address, amount=arguments.amount
        )
        txns.append(withdraw_aura)

        return txns


@register
class Withdraw2:
    """Withdraw funds from Aura and then from the Balancer pool withdrawing all assets in proportional way
    (not used for pools in recovery mode!).
    """

    op_type = WithdrawOperation
    kind = "disassembly"
    protocol = "aura"
    name = "exit_2_1"

    @classmethod
    def get_txns(
            cls, ctx: GenericTxContext, arguments: Exit21ArgumentElement
    ) -> list[Transactable]:
        txns = []
        amount = arguments.amount
        if amount == 0:
            return txns

        aura_reward_address = to_checksum_address(arguments.rewards_address)
        aura_txns = Withdraw.get_txns(
            ctx,
            arguments=Exit1ArgumentElement(**{"rewards_address": aura_reward_address, "amount": amount}),
        )
        txns.extend(aura_txns)

        bpt_address = ctx.ctx["aura"]["aura_to_bpt"][aura_reward_address]

        bal_txns = balancer.WithdrawAllAssetsProportional.get_txns(
            ctx=ctx,
            arguments=balancer.Exit11ArgumentElement(**
                                                     {
                                                         "bpt_address": bpt_address,
                                                         "max_slippage": arguments.max_slippage,
                                                         "amount": amount,
                                                     }
                                                     )
        )
        txns.extend(bal_txns)

        return txns


@register
class Exit22:
    """Withdraw funds from Aura and then from the Balancer pool withdrawing a single asset specified by the
    token index.
    """

    op_type = WithdrawOperation
    kind = "disassembly"
    protocol = "aura"
    name = "exit_2_2"

    @classmethod
    def get_txns(
            cls, ctx: GenericTxContext, arguments: Exit22ArgumentElement
    ) -> list[Transactable]:

        txns = []

        aura_rewards_address = to_checksum_address(arguments.rewards_address)
        max_slippage = arguments.max_slippage
        token_out_address = to_checksum_address(arguments.token_out_address)
        amount = arguments.amount

        bpt_address = aura_to_bpt_address(ctx, aura_rewards_address)

        if amount == 0:
            return txns

        withdraw_aura = aura.WithdrawAndUndwrapStakedBPT(
            reward_address=aura_rewards_address, amount=amount
        )

        withdraw_balancer = balancer.WithdrawSingle.get_txns(ctx=ctx,
                                                             arguments=balancer.Exit12ArgumemntElement(**
                                                                                                       {
                                                                                                           "bpt_address": bpt_address,
                                                                                                           "max_slippage": max_slippage,
                                                                                                           "token_out_address": token_out_address,
                                                                                                           "amount": amount,
                                                                                                       }
                                                                                                       )
                                                             )

        txns.append(withdraw_aura)
        for transactable in withdraw_balancer:
            txns.append(transactable)

        return txns


# Original Contracts Payloads [(Withdraw, Allow, ...)]

# Multisend()

# Roles Modifier Contract (Roles: execTransactionWithRole, role, role_mod_address) -> execution_service


@register
class Exit23:
    """Withdraw funds from Aura and then from the Balancer pool withdrawing all assets in proportional way when
    pool is in recovery mode.
    """

    op_type = WithdrawOperation
    kind = "disassembly"
    protocol = "aura"
    name = "exit_2_3"

    @classmethod
    def get_txns(
            cls, ctx: GenericTxContext, arguments: Exit1ArgumentElement
    ) -> list[Transactable]:
        txns = []
        if arguments.amount == 0:
            return txns

        aura_rewards_address = to_checksum_address(arguments.rewards_address)

        bpt_address = aura_to_bpt_address(ctx, aura_rewards_address)

        withdraw_aura = aura.WithdrawAndUndwrapStakedBPT(
            reward_address=aura_rewards_address, amount=arguments.amount
        )

        withdraw_balancer = (
            balancer.WithdrawAllAssetsProportionalPoolsInRecovery.get_txns(
                ctx=ctx, arguments=balancer.Exit13ArgumentElement(**{"bpt_address": bpt_address, "amount": arguments.amount})
            )
        )

        txns.append(withdraw_aura)
        for transactable in withdraw_balancer:
            txns.append(transactable)

        return txns
