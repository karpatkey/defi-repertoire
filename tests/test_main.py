from dataclasses import dataclass
from unittest.mock import ANY, patch

from defabipedia.types import Chain
from fastapi.testclient import TestClient
from roles_royce.generic_method import TxData

from defi_repertoire.main import app
from defi_repertoire.strategies.disassembling.disassembling_balancer import (
    WithdrawAllAssetsProportional,
)
from tests.vcr import my_vcr

client = TestClient(app)


def test_read_main():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "DeFi Repertoire API"}


@my_vcr.use_cassette()
def test_list_ethereum_strategies():
    response = client.get("/strategies/ethereum")
    assert response.status_code == 200, response.text

    first_strategy = response.json()["strategies"][0]
    assert "id" in first_strategy
    assert "protocol" in first_strategy
    assert "name" in first_strategy
    assert "kind" in first_strategy
    assert "arguments" in first_strategy


@my_vcr.use_cassette()
def test_list_gnosis_strategies():
    response = client.get("/strategies/gnosis")
    assert response.status_code == 200, response.text

    strategies = response.json()["strategies"]
    # __import__("pprint").pprint(strategies)
    first_strategy = strategies[0]
    assert "id" in first_strategy
    assert "protocol" in first_strategy
    assert "name" in first_strategy
    assert "kind" in first_strategy
    assert "arguments" in first_strategy


def test_multiple_strategies():
    with patch.object(Chain, "get_blockchain_from_web3", lambda x: Chain.ETHEREUM):
        response = client.post(
            "/strategies-to-transactions/?"
            "blockchain=ethereum&"
            "avatar_safe_address=0x8353157092ED8Be69a9DF8F95af097bbF33Cb2aF&",
            json=[
                {
                    "id": "dsr__withdraw_without_proxy",
                    "arguments": {
                        "amount": 10,
                    },
                }
            ],
        )
        assert response.json() == {
            "txns": [
                {
                    "operation": 0,
                    "data": "0x095ea7b3000000000000000000000000373238337bfe1146fb49989fc222523f83081ddb000000000000000000000000000000000000000000000000000000000000000a",
                    "value": 0,
                    "contract_address": "0x6B175474E89094C44Da98b954EedeAC495271d0F",
                },
                {
                    "operation": 0,
                    "data": "0xef693bed0000000000000000000000008353157092ed8be69a9df8f95af097bbf33cb2af000000000000000000000000000000000000000000000000000000000000000a",
                    "value": 0,
                    "contract_address": "0x373238337Bfe1146fb49989fc222523f83081dDb",
                },
            ]
        }

        # Using multisend
        response = client.post(
            "/strategies-to-transactions/?"
            "blockchain=ethereum&"
            "avatar_safe_address=0x8353157092ED8Be69a9DF8F95af097bbF33Cb2aF&"
            "multisend=true",
            json=[
                {
                    "id": "dsr__withdraw_without_proxy",
                    "arguments": {
                        "amount": 10,
                    },
                }
            ],
        )
        assert response.json() == {
            "txns": [
                {
                    "contract_address": "0xA238CBeb142c10Ef7Ad8442C6D1f9E89e07e7761",
                    "data": "0x8d80ff0a00000000000000000000000000000000000000000000000000000000000000200000000000000000000000000000000000000000000000000000000000000132006b175474e89094c44da98b954eedeac495271d0f00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000044095ea7b3000000000000000000000000373238337bfe1146fb49989fc222523f83081ddb000000000000000000000000000000000000000000000000000000000000000a00373238337bfe1146fb49989fc222523f83081ddb00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000044ef693bed0000000000000000000000008353157092ed8be69a9df8f95af097bbf33cb2af000000000000000000000000000000000000000000000000000000000000000a0000000000000000000000000000",
                    "operation": 1,
                    "value": 0,
                }
            ]
        }


