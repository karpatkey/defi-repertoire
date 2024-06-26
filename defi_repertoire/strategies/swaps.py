from decimal import Decimal
from time import time

from defabipedia.balancer import Abis as BalancerAbis
from defabipedia.swap_pools import SwapPoolInstances
from defabipedia.tokens import Abis, Addresses, NATIVE
from defabipedia.types import Chain, SwapPools, Blockchain
from web3 import Web3

from roles_royce.generic_method import Transactable
from roles_royce.protocols.balancer.methods_general import ApproveForVault
from roles_royce.protocols import balancer
from roles_royce.protocols.balancer.types_and_enums import SwapKind
from roles_royce.protocols.base import Address
from roles_royce.protocols import cowswap
from roles_royce.protocols.swap_pools.quote_methods import QuoteCurve, QuoteUniswapV3
from roles_royce.protocols.swap_pools.swap_methods import (
    ApproveCurve,
    ApproveUniswapV3,
    SwapCurve,
    SwapUniswapV3,
    WrapNativeToken,
)
from defi_repertoire.strategies.disassembling.disassembler import validate_percentage
from defi_repertoire.strategies.base import GenericTxContext, SwapOperation, register


def get_amount_to_redeem(ctx: GenericTxContext, token_in_address: Address, fraction: float | Decimal) -> int:
    balance = 0
    if token_in_address == NATIVE:
        balance = ctx.w3.eth.get_balance(ctx.avatar_safe_address)
    else:
        token_in_contract = ctx.w3.eth.contract(address=token_in_address, abi=Abis.ERC20.abi)
        balance = token_in_contract.functions.balanceOf(ctx.avatar_safe_address).call()

    amount = int(Decimal(balance) * Decimal(fraction))

    if token_in_address == NATIVE:
        min_amount = 3
        if balance - amount <= Web3.to_wei(min_amount, "ether"):
            raise ValueError(f"Must keep at least a balance of {min_amount} of native token")

    return amount


def get_wrapped_token(blockchain: Blockchain) -> Address:
    if blockchain == Chain.ETHEREUM:
        return Addresses[blockchain].WETH
    elif blockchain == Chain.GNOSIS:
        return Addresses[blockchain].WXDAI
    else:
        raise ValueError("Blockchain not supported")


def get_pool_id(w3: Web3, blockchain: Blockchain, pool_address: Address) -> str:
    return (w3.eth.contract(address=pool_address, abi=BalancerAbis[blockchain].UniversalBPT.abi)
            .functions.getPoolId()
            .call())


def get_swap_pools(blockchain, protocol, token_in, token_out):
    """Returns all instances of SwapPools within the specified blockchain's
    SwapPools class, filtered by protocol and tokens."""
    pools_class = SwapPoolInstances[blockchain]

    instances = []
    for attr_name in dir(pools_class):
        attr_value = getattr(pools_class, attr_name)
        if isinstance(attr_value, SwapPools) and attr_value.protocol == protocol:
            if protocol == "UniswapV3" or protocol == "Balancer":
                if token_in == NATIVE:
                    token_in = get_wrapped_token(blockchain)
                if token_out == NATIVE:
                    token_out = get_wrapped_token(blockchain)
            # Check if both tokens are in the instance's tokens list
            if token_in in attr_value.tokens and token_out in attr_value.tokens:
                instances.append(attr_value)
    return instances


