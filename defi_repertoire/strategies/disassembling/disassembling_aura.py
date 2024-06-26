from decimal import Decimal

from defabipedia.aura import Abis
from typing_extensions import TypedDict
from web3.types import ChecksumAddress

from roles_royce.generic_method import Transactable
from roles_royce.protocols.eth import aura
from roles_royce.toolshed.disassembling.disassembling_balancer import (
    validate_percentage,
)
from roles_royce.utils import to_checksum_address

from .disassembler import validate_percentage
from ..base import GenericTxContext, WithdrawOperation
from . import disassembling_balancer as balancer
from defi_repertoire.strategies import register

class Exit1ArgumentElement(TypedDict):
    rewards_address: str


class Exit21ArgumentElement(TypedDict):
    rewards_address: str
    max_slippage: float


class Exit22ArgumentElement(TypedDict):
    rewards_address: str
    max_slippage: float
    token_out_address: str


def aura_contracts_helper(ctx: GenericTxContext, aura_rewards_address: ChecksumAddress, fraction: float | Decimal) -> (
        str, int):
    aura_rewards_contract = ctx.w3.eth.contract(
        address=aura_rewards_address, abi=Abis[ctx.blockchain].BaseRewardPool.abi
    )
    aura_token_amount = aura_rewards_contract.functions.balanceOf(ctx.avatar_safe_address).call()
    bpt_address = aura_rewards_contract.functions.asset().call()

    amount_to_redeem = int(Decimal(aura_token_amount) * Decimal(fraction))

    return bpt_address, amount_to_redeem

@register
class Withdraw:
    """Withdraw funds from Aura.

    Args:
        percentage (float): Percentage of liquidity to remove from Aura.
        arguments (list[dict]): List of dictionaries with the Aura rewards addresses to withdraw from.
            arg_dicts = [
                    {
                        "rewards_address": "0xsOmEAddResS"
                    }
            ]

    Returns:
        list[Transactable]: List of transactions to execute.
    """
    op_type = WithdrawOperation
    kind = "disassembly"
    protocol = "aura"

    @classmethod
    def get_txns(cls, ctx: GenericTxContext, percentage: float, arguments: list[Exit1ArgumentElement],
                 amount_to_redeem: int = None) -> list[Transactable]:
        fraction = validate_percentage(percentage)

        txns = []
        for element in arguments:
            aura_rewards_address = to_checksum_address(element["rewards_address"])

            bpt_address, amount_to_redeem = aura_contracts_helper(ctx,
                                                                  aura_rewards_address=aura_rewards_address,
                                                                  fraction=fraction
                                                                  )
            ctx.ctx["aura"]["aura_to_bpt"][aura_rewards_address] = bpt_address
            if amount_to_redeem == 0:
                return []
            withdraw_aura = aura.WithdrawAndUndwrapStakedBPT(
                reward_address=aura_rewards_address, amount=amount_to_redeem
            )
            txns.append(withdraw_aura)

        return txns

