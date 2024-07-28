import logging
import os
from decimal import Decimal
from typing import Dict, Tuple

import requests
from defabipedia.balancer import Abis
from defabipedia.types import Blockchain, Chain
from pydantic import BaseModel
from roles_royce.generic_method import Transactable
from roles_royce.protocols import balancer
from web3.exceptions import ContractLogicError

from defi_repertoire.stale_while_revalidate import cache_af

from ..base import Amount, ChecksumAddress, GenericTxContext, Percentage, register

logger = logging.getLogger(__name__)

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


@cache_af()
async def fetch_pools(blockchain: Blockchain):
    logger.debug(f"\nFETCHING BALANCER POOLS {blockchain.name}\n")

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


@cache_af()
async def fetch_gauges(blockchain: Blockchain):
    logger.debug(f"\nFETCHING BALANCER GAUGES {blockchain.name}\n")

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


def get_contract_mode(
    ctx: GenericTxContext, bpt_address: ChecksumAddress
) -> Tuple[bool, bool]:
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

    class OptArgs(BaseModel):
        bpt_address: ChecksumAddress

    @classmethod
    async def get_base_options(
        cls,
        blockchain: Blockchain,
    ):
        pools = await fetch_pools(blockchain)
        return {
            "bpt_address": [
                {"address": p["address"], "label": p["symbol"]} for p in pools
            ]
        }

    @classmethod
    async def get_options(
        cls,
        blockchain: Blockchain,
        arguments: OptArgs,
    ):
        pools = await fetch_pools(blockchain)
        bpt_address = str.lower(arguments.bpt_address)
        pool = next(
            (p for p in pools if str.lower(p["address"]) == bpt_address),
            None,
        )
        if not pool:
            raise ValueError("Pool not found")
        return {
            "token_out_address": [
                {"address": t["address"], "label": t["symbol"]} for t in pool["tokens"]
            ]
        }

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
        return [withdraw_balancer]


@register
class WithdrawProportional:
    """
    Withdraw funds from the Balancer pool withdrawing all assets in proportional way for pools in recovery mode.
    """

    kind = "disassembly"
    protocol = "balancer"
    id = "withdraw_proportional"
    name = "Withdraw Proportionally"

    class Args(BaseModel):
        bpt_address: ChecksumAddress
        amount: Amount

    @classmethod
    async def get_base_options(
        cls,
        blockchain: Blockchain,
    ):
        pools = await fetch_pools(blockchain)
        return {
            "bpt_address": [
                {"address": p["address"], "label": p["symbol"]} for p in pools
            ]
        }

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
    in proportional way (checks if pool is in recovery mode and acts accordingly).
    """

    kind = "disassembly"
    protocol = "balancer"
    id = "unstake_withdraw_proportional"
    name = "Unstake + Withdraw (proportional)"

    class Args(BaseModel):
        gauge_address: ChecksumAddress
        amount: Amount
        max_slippage: Percentage

    @classmethod
    async def get_base_options(
        cls,
        blockchain: Blockchain,
    ):
        gauges = await fetch_gauges(blockchain)
        return {
            "gauge_address": [
                {
                    "label": p["symbol"],
                    "address": p["id"],
                    # "poolAddress": p["poolAddress"],
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
    async def get_base_options(
        cls,
        blockchain: Blockchain,
    ):
        gauges = await fetch_gauges(blockchain)
        return {
            "gauge_address": [
                {
                    "label": p["symbol"],
                    "address": p["id"],
                    # "poolAddress": p["poolAddress"],
                }
                for p in gauges
            ]
        }

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
