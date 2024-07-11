import os
from decimal import Decimal
from typing import Dict

import requests
from defabipedia.balancer import Abis
from defabipedia.types import Blockchain, Chain
from pydantic import BaseModel
from roles_royce.generic_method import Transactable
from roles_royce.protocols import balancer
from web3.exceptions import ContractLogicError

from defi_repertoire.stale_while_revalidate import stale_while_revalidate_cache

from ..base import (
    Amount,
    ChecksumAddress,
    GenericTxContext,
    Percentage,
    optional_args,
    register,
)

API_KEY = os.getenv("THEGRAPH_API_KEY", "MOCK_KEY")

GRAPHS: Dict[Blockchain, str] = {}
GRAPHS[Chain.get_blockchain_by_chain_id(1)] = (
    f"https://gateway-arbitrum.network.thegraph.com/api/{API_KEY}/subgraphs/id/C4ayEZP2yTXRAB8vSaTrgN4m9anTe9Mdm2ViyiAuV9TV"
)
GRAPHS[Chain.get_blockchain_by_chain_id(100)] = (
    f"https://gateway-arbitrum.network.thegraph.com/api/{API_KEY}/subgraphs/id/EJezH1Cp31QkKPaBDerhVPRWsKVZLrDfzjrLqpmv6cGg"
)

GAUGE_GRAPHS: Dict[Blockchain, str] = {}
GAUGE_GRAPHS[Chain.get_blockchain_by_chain_id(1)] = (
    f"https://gateway-arbitrum.network.thegraph.com/api/{API_KEY}/subgraphs/id/4sESujoqmztX6pbichs4wZ1XXyYrkooMuHA8sKkYxpTn"
)
GAUGE_GRAPHS[Chain.get_blockchain_by_chain_id(100)] = (
    f"https://gateway-arbitrum.network.thegraph.com/api/{API_KEY}/subgraphs/id/HW5XpZBi2iYDLBqqEEMiRJFx8ZJAQak9uu5TzyH9BBxy"
)


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


@stale_while_revalidate_cache(ttl=5 * 60, use_stale_ttl=10 * 60)
async def fetch_pools(blockchain: Blockchain):
    print(f"\nFETCHING BALANCER POOLS {blockchain.name}\n")
    req = """
    {
      pools(where: { totalLiquidity_gt: "500000" }, orderBy: totalLiquidity) {
        name
        address
        poolType
        strategyType
        oracleEnabled
        symbol
        swapEnabled
        isPaused
        isInRecoveryMode
        totalLiquidity
        tokens {
          symbol
          name
          address
        }
      }
    }
    """

    graph_url = GRAPHS.get(blockchain)
    if not graph_url:
        raise ValueError(f"Blockchain not supported: {blockchain}")

    response = requests.post(url=graph_url, json={"query": req})
    return response.json()["data"]["pools"]


@stale_while_revalidate_cache(ttl=5 * 60, use_stale_ttl=10 * 60)
async def fetch_gauges(blockchain: Blockchain):
    print(f"\nFETCHING BALANCER GAUGES {blockchain.name}\n")
    req = """
    {
      gaugeFactories {
        id
        gauges {
          id
          symbol
          poolAddress
        }
      }
    }
    """
    graph_url = GAUGE_GRAPHS.get(blockchain)
    if not graph_url:
        raise ValueError(f"Blockchain not supported: {blockchain}")

    response = requests.post(url=graph_url, json={"query": req})
    factories = response.json()["data"]["gaugeFactories"]
    return [g for f in factories for g in f["gauges"]]


@register
class WithdrawAllAssetsProportional:
    """
    Withdraw funds from the Balancer pool withdrawing all assets in proportional way (not used for pools in recovery mode!).
    """

    kind = "disassembly"
    protocol = "balancer"
    id = "withdraw_all_assets_proportional"
    name = "Withdraw Proportionally"

    class Args(BaseModel):
        bpt_address: ChecksumAddress
        max_slippage: Percentage
        amount: Amount

    @classmethod
    def get_txns(cls, ctx: GenericTxContext, arguments: Args) -> list[Transactable]:

        bpt_address = arguments.bpt_address
        max_slippage = arguments.max_slippage / 100
        amount = arguments.amount

        bpt_contract = ctx.w3.eth.contract(
            address=bpt_address, abi=Abis[ctx.blockchain].UniversalBPT.abi
        )

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
        return [withdraw_balancer]


@register
class WithdrawSingle:
    """
    Withdraw funds from the Balancer pool withdrawing a single asset specified by the token index.
    """

    kind = "disassembly"
    protocol = "balancer"
    id = "withdraw_single"
    name = "Withdraw (Single Token)"

    class Args(BaseModel):
        bpt_address: ChecksumAddress
        amount: Amount
        max_slippage: Percentage
        token_out_address: ChecksumAddress

    OptArgs = optional_args(Args)

    @classmethod
    async def get_options(
        cls,
        blockchain: Blockchain,
        arguments: OptArgs,
    ):
        pools = await fetch_pools(blockchain)
        if arguments.bpt_address:
            bpt_address = str.lower(arguments.bpt_address)
            pool = next(
                (p for p in pools if str.lower(p["address"]) == bpt_address),
                None,
            )
            if not pool:
                raise ValueError("Pool not found")
            return {"bpt_address": [bpt_address], "token_out_address": pool["tokens"]}

        else:
            return {"bpt_address": [p["address"] for p in pools]}

    @classmethod
    def get_txns(
        cls,
        ctx: GenericTxContext,
        arguments: Args,
    ) -> list[Transactable]:

        bpt_address = arguments.bpt_address
        max_slippage = arguments.max_slippage / 100
        token_out_address = arguments.token_out_address
        amount = arguments.amount

        bpt_contract = ctx.w3.eth.contract(
            address=bpt_address, abi=Abis[ctx.blockchain].UniversalBPT.abi
        )

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
        return [withdraw_balancer]