def get_quote(ctx: GenericTxContext, swap_pool: SwapPools, token_in: str, token_out: str, amount_in) -> Decimal:
    if swap_pool.protocol == "Curve":
        try:
            index_in = swap_pool.tokens.index(token_in)
        except ValueError:
            index_in = None

        try:
            index_out = swap_pool.tokens.index(token_out)
        except ValueError:
            index_out = None
        quote = QuoteCurve(ctx.blockchain, swap_pool.address, index_in, index_out, amount_in)
        amount_out = quote.call(web3=ctx.w3)
        return swap_pool, amount_out

    elif swap_pool.protocol == "UniswapV3":
        if token_in == NATIVE:
            token_in = get_wrapped_token(ctx.blockchain)
        elif token_out == NATIVE:
            token_out = get_wrapped_token(ctx.blockchain)
        quote = QuoteUniswapV3(ctx.blockchain, token_in, token_out, amount_in, swap_pool.uni_fee)
        amount_out = quote.call(web3=ctx.w3)
        return swap_pool, amount_out[0]

    elif swap_pool.protocol == "Balancer":
        if token_in == NATIVE:
            token_in = get_wrapped_token(ctx.blockchain)
        elif token_out == NATIVE:
            token_out = get_wrapped_token(ctx.blockchain)
        pool_id = get_pool_id(ctx.w3, ctx.blockchain, swap_pool.address)
        quote = balancer.methods_swap.QuerySwap(
            ctx.blockchain,
            pool_id,
            ctx.avatar_safe_address,
            token_in,
            token_out,
            amount_in,
        )
        amount_out = quote.call(web3=ctx.w3)
        return swap_pool, amount_out

    else:
        raise ValueError("Protocol not supported")

@register
class SwapCowswap:
    """Make a swap on CowSwap with best amount out
        Args:
        percentage (float): Percentage of token to remove.
        arguments (list[dict], optional): List of dictionaries with the withdrawal parameters.
            arg_dicts = [
                {
                    "token_in_address: "FillMewithTokenAddress",
                    "max_slippage": 0.01,
                    "token_out_address": "FillMewithTokenAddress"
                }
            ]
        amount_to_redeem (int, optional): Amount of wallet token to redeem. Defaults to None.
    Returns:
        list[ Transactable]:  List of transactions to execute.
    """
    op_type = SwapOperation
    kind = "swap"
    protocol = "cowswap"

    @classmethod
    def get_txns(cls, ctx: GenericTxContext, percentage: float, arguments: list[dict] = None,
                 amount_to_redeem: int = None) -> list[Transactable]:
        max_slippage = arguments[0]["max_slippage"] / 100
        token_in = arguments[0]["token_in_address"]
        token_out = arguments[0]["token_out_address"]
        fraction = validate_percentage(percentage)

        if amount_to_redeem is None:
            amount_to_redeem = get_amount_to_redeem(ctx.w3, ctx.avatar_safe_address, token_in, fraction)

        txns = []

        if amount_to_redeem == 0:
            return []

        if "anvil" in ctx.w3.client_version:
            fork = True
        else:
            fork = False

        if token_in == NATIVE:
            if amount_to_redeem is not None:
                amount_to_redeem = get_amount_to_redeem(ctx.w3, ctx.avatar_safe_address, token_in, fraction)
            wraptoken = WrapNativeToken(blockchain=ctx.blockchain, eth_amount=amount_to_redeem)
            txns.append(wraptoken)
            token_in = get_wrapped_token(ctx.blockchain)

        cow_txns = cowswap.create_order_and_swap(
            w3=ctx.w3,
            avatar=ctx.avatar_safe_address,
            sell_token=token_in,
            buy_token=token_out,
            amount=amount_to_redeem,
            kind=cowswap.SwapKind.SELL,
            max_slippage=max_slippage,
            valid_duration=20 * 60,
            fork=fork,
        )

        for cow_txn in cow_txns:
            txns.append(cow_txn)

        return txns