@register
class Withdraw2:
    """Withdraw funds from Aura and then from the Balancer pool withdrawing all assets in proportional way
    (not used for pools in recovery mode!).

    Args:
        percentage (float): Percentage of liquidity to remove from Aura.
        arguments (list[dict]): List of dictionaries with the withdrawal parameters.
            arg_dicts = [
                {
                    "rewards_address": 0xsOmEAddResS",
                    "max_slippage": 1.27
                }
            ]

    Returns:
        list[Transactable]: List of transactions to execute.
    """
    op_type = WithdrawOperation
    name = "widraw_aura_balancer"
    kind = "disassembly"
    protocol = "aura"

    @classmethod
    def get_txns(cls, ctx: GenericTxContext, percentage: float, arguments: list[Exit21ArgumentElement],
                 amount_to_redeem: int = None) -> list[Transactable]:

        if amount_to_redeem == 0:
            return []

        fraction = validate_percentage(percentage)
        txns = []

        for element in arguments:
            aura_reward_address = to_checksum_address(element["rewards_address"])
            aura_txns = Withdraw.get_txns(ctx, percentage, arguments=[{"rewards_address": aura_reward_address}],
                                          amount_to_redeem=amount_to_redeem)
            txns.extend(aura_txns)

            max_slippage = element["max_slippage"]

            bpt_address = ctx.ctx["aura"]["aura_to_bpt"][aura_reward_address]

            bal_txns = balancer.WithdrawAllAssetsProportional.get_txns(
                ctx=ctx,
                percentage=100,
                arguments=[{"bpt_address": bpt_address, "max_slippage": max_slippage}],
                amount_to_redeem=amount_to_redeem,
            )
            txns.extend(bal_txns)

        return txns

    # def exit_2_2(self, percentage: float, arguments: list[Exit22ArgumentElement]) -> list[Transactable]:
    #     """Withdraw funds from Aura and then from the Balancer pool withdrawing a single asset specified by the
    #     token index.
    #
    #     Args:
    #         percentage (float): Percentage of liquidity to remove from Aura.
    #         arguments (list[dict]): List of dictionaries with the withdrawal parameters.
    #             arg_dicts = [
    #                 {
    #                     "rewards_address": "0xsOmEAddResS",
    #                     "max_slippage": 0.1,
    #                     token_out_address": "0xAnoThERAdDResS"
    #                 }
    #             ]
    #
    #     Returns:
    #         list[Transactable]: List of transactions to execute.
    #     """
    #
    #     fraction = validate_percentage(percentage)
    #
    #     txns = []
    #
    #     for element in arguments:
    #         aura_rewards_address = to_checksum_address(element["rewards_address"])
    #         max_slippage = element["max_slippage"]
    #         token_out_address = to_checksum_address(element["token_out_address"])
    #
    #         bpt_address, amount_to_redeem = aura_contracts_helper(
    #             aura_rewards_address=aura_rewards_address, fraction=fraction
    #         )
    #
    #         if amount_to_redeem == 0:
    #             return []
    #
    #         withdraw_aura = aura.WithdrawAndUndwrapStakedBPT(
    #             reward_address=aura_rewards_address, amount=amount_to_redeem
    #         )
    #
    #         balancer_disassembler = BalancerDisassembler(
    #             w3=self.w3,
    #             avatar_safe_address=self.avatar_safe_address,
    #             roles_mod_address=self.roles_mod_address,
    #             role=self.role,
    #             signer_address=self.signer_address,
    #         )
    #
    #         withdraw_balancer = balancer_disassembler.exit_1_2(
    #             percentage=100,
    #             arguments=[
    #                 {"bpt_address": bpt_address, "max_slippage": max_slippage, "token_out_address": token_out_address}
    #             ],
    #             amount_to_redeem=amount_to_redeem,
    #         )
    #
    #         txns.append(withdraw_aura)
    #         for transactable in withdraw_balancer:
    #             txns.append(transactable)
    #
    #     return txns
    #
    # def exit_2_3(self, percentage: float, arguments: list[Exit1ArgumentElement]) -> list[Transactable]:
    #     """Withdraw funds from Aura and then from the Balancer pool withdrawing all assets in proportional way when
    #     pool is in recovery mode.
    #
    #     Args:
    #         percentage (float): Percentage of liquidity to remove from Aura.
    #         arguments (list[dict]): List of dictionaries with the withdrawal parameters.
    #             arg_dicts = [
    #                 {
    #                     "rewards_address": "0xsOmEAddResS"
    #                 }
    #             ]
    #
    #     Returns:
    #         list[Transactable]: List of transactions to execute.
    #     """
    #
    #     fraction = validate_percentage(percentage)
    #
    #     txns = []
    #
    #     for element in arguments:
    #         aura_rewards_address = to_checksum_address(element["rewards_address"])
    #
    #         bpt_address, amount_to_redeem = self.aura_contracts_helper(
    #             aura_rewards_address=aura_rewards_address, fraction=fraction
    #         )
    #
    #         if amount_to_redeem == 0:
    #             return []
    #
    #         withdraw_aura = aura.WithdrawAndUndwrapStakedBPT(
    #             reward_address=aura_rewards_address, amount=amount_to_redeem
    #         )
    #
    #         balancer_disassembler = BalancerDisassembler(
    #             w3=self.w3,
    #             avatar_safe_address=self.avatar_safe_address,
    #             roles_mod_address=self.roles_mod_address,
    #             role=self.role,
    #             signer_address=self.signer_address,
    #         )
    #
    #         withdraw_balancer = balancer_disassembler.exit_1_3(
    #             percentage=100, arguments=[{"bpt_address": bpt_address}], amount_to_redeem=amount_to_redeem
    #         )
    #
    #         txns.append(withdraw_aura)
    #         for transactable in withdraw_balancer:
    #             txns.append(transactable)
    #
    #     return txns