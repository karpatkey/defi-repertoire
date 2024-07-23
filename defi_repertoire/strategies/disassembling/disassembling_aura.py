from decimal import Decimal

from defabipedia.aura import Abis
from pydantic import BaseModel
from roles_royce.generic_method import Transactable
from roles_royce.protocols.eth import aura

from defi_repertoire.strategies import register

from ..base import Amount, ChecksumAddress, GenericTxContext, Percentage
from . import disassembling_balancer as balancer


class Exit1ArgumentElement(BaseModel):
    rewards_address: ChecksumAddress
    amount: Amount


class Exit21ArgumentElement(BaseModel):
    rewards_address: ChecksumAddress
    max_slippage: Percentage
    amount: Amount


class Exit22ArgumentElement(BaseModel):
    rewards_address: ChecksumAddress
    max_slippage: Percentage
    token_out_address: ChecksumAddress
    amount: Amount


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

    kind = "disassembly"
    protocol = "aura"
    name = "exit_1"

    @classmethod
    def get_txns(
        cls, ctx: GenericTxContext, arguments: Exit1ArgumentElement
    ) -> list[Transactable]:
        txns = []
        bpt_address = aura_to_bpt_address(ctx, arguments.rewards_address)
        ctx.ctx["aura"]["aura_to_bpt"][arguments.rewards_address] = bpt_address

        withdraw_aura = aura.WithdrawAndUndwrapStakedBPT(
            reward_address=arguments.rewards_address, amount=arguments.amount
        )
        txns.append(withdraw_aura)

        return txns


@register
class Withdraw2:
    """Withdraw funds from Aura and then from the Balancer pool withdrawing all assets in proportional way
    (checks for recovery mode and acts accordingly).
    """

    kind = "disassembly"
    protocol = "aura"
    name = "exit_2_1"

    @classmethod
    def get_txns(
        cls, ctx: GenericTxContext, arguments: Exit21ArgumentElement
    ) -> list[Transactable]:
        txns = []
        amount = arguments.amount

        aura_reward_address = arguments.rewards_address
        aura_txns = Withdraw.get_txns(
            ctx,
            arguments=Exit1ArgumentElement(
                **{"rewards_address": aura_reward_address, "amount": amount}
            ),
        )
        txns.extend(aura_txns)

        bpt_address = ctx.ctx["aura"]["aura_to_bpt"][aura_reward_address]

        bal_txns = balancer.WithdrawAllAssetsProportional.get_txns(
            ctx=ctx,
            arguments=balancer.Exit11ArgumentElement(
                **{
                    "bpt_address": bpt_address,
                    "max_slippage": arguments.max_slippage,
                    "amount": amount,
                }
            ),
        )
        txns.extend(bal_txns)

        return txns


@register
class Exit22:
    """Withdraw funds from Aura and then from the Balancer pool withdrawing a single asset specified by the
    token index.
    """

    kind = "disassembly"
    protocol = "aura"
    name = "exit_2_2"

    @classmethod
    def get_txns(
        cls, ctx: GenericTxContext, arguments: Exit22ArgumentElement
    ) -> list[Transactable]:
        txns = []

        aura_rewards_address = arguments.rewards_address
        max_slippage = arguments.max_slippage
        token_out_address = arguments.token_out_address
        amount = arguments.amount

        bpt_address = aura_to_bpt_address(ctx, aura_rewards_address)

        withdraw_aura = aura.WithdrawAndUndwrapStakedBPT(
            reward_address=aura_rewards_address, amount=amount
        )

        withdraw_balancer = balancer.WithdrawSingle.get_txns(
            ctx=ctx,
            arguments=balancer.Exit12ArgumemntElement(
                **{
                    "bpt_address": bpt_address,
                    "max_slippage": max_slippage,
                    "token_out_address": token_out_address,
                    "amount": amount,
                }
            ),
        )

        txns.append(withdraw_aura)
        for transactable in withdraw_balancer:
            txns.append(transactable)

        return txns