@register
class WithdrawProportionalRecovery:
    """
    Withdraw funds from the Balancer pool withdrawing all assets in proportional way for pools in recovery mode.
    """

    kind = "disassembly"
    protocol = "balancer"
    id = "withdraw_all_assets_proportional_pools_in_recovery"
    name = "Withdraw Proportionally (Recovery mode)"

    class Args(BaseModel):
        bpt_address: ChecksumAddress
        amount: Amount

    @classmethod
    def get_txns(
        cls,
        ctx: GenericTxContext,
        arguments: Args,
    ) -> list[Transactable]:

        bpt_address = arguments.bpt_address
        amount = arguments.amount

        bpt_contract = ctx.w3.eth.contract(
            address=bpt_address, abi=Abis[ctx.blockchain].UniversalBPT.abi
        )

        try:
            bpt_pool_recovery_mode = bpt_contract.functions.inRecoveryMode().call()
        except ContractLogicError:
            bpt_pool_recovery_mode = False
        if bpt_pool_recovery_mode is False:
            raise ValueError("This pool is not in recovery mode.")

        bpt_pool_id = "0x" + bpt_contract.functions.getPoolId().call().hex()

        withdraw_balancer = balancer.ExactBptRecoveryModeExit(
            w3=ctx.w3,
            pool_id=bpt_pool_id,
            avatar=ctx.avatar_safe_address,
            bpt_amount_in=amount,
        )

        return [withdraw_balancer]


@register
class UnstakeAndWithdrawProportional:
    """
    Unstake from gauge and withdraw funds from the Balancer pool withdrawing all assets
    in proportional way (not used for pools in recovery mode!).
    """

    kind = "disassembly"
    protocol = "balancer"
    id = "unstake_withdraw_proportional"
    name = "Unstake + Withdraw (proportional)"

    class Args(BaseModel):
        gauge_address: ChecksumAddress
        amount: Amount
        max_slippage: Percentage

    OptArgs = optional_args(Args)

    @classmethod
    async def get_options(
        cls,
        blockchain: Blockchain,
        arguments: OptArgs,
    ):
        gauges = await fetch_gauges(blockchain)
        return {
            "gauge_address": [
                {
                    "symbol": p["symbol"],
                    "address": p["id"],
                    "poolAddress": p["poolAddress"],
                }
                for p in gauges
            ]
        }

    @classmethod
    def get_txns(cls, ctx: GenericTxContext, arguments: Args) -> list[Transactable]:

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
            arguments=WithdrawAllAssetsProportional.Args(
                bpt_address=bpt_address,
                max_slippage=max_slippage,
                amount=amount,
            ),
        )
        for transactable in withdraw_balancer:
            txns.append(transactable)

        return txns


@register
class UnstakeAndWithdrawSingleToken:
    """
    Unstake from gauge and withdraw funds from the Balancer pool withdrawing a single asset specified by the token index.
    """

    kind = "disassembly"
    protocol = "balancer"
    id = "unstake_withdraw_single"
    name = "Unstake + Windraw (Single Token)"

    class Args(BaseModel):
        gauge_address: ChecksumAddress
        amount: Amount
        max_slippage: Percentage
        token_out_address: ChecksumAddress

    @classmethod
    def get_txns(cls, ctx: GenericTxContext, arguments: Args) -> list[Transactable]:

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
            arguments=WithdrawSingle.Args(
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


@register
class UnstakeAndWithdrawProportionalRecovery:
    """
    Unstake from gauge and withdraw funds from the Balancer pool withdrawing all assets
    in proportional way for pools in recovery mode.
    """

    kind = "disassembly"
    protocol = "balancer"
    id = "unstake_withdraw_proportional_recovery"
    name = "Unstake + Withdraw (proportional) (Rocovery)"

    class Args(BaseModel):
        gauge_address: ChecksumAddress
        amount: Amount
        max_slippage: Percentage

    @classmethod
    def get_txns(cls, ctx: GenericTxContext, arguments: Args) -> list[Transactable]:
        txns = []

        gauge_address = arguments.gauge_address
        amount = arguments.amount

        unstake_gauge = balancer.Unstake(
            w3=ctx.w3, gauge_address=gauge_address, amount=amount
        )
        txns.append(unstake_gauge)

        gauge_contract = ctx.w3.eth.contract(
            address=gauge_address, abi=Abis[ctx.blockchain].Gauge.abi
        )
        bpt_address = gauge_contract.functions.lp_token().call()

        withdraw_balancer = WithdrawProportionalRecovery.get_txns(
            ctx=ctx,
            arguments=WithdrawProportionalRecovery.Args(
                **{"bpt_address": bpt_address, "amount": amount}
            ),
        )
        for transactable in withdraw_balancer:
            txns.append(transactable)

        return txns
