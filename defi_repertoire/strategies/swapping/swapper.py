from decimal import Decimal

from defabipedia.balancer import Abis as BalancerAbis
from defabipedia.swap_pools import SwapPoolInstances
from defabipedia.tokens import NATIVE, Addresses
from defabipedia.types import Blockchain, Chain, SwapPools
from roles_royce.protocols import balancer
from roles_royce.protocols.base import Address
from roles_royce.protocols.swap_pools.quote_methods import QuoteCurve, QuoteUniswapV3
from web3 import Web3

from defi_repertoire.strategies.base import GenericTxContext


def get_wrapped_token(blockchain: Blockchain) -> Address:
    if blockchain == Chain.ETHEREUM:
        return Addresses[blockchain].WETH
    elif blockchain == Chain.GNOSIS:
        return Addresses[blockchain].WXDAI
    else:
        raise ValueError("Blockchain not supported")


def get_pool_id(w3: Web3, blockchain: Blockchain, pool_address: Address) -> str:
    return (
        w3.eth.contract(
            address=pool_address, abi=BalancerAbis[blockchain].UniversalBPT.abi
        )
        .functions.getPoolId()
        .call()
    )


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


def get_quote(
    ctx: GenericTxContext,
    swap_pool: SwapPools,
    token_in: str,
    token_out: str,
    amount_in,
) -> Decimal:
    if swap_pool.protocol == "Curve":
        try:
            index_in = swap_pool.tokens.index(token_in)
        except ValueError:
            index_in = None

        try:
            index_out = swap_pool.tokens.index(token_out)
        except ValueError:
            index_out = None
        quote = QuoteCurve(
            ctx.blockchain, swap_pool.address, index_in, index_out, amount_in
        )
        amount_out = quote.call(web3=ctx.w3)
        return swap_pool, amount_out

    elif swap_pool.protocol == "UniswapV3":
        if token_in == NATIVE:
            token_in = get_wrapped_token(ctx.blockchain)
        elif token_out == NATIVE:
            token_out = get_wrapped_token(ctx.blockchain)
        quote = QuoteUniswapV3(
            ctx.blockchain, token_in, token_out, amount_in, swap_pool.uni_fee
        )
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
