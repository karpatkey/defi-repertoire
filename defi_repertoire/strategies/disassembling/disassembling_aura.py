from decimal import Decimal
from typing import Dict

import requests
from defabipedia.aura import Abis
from defabipedia.types import Blockchain, Chain
from pydantic import BaseModel
from roles_royce.generic_method import Transactable
from roles_royce.protocols.eth import aura

from defi_repertoire.stale_while_revalidate import stale_while_revalidate_cache
from defi_repertoire.strategies import register

from ..base import Amount, ChecksumAddress, GenericTxContext, Percentage, optional_args
from . import disassembling_balancer as balancer


class Exit1ArgumentElement(BaseModel):
    rewards_address: ChecksumAddress
    amount: Amount


class Exit21ArgumentElement(BaseModel):
    rewards_address: ChecksumAddress
    max_slippage: Percentage
    amount: Amount


class WithdrawSingleArgs(BaseModel):
    rewards_address: ChecksumAddress
    max_slippage: Percentage
    token_out_address: ChecksumAddress
    amount: Amount


OptExit1Arguments = optional_args(Exit1ArgumentElement)
OptExit21Arguments = optional_args(Exit21ArgumentElement)
OptWithdrawSingleArgs = optional_args(WithdrawSingleArgs)

GRAPHS: Dict[Blockchain, str] = {}
GRAPHS[Chain.get_blockchain_by_chain_id(1)] = (
    "https://subgraph.satsuma-prod.com/cae76ab408ca/1xhub-ltd/aura-finance-mainnet/api"
)
GRAPHS[Chain.get_blockchain_by_chain_id(100)] = (
    "https://subgraph.satsuma-prod.com/cae76ab408ca/1xhub-ltd/aura-finance-gnosis/api"
)


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


@stale_while_revalidate_cache(ttl=5 * 60, use_stale_ttl=10 * 60)
async def fetch_pools(blockchain: Blockchain):
    print(f"\nFETCHING AURA POOLS {blockchain.name}\n")
    req = """
    {
      pools(where: { totalSupply_gt: "500000" }) {
        id
        totalSupply
        depositToken {
          id
          decimals
          symbol
          name
        }
        lpToken {
          id
          decimals
          symbol
          name
        }
        gauge {
          id
        }
        isFactoryPool
        rewardPool
      }
    }
    """
    graph_url = GRAPHS.get(blockchain)
    if not graph_url:
        raise ValueError(f"Blockchain not supported: {blockchain}")

    response = requests.post(url=graph_url, json={"query": req})
    return response.json()["data"]["pools"]


@register
class Withdraw:
    """Withdraw funds from Aura."""

    kind = "disassembly"
    protocol = "aura"
    name = "exit_1"

    @classmethod
    async def get_options(cls, ctx: GenericTxContext, arguments: OptExit1Arguments):
        pools = await fetch_pools(ctx.blockchain)
        if arguments.rewards_address:
            address = str.lower(arguments.rewards_address)
            pool = next(
                (p for p in pools if str.lower(p["rewardPool"]) == address),
                None,
            )
            if not pool:
                raise ValueError("Pool not found")
            return {"rewards_address": [pool["rewardPool"]]}
        else:
            reward_addresses = [p["rewardPool"] for p in pools]
            return {"rewards_address": reward_addresses}

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
    (not used for pools in recovery mode!).
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
class WithdrawSingle:
    """Withdraw funds from Aura and then from the Balancer pool withdrawing a single asset specified by the
    token index.
    """

    kind = "disassembly"
    protocol = "aura"
    name = "exit_2_2"

    @classmethod
    async def get_options(cls, ctx: GenericTxContext, arguments: OptWithdrawSingleArgs):
        pools = await fetch_pools(ctx.blockchain)
        if arguments.rewards_address:

            address = str.lower(arguments.rewards_address)
            pool = next(
                (p for p in pools if str.lower(p["rewardPool"]) == address),
                None,
            )
            if not pool:
                raise ValueError("Pool not found")

            bpt_address = pool["lpToken"]["id"]
            balancer_options = await balancer.WithdrawSingle.get_options(
                ctx=ctx,
                arguments=balancer.OptExit12Arguments(
                    **{
                        "bpt_address": bpt_address,
                    }
                ),
            )
            return {
                "rewards_address": [address],
                "token_out_address": balancer_options["token_out_address"],
            }

        else:
            reward_addresses = [p["rewardPool"] for p in pools]
            return {"rewards_address": reward_addresses}

    @classmethod
    def get_txns(
        cls, ctx: GenericTxContext, arguments: WithdrawSingleArgs
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


@register
class Exit23:
    """Withdraw funds from Aura and then from the Balancer pool withdrawing all assets in proportional way when
    pool is in recovery mode.
    """

    kind = "disassembly"
    protocol = "aura"
    name = "exit_2_3"

    @classmethod
    def get_txns(
        cls, ctx: GenericTxContext, arguments: Exit1ArgumentElement
    ) -> list[Transactable]:
        txns = []

        aura_rewards_address = arguments.rewards_address

        bpt_address = aura_to_bpt_address(ctx, aura_rewards_address)

        withdraw_aura = aura.WithdrawAndUndwrapStakedBPT(
            reward_address=aura_rewards_address, amount=arguments.amount
        )

        withdraw_balancer = (
            balancer.WithdrawAllAssetsProportionalPoolsInRecovery.get_txns(
                ctx=ctx,
                arguments=balancer.Exit13ArgumentElement(
                    **{"bpt_address": bpt_address, "amount": arguments.amount}
                ),
            )
        )

        txns.append(withdraw_aura)
        for transactable in withdraw_balancer:
            txns.append(transactable)

        return txns