def test_exec_with_role():
    with patch.object(Chain, "get_blockchain_from_web3", lambda x: Chain.ETHEREUM):
        response = client.post(
            "/strategies-to-exec-with-role/?"
            "blockchain=ethereum&"
            "avatar_safe_address=0x8353157092ED8Be69a9DF8F95af097bbF33Cb2aF&"
            "roles_mod_address=0x8C33ee6E439C874713a9912f3D3debfF1Efb90Da&"
            "role=1",
            json=[
                {
                    "id": "dsr__withdraw_without_proxy",
                    "arguments": {
                        "amount": 10,
                    },
                }
            ],
        )

        assert response.json() == {
            "txn": {
                "contract_address": "0x8C33ee6E439C874713a9912f3D3debfF1Efb90Da",
                "data": "0xc6fe8747000000000000000000000000a238cbeb142c10ef7ad8442c6d1f9e89e07e7761000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000c000000000000000000000000000000000000000000000000000000000000000013100000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000100000000000000000000000000000000000000000000000000000000000001848d80ff0a00000000000000000000000000000000000000000000000000000000000000200000000000000000000000000000000000000000000000000000000000000132006b175474e89094c44da98b954eedeac495271d0f00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000044095ea7b3000000000000000000000000373238337bfe1146fb49989fc222523f83081ddb000000000000000000000000000000000000000000000000000000000000000a00373238337bfe1146fb49989fc222523f83081ddb00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000044ef693bed0000000000000000000000008353157092ed8be69a9df8f95af097bbf33cb2af000000000000000000000000000000000000000000000000000000000000000a000000000000000000000000000000000000000000000000000000000000000000000000000000000000",
                "operation": 0,
                "value": 0,
            },
            "decoded": {
                "txn": {
                    "contract_address": "0x8C33ee6E439C874713a9912f3D3debfF1Efb90Da",
                    "data": "0xc6fe8747000000000000000000000000a238cbeb142c10ef7ad8442c6d1f9e89e07e7761000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000c000000000000000000000000000000000000000000000000000000000000000013100000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000100000000000000000000000000000000000000000000000000000000000001848d80ff0a00000000000000000000000000000000000000000000000000000000000000200000000000000000000000000000000000000000000000000000000000000132006b175474e89094c44da98b954eedeac495271d0f00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000044095ea7b3000000000000000000000000373238337bfe1146fb49989fc222523f83081ddb000000000000000000000000000000000000000000000000000000000000000a00373238337bfe1146fb49989fc222523f83081ddb00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000044ef693bed0000000000000000000000008353157092ed8be69a9df8f95af097bbf33cb2af000000000000000000000000000000000000000000000000000000000000000a000000000000000000000000000000000000000000000000000000000000000000000000000000000000",
                    "operation": 0,
                    "value": 0,
                },
                "decoded": {
                    "name": "execTransactionWithRole",
                    "inputs": {
                        "to": "0xA238CBeb142c10Ef7Ad8442C6D1f9E89e07e7761",
                        "value": 0,
                        "data": "0x8d80ff0a00000000000000000000000000000000000000000000000000000000000000200000000000000000000000000000000000000000000000000000000000000132006b175474e89094c44da98b954eedeac495271d0f00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000044095ea7b3000000000000000000000000373238337bfe1146fb49989fc222523f83081ddb000000000000000000000000000000000000000000000000000000000000000a00373238337bfe1146fb49989fc222523f83081ddb00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000044ef693bed0000000000000000000000008353157092ed8be69a9df8f95af097bbf33cb2af000000000000000000000000000000000000000000000000000000000000000a0000000000000000000000000000",
                        "operation": 1,
                        "role_key": "0x3100000000000000000000000000000000000000000000000000000000000000",
                        "should_revert": True,
                    },
                },
                "children": [
                    {
                        "txn": {
                            "contract_address": "0xA238CBeb142c10Ef7Ad8442C6D1f9E89e07e7761",
                            "data": "0x8d80ff0a00000000000000000000000000000000000000000000000000000000000000200000000000000000000000000000000000000000000000000000000000000132006b175474e89094c44da98b954eedeac495271d0f00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000044095ea7b3000000000000000000000000373238337bfe1146fb49989fc222523f83081ddb000000000000000000000000000000000000000000000000000000000000000a00373238337bfe1146fb49989fc222523f83081ddb00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000044ef693bed0000000000000000000000008353157092ed8be69a9df8f95af097bbf33cb2af000000000000000000000000000000000000000000000000000000000000000a0000000000000000000000000000",
                            "operation": 1,
                            "value": 0,
                        },
                        "decoded": {
                            "name": "multiSend",
                            "inputs": {
                                "transactions": "0x006b175474e89094c44da98b954eedeac495271d0f00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000044095ea7b3000000000000000000000000373238337bfe1146fb49989fc222523f83081ddb000000000000000000000000000000000000000000000000000000000000000a00373238337bfe1146fb49989fc222523f83081ddb00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000044ef693bed0000000000000000000000008353157092ed8be69a9df8f95af097bbf33cb2af000000000000000000000000000000000000000000000000000000000000000a"
                            },
                        },
                        "children": [
                            {
                                "txn": {
                                    "contract_address": "0x6B175474E89094C44Da98b954EedeAC495271d0F",
                                    "data": "0x095ea7b3000000000000000000000000373238337bfe1146fb49989fc222523f83081ddb000000000000000000000000000000000000000000000000000000000000000a",
                                    "operation": 0,
                                    "value": 0,
                                },
                                "decoded": {
                                    "name": "approve",
                                    "inputs": {
                                        "spender": "0x373238337Bfe1146fb49989fc222523f83081dDb",
                                        "amount": 10,
                                    },
                                },
                                "children": None,
                            },
                            {
                                "txn": {
                                    "contract_address": "0x373238337Bfe1146fb49989fc222523f83081dDb",
                                    "data": "0xef693bed0000000000000000000000008353157092ed8be69a9df8f95af097bbf33cb2af000000000000000000000000000000000000000000000000000000000000000a",
                                    "operation": 0,
                                    "value": 0,
                                },
                                "decoded": {
                                    "name": "exit",
                                    "inputs": {
                                        "dst": "0x8353157092ED8Be69a9DF8F95af097bbF33Cb2aF",
                                        "wad": 10,
                                    },
                                },
                                "children": None,
                            },
                        ],
                    }
                ],
            },
        }


