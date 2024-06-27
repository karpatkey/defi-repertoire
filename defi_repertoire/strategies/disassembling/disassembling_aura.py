from decimal import Decimal

from defabipedia.aura import Abis
from typing_extensions import TypedDict
from web3.types import ChecksumAddress

from roles_royce.generic_method import Transactable
from roles_royce.protocols.eth import aura

from roles_royce.utils import to_checksum_address
from ..base import GenericTxContext, WithdrawOperation
from . import disassembling_balancer as balancer
from defi_repertoire.strategies import register


class Exit1ArgumentElement(TypedDict):
    rewards_address: str
    amount: int


class Exit21ArgumentElement(TypedDict):
    rewards_address: str
    max_slippage: float
    amount: int


class Exit22ArgumentElement(TypedDict):
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

    @classmethod
    def get_txns(
        cls, ctx: GenericTxContext, arguments: list[Exit1ArgumentElement]
    ) -> list[Transactable]:

        txns = []
        for element in arguments:
            aura_rewards_address = to_checksum_address(element["rewards_address"])

            bpt_address = aura_to_bpt_address(ctx, aura_rewards_address)
            ctx.ctx["aura"]["aura_to_bpt"][aura_rewards_address] = bpt_address
            if element["amount"] == 0:
                continue
            withdraw_aura = aura.WithdrawAndUndwrapStakedBPT(
                reward_address=aura_rewards_address, amount=element["amount"]
            )
            txns.append(withdraw_aura)

        return txns


@register
class Withdraw2:
    """Withdraw funds from Aura and then from the Balancer pool withdrawing all assets in proportional way
    (not used for pools in recovery mode!).
    """

    op_type = WithdrawOperation
    name = "widraw_aura_balancer"
    kind = "disassembly"
    protocol = "aura"

    @classmethod
    def get_txns(
        cls, ctx: GenericTxContext, arguments: list[Exit21ArgumentElement]
    ) -> list[Transactable]:

        txns = []

        for element in arguments:
            amount = element["amount"]
            if amount == 0:
                continue

            aura_reward_address = to_checksum_address(element["rewards_address"])
            aura_txns = Withdraw.get_txns(
                ctx,
                arguments=[{"rewards_address": aura_reward_address, "amount": amount}],
            )
            txns.extend(aura_txns)

            max_slippage = element["max_slippage"]

            bpt_address = ctx.ctx["aura"]["aura_to_bpt"][aura_reward_address]

            bal_txns = balancer.WithdrawAllAssetsProportional.get_txns(
                ctx=ctx,
                arguments=[
                    {
                        "bpt_address": bpt_address,
                        "max_slippage": max_slippage,
                        "amount": amount,
                    }
                ],
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

    @classmethod
    def get_txns(
        cls, ctx: GenericTxContext, arguments: list[Exit22ArgumentElement]
    ) -> list[Transactable]:

        txns = []

        for element in arguments:
            aura_rewards_address = to_checksum_address(element["rewards_address"])
            max_slippage = element["max_slippage"]
            token_out_address = to_checksum_address(element["token_out_address"])
            amount = element["amount"]

            bpt_address = aura_to_bpt_address(ctx, aura_rewards_address)

            if amount == 0:
                continue

            withdraw_aura = aura.WithdrawAndUndwrapStakedBPT(
                reward_address=aura_rewards_address, amount=amount
            )

            withdraw_balancer = balancer.WithdrawSingle.get_txns(
                arguments=[
                    {
                        "bpt_address": bpt_address,
                        "max_slippage": max_slippage,
                        "token_out_address": token_out_address,
                        "amount": amount,
                    }
                ],
            )

            txns.append(withdraw_aura)
            for transactable in withdraw_balancer:
                txns.append(transactable)

        return txns


@register
class Exit23:
    """Withdraw funds from Aura and then from the Balancer pool withdrawing all assets in proportional way when
    pool is in recovery mode.
    """

    op_type = WithdrawOperation
    kind = "disassembly"
    protocol = "aura"

    @classmethod
    def get_txns(
        cls, ctx: GenericTxContext, arguments: list[Exit1ArgumentElement]
    ) -> list[Transactable]:
        txns = []

        for element in arguments:
            aura_rewards_address = to_checksum_address(element["rewards_address"])
            amount = element["amount"]

            bpt_address = aura_to_bpt_address(ctx, aura_rewards_address)

            if amount == 0:
                continue

            withdraw_aura = aura.WithdrawAndUndwrapStakedBPT(
                reward_address=aura_rewards_address, amount=amount
            )

            withdraw_balancer = (
                balancer.WithdrawAllAssetsProportionalPoolsInRecovery.get_txns(
                    ctx=ctx, arguments=[{"bpt_address": bpt_address, "amount": amount}]
                )
            )

            txns.append(withdraw_aura)
            for transactable in withdraw_balancer:
                txns.append(transactable)

        return txns