@register
class SwapBalancer:
    """Make a swap on Balancer with best amount out
    Args:
        percentage (float): Percentage of token to remove.
        arguments (list[dict], optional): List of dictionaries with the withdrawal parameters.
            arg_dicts = [
                {
                    "token_in_address: "FillMewithTokenAddress",
                    "max_slippage": 0.01,
                    "token_out_address": "FillMewithTokenAddress"
                }
            ]
        amount_to_redeem (int, optional): Amount of wallet token to redeem. Defaults to None.
    Returns:
        list[ Transactable]:  List of transactions to execute.
    """
    op_type = SwapOperation
    kind = "swap"
    protocol = "balancer"

    @classmethod
    def get_txns(cls, ctx: GenericTxContext, percentage: float, arguments: list[dict] = None,
                 amount_to_redeem: int = None) -> list[Transactable]:
        for element in arguments:
            max_slippage = element["max_slippage"] / 100
            token_in = element["token_in_address"]
            token_out = element["token_out_address"]
            fraction = validate_percentage(percentage)

            if amount_to_redeem is None:
                amount_to_redeem = get_amount_to_redeem(ctx.w3, ctx.avatar_safe_address, token_in, fraction)

            txns = []

            # get the pools where we get a quote from
            pools = get_swap_pools(ctx.blockchain, "Balancer", token_in, token_out)
            quotes = []
            if len(pools) == 0:
                raise ValueError("No pools found with the specified tokens")
            else:
                for pool in pools:
                    swap_pool, quote = get_quote(ctx, pool, token_in, token_out, amount_to_redeem)
                    quotes.append(quote)

            # TODO: here swap_pool is the latest defined swap_pool, is that correct?
            pool_id = get_pool_id(ctx.w3, ctx.blockchain, swap_pool.address)
            best_quote = max(quotes)
            amount_out_min_slippage = int(Decimal(best_quote) * Decimal(1 - max_slippage))
            if token_in == NATIVE:
                if amount_to_redeem is not None:
                    amount_to_redeem = get_amount_to_redeem(ctx, token_in, fraction)
                wraptoken = WrapNativeToken(blockchain=ctx.blockchain, eth_amount=amount_to_redeem)
                txns.append(wraptoken)
                token_in = get_wrapped_token(ctx.blockchain)
            elif token_out == NATIVE:
                token_out = get_wrapped_token(ctx.blockchain)
            approve_vault = ApproveForVault(token=token_in, amount=amount_to_redeem)
            swap_balancer = balancer.methods_swap.SingleSwap(
                blockchain=ctx.blockchain,
                pool_id=pool_id,
                avatar=ctx.avatar_safe_address,
                kind=SwapKind.OutGivenExactIn,
                token_in_address=token_in,
                token_out_address=token_out,
                amount_in=amount_to_redeem,
                min_amount_out=amount_out_min_slippage,
                deadline=int(int(time()) + 600),
            )

            txns.append(approve_vault)
            txns.append(swap_balancer)
        return txns

@register
class SwapOnCurve:
    op_type = SwapOperation
    kind = "swap"
    protocol = "balancer"

    @classmethod
    def get_txns(cls, ctx: GenericTxContext, percentage: float, arguments: list[dict] = None,
                 amount_to_redeem: int = None) -> list[Transactable]:

        """Make a swap on Curve with best amount out
        Args:
            percentage (float): Percentage of token to remove.
            arguments (list[dict], optional): List of dictionaries with the withdrawal parameters.
                arg_dicts = [
                    {
                        "token_in_address: "FillMewithTokenAddress",
                        "max_slippage": 0.01,
                        "token_out_address": "FillMewithTokenAddress"
                    }
                ]
            amount_to_redeem (int, optional): Amount of wallet token to redeem. Defaults to None.
        Returns:
            list[ Transactable]:  List of transactions to execute.
        """
        for element in arguments:
            max_slippage = element["max_slippage"] / 100
            token_in = element["token_in_address"]
            token_out = element["token_out_address"]
            fraction = validate_percentage(percentage)

            if amount_to_redeem is None:
                amount_to_redeem = get_amount_to_redeem(ctx, token_in, fraction)

            txns = []

            # get the pools where we get a quote from
            pools = get_swap_pools(ctx.blockchain, "Curve", token_in, token_out)
            quotes = []
            if len(pools) == 0:
                raise ValueError("No pools found with the specified tokens")
            else:
                for pool in pools:
                    swap_pool, quote = get_quote(ctx, pool, token_in, token_out, amount_to_redeem)
                    quotes.append(quote)

            # get the best quote
            best_quote = max(quotes)
            amount_out_min_slippage = int(Decimal(best_quote) * Decimal(1 - max_slippage))

            if token_in == NATIVE:
                if amount_to_redeem is not None:
                    amount_to_redeem = get_amount_to_redeem(ctx, token_in, fraction)
                eth_amount = amount_to_redeem
            else:
                eth_amount = 0
                approve_curve = ApproveCurve(
                    blockchain=ctx.blockchain,
                    token_address=token_in,
                    spender=swap_pool.address,
                    amount=amount_to_redeem,
                )
                txns.append(approve_curve)

            swap_curve = SwapCurve(
                blockchain=ctx.blockchain,
                pool_address=swap_pool.address,
                token_x=swap_pool.tokens.index(token_in),
                token_y=swap_pool.tokens.index(token_out),
                amount_x=amount_to_redeem,
                min_amount_y=amount_out_min_slippage,
                eth_amount=eth_amount,
            )

            txns.append(swap_curve)
        return txns