def test_disassembly_balancer():
    with patch.object(Chain, "get_blockchain_from_web3", lambda x: Chain.ETHEREUM):
        with patch.object(WithdrawAllAssetsProportional, "get_txns") as exit_strategy:
            tx_data = "0x8bdb39138353157092ed8be69a9df8f95af097bbf33cb2a..."
            vault_address = "0xBA12222222228d8Ba445958a75a0704d566BF2C8"
            exit_strategy.return_value = [
                TxData(
                    data=tx_data, operation=0, value=0, contract_address=vault_address
                )
            ]

            response = client.post(
                "/txns/disassembly/balancer/withdraw_all_assets_proportional?"
                "blockchain=ethereum&"
                "avatar_safe_address=0x8353157092ED8Be69a9DF8F95af097bbF33Cb2aF&",
                json={
                    "bpt_address": "0x8353157092ED8Be69a9DF8F95af097bbF33Cb2aF",
                    "max_slippage": 0.2,
                    "amount": 10,
                },
            )

            assert response.status_code == 200, response.text
            exit_strategy.assert_called_with(
                ctx=ANY,
                arguments=WithdrawAllAssetsProportional.Args(
                    **{
                        "bpt_address": "0x8353157092ED8Be69a9DF8F95af097bbF33Cb2aF",
                        "max_slippage": 0.2,
                        "amount": 10,
                    }
                ),
            )
            assert response.json() == {
                "txns": [
                    {
                        "data": tx_data,
                        "operation": 0,
                        "value": 0,
                        "contract_address": vault_address,
                    }
                ]
            }

            response = client.post(
                "/txns/disassembly/balancer/withdraw_all_assets_proportional/?"
                "blockchain=ethereum&"
                "avatar_safe_address=0x8353157092ED8Be69a9DF8F95af097bbF33Cb2aF&",
                json={
                    "bpt_address": "0x8353157092ED8Be69a9DF8F95af097bbF33Cb2aF",
                    "max_slippage": 0.2,
                    "amount": 10,
                },
            )

            assert response.status_code == 200, response.text
            exit_strategy.assert_called_with(
                ctx=ANY,
                arguments=WithdrawAllAssetsProportional.Args(
                    **{
                        "bpt_address": "0x8353157092ED8Be69a9DF8F95af097bbF33Cb2aF",
                        "max_slippage": 0.2,
                        "amount": 10,
                    }
                ),
            )
            assert response.json() == {
                "txns": [
                    {
                        "data": tx_data,
                        "operation": 0,
                        "value": 0,
                        "contract_address": vault_address,
                    }
                ]
            }


def test_multisend():
    with patch.object(Chain, "get_blockchain_from_web3", lambda x: Chain.ETHEREUM):
        ctract = "0xCB664132622f29943f67FA56CCfD1e24CC8B4995"

        response = client.post(
            "/multisend-transactions/?" "blockchain=ethereum",
            json=[
                {
                    "contract_address": ctract,
                    "data": "0xb6b55f25000000000000000000000000000000000000000000000000016513bc209d8bba",
                    "operation": 0,
                    "value": 0,
                },
                {
                    "contract_address": ctract,
                    "data": "0xb6b55f25000000000000000000000000000000000000000000000000016513bc209d8bba",
                    "operation": 0,
                    "value": 0,
                },
            ],
        )

        assert response.status_code == 200
        assert response.json() == {
            "txn": {
                "data": "0x8d80ff0a000000000000000000000000000000000000000000000000000000000000002000000000000000000000000000000000000000000000000000000000000000f200cb664132622f29943f67fa56ccfd1e24cc8b499500000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000024b6b55f25000000000000000000000000000000000000000000000000016513bc209d8bba00cb664132622f29943f67fa56ccfd1e24cc8b499500000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000024b6b55f25000000000000000000000000000000000000000000000000016513bc209d8bba0000000000000000000000000000",
                "operation": 1,
                "value": 0,
                "contract_address": "0xA238CBeb142c10Ef7Ad8442C6D1f9E89e07e7761",
            }
        }
