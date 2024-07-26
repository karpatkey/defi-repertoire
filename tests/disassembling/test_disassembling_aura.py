from decimal import Decimal

from defabipedia.aura import Abis
from defabipedia.types import Chain

from roles_royce.protocols.aura.contract_methods import DepositBPT, ApproveForBooster
from roles_royce import roles

from defi_repertoire.strategies.disassembling import disassembler
from defi_repertoire.strategies.disassembling import disassembling_aura as aura
from defi_repertoire.strategies.base import GenericTxContext
from tests.fork_fixtures import accounts, local_node_eth
from tests.roles import apply_presets, deploy_roles, setup_common_roles
from tests.utils import create_simple_safe, steal_token

presets = """{
  "version": "1.0",
  "chainId": "1",
  "meta": {
    "name": null,
    "description": "",
    "txBuilderVersion": "1.8.0"
  },
  "createdAt": 1701637793776,
  "transactions": [
                {
                "to": "0x1ffAdc16726dd4F91fF275b4bF50651801B06a86",
                "data": "0x5e8266950000000000000000000000000000000000000000000000000000000000000004000000000000000000000000CfCA23cA9CA720B6E98E3Eb9B6aa0fFC4a5C08B9",
                "value": "0"
                },
                {
                "to": "0x1ffAdc16726dd4F91fF275b4bF50651801B06a86",
                "data": "0x2fcf52d10000000000000000000000000000000000000000000000000000000000000004000000000000000000000000CfCA23cA9CA720B6E98E3Eb9B6aa0fFC4a5C08B9095ea7b3000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000002",
                "value": "0"
                },
                {
                "to": "0x1ffAdc16726dd4F91fF275b4bF50651801B06a86",
                "data": "0x5e8266950000000000000000000000000000000000000000000000000000000000000004000000000000000000000000A57b8d98dAE62B26Ec3bcC4a365338157060B234",
                "value": "0"
                },
                {
                "to": "0x1ffAdc16726dd4F91fF275b4bF50651801B06a86",
                "data": "0x2fcf52d10000000000000000000000000000000000000000000000000000000000000004000000000000000000000000A57b8d98dAE62B26Ec3bcC4a365338157060B23443a0d066000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000002",
                "value": "0"
                },
                {
                "to": "0x1ffAdc16726dd4F91fF275b4bF50651801B06a86",
                "data": "0x5e82669500000000000000000000000000000000000000000000000000000000000000040000000000000000000000001204f5060be8b716f5a62b4df4ce32acd01a69f5",
                "value": "0"
                },
                {
                "to": "0x1ffAdc16726dd4F91fF275b4bF50651801B06a86",
                "data": "0x2fcf52d100000000000000000000000000000000000000000000000000000000000000040000000000000000000000001204f5060be8b716f5a62b4df4ce32acd01a69f5c32e7202000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000002",
                "value": "0"
                }
]
}"""

def test_integration_exit_1(local_node_eth, accounts):
    w3 = local_node_eth.w3
    block = 18193307
    local_node_eth.set_block(block)

    avatar_safe = create_simple_safe(w3=w3, owner=accounts[0])
    roles_contract = deploy_roles(avatar=avatar_safe.address, w3=w3)
    setup_common_roles(avatar_safe, roles_contract)

    apply_presets(
        avatar_safe,
        roles_contract,
        json_data=presets,
        replaces=[
            ("c01318bab7ee1f5ba734172bf7718b5dc6ec90e1", avatar_safe.address[2:])
        ],
    )
    disassembler_address = accounts[4].address
    private_key = accounts[4].key
    role = 4

    disassembler_instance = disassembler.Disassembler()
    blockchain = Chain.get_blockchain_from_web3(w3)
    ctx = GenericTxContext(w3=w3, avatar_safe_address=avatar_safe.address)
    AURA_WETH_BPT_address = "0xCfCA23cA9CA720B6E98E3Eb9B6aa0fFC4a5C08B9"
    AURA_WETH_aura_rewards_address = "0x1204f5060bE8b716F5A62b4Df4cE32acD01a69f5"

    steal_token(
        w3=w3,
        token=AURA_WETH_BPT_address,
        holder="0xC166b67C8D94C1c1F9AfDe897E8CA5d05Cd2385c",
        to=avatar_safe.address,
        amount=1_000_000_000_000_000_000,
    )

    approve_BPT = ApproveForBooster(token= AURA_WETH_BPT_address, amount=1_000_000_000_000_000_000)
    roles.send([approve_BPT], role=4, private_key=accounts[4].key, roles_mod_address=roles_contract.address, web3=w3)
    deposit_BPT = DepositBPT(pool_id=100, amount=1_000_000_000_000_000_000)
    roles.send([deposit_BPT], role=4, private_key=accounts[4].key, roles_mod_address=roles_contract.address, web3=w3)

    aura_rewards_contract = w3.eth.contract(
        address=AURA_WETH_aura_rewards_address, abi=Abis[blockchain].BaseRewardPool.abi
    )

    aura_token_balance = aura_rewards_contract.functions.balanceOf(avatar_safe.address).call()
    assert aura_token_balance == 1_000_000_000_000_000_000

    txn_transactable = aura.Withdraw.get_txns(
        ctx=ctx,
        arguments=aura.Withdraw.Args(rewards_address=AURA_WETH_aura_rewards_address, amount=1_000_000_000_000_000_000)

    )
    # Since we don't have the private key of the disassembler, we need to build the transaction and send it "manually"
    txn = disassembler_instance.build(txn_transactable, from_address=disassembler_address)
    w3.eth.send_transaction(txn)

    aura_token_balance_after = aura_rewards_contract.functions.balanceOf(avatar_safe.address).call()
    assert aura_token_balance_after == 0
    assert aura_token_balance_after == int(Decimal(aura_token_balance) / Decimal(2))