@register
class SwapUniswapV3:
    op_type = SwapOperation
    kind = "swap"
    protocol = "uniswapv3"

    @classmethod
    def get_txns(cls, ctx: GenericTxContext, percentage: float, arguments: list[dict] = None,
                 amount_to_redeem: int = None) -> list[Transactable]:
        """Make a swap on UniswapV3 with best amount out
        Args:
            percentage (float): Percentage of token to remove.
            arguments (list[dict], optional): List of dictionaries with the withdrawal parameters.
                arg_dicts = [
                    {
                        "token_in_address: "FillMewithTokenAddress",
                        "max_slippage": 0.01,
                        "token_out_address": "FillMewithTokenAddress"
                    }
                ]
            amount_to_redeem (int, optional): Amount of wallet token to redeem. Defaults to None.
        Returns:
            list[ Transactable]:  List of transactions to execute.
        """
        for element in arguments:
            max_slippage = element["max_slippage"] / 100
            token_in = element["token_in_address"]
            token_out = element["token_out_address"]
            fraction = validate_percentage(percentage)

            if amount_to_redeem is None:
                amount_to_redeem = get_amount_to_redeem(ctx, token_in, fraction)

            txns = []

            # get the pools where we get a quote from
            pools = get_swap_pools(ctx.blockchain, "UniswapV3", token_in, token_out)
            quotes = []
            if len(pools) == 0:
                raise ValueError("No pools found with the specified tokens")
            else:
                for pool in pools:
                    swap_pool, quote = get_quote(ctx, pool, token_in, token_out, amount_to_redeem)
                    quotes.append(quote)

            # get the best quote
            best_quote = max(quotes)
            amount_out_min_slippage = int(Decimal(best_quote) * Decimal(1 - max_slippage))
            if token_in == NATIVE:
                if amount_to_redeem is not None:
                    amount_to_redeem = get_amount_to_redeem(ctx, token_in, fraction)
                wraptoken = WrapNativeToken(blockchain=ctx.blockchain, eth_amount=amount_to_redeem)
                txns.append(wraptoken)
                token_in = get_wrapped_token(ctx.blockchain)
            elif token_out == NATIVE:
                token_out = get_wrapped_token(ctx.blockchain)

            approve_uniswapV3 = ApproveUniswapV3(
                blockchain=ctx.blockchain,
                token_address=token_in,
                amount=amount_to_redeem,
            )

            swap_uniswapV3 = SwapUniswapV3(
                blockchain=ctx.blockchain,
                token_in=token_in,
                token_out=token_out,
                avatar=ctx.avatar_safe_address,
                amount_in=amount_to_redeem,
                min_amount_out=amount_out_min_slippage,
                fee=swap_pool.uni_fee,
            )

            txns.append(approve_uniswapV3)
            txns.append(swap_uniswapV3)
        return txns
