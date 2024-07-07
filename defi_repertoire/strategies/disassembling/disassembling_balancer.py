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


OptExit12Arguments = optional_args(Exit12ArgumemntElement)


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


API_KEY = os.getenv("THEGRAPH_API_KEY")

GRAPHS: Dict[Blockchain, str] = {}
GRAPHS[Chain.get_blockchain_by_chain_id(1)] = (
    f"https://gateway-arbitrum.network.thegraph.com/api/{API_KEY}/subgraphs/id/C4ayEZP2yTXRAB8vSaTrgN4m9anTe9Mdm2ViyiAuV9TV"
)
GRAPHS[Chain.get_blockchain_by_chain_id(100)] = (
    f"https://gateway-arbitrum.network.thegraph.com/api/{API_KEY}/subgraphs/id/EJezH1Cp31QkKPaBDerhVPRWsKVZLrDfzjrLqpmv6cGg"
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


@register
class WithdrawAllAssetsProportional:
    """
    Withdraw funds from the Balancer pool withdrawing all assets in proportional way (not used for pools in recovery mode!).
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

    kind = "disassembly"
    protocol = "balancer"
    name = "withdraw_single"

    @classmethod
    async def get_options(
        cls,
        ctx: GenericTxContext,
        arguments: OptExit12Arguments,
    ):
        pools = await fetch_pools(ctx.blockchain)
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
        txns.append(withdraw_balancer)

        return txns


@register
class WithdrawAllAssetsProportionalPoolsInRecovery:
    """
    Withdraw funds from the Balancer pool withdrawing all assets in proportional way for pools in recovery mode.
    """

    kind = "disassembly"
    protocol = "balancer"
    name = "withdraw_all_assets_proportional_pools_in_recovery"

    @classmethod
    def get_txns(
        cls,
        ctx: GenericTxContext,
        arguments: Exit13ArgumentElement,
    ) -> list[Transactable]:

        txns = []
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

        txns.append(withdraw_balancer)

        return txns


@register
class Exit21:
    """
    Unstake from gauge and withdraw funds from the Balancer pool withdrawing all assets
    in proportional way (not used for pools in recovery mode!).
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


@register
class Exit23:
    """
    Unstake from gauge and withdraw funds from the Balancer pool withdrawing all assets
    in proportional way for pools in recovery mode.
    """

    kind = "disassembly"
    protocol = "balancer"
    name = "exit_2_3"

    @classmethod
    def get_txns(
        cls, ctx: GenericTxContext, arguments: Exit23ArgumentElement
    ) -> list[Transactable]:
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

        withdraw_balancer = WithdrawAllAssetsProportionalPoolsInRecovery.get_txns(
            ctx=ctx,
            arguments=Exit13ArgumentElement(
                **{"bpt_address": bpt_address, "amount": amount}
            ),
        )
        for transactable in withdraw_balancer:
            txns.append(transactable)

        return txns
