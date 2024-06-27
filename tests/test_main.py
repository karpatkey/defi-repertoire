from dataclasses import dataclass
from fastapi.testclient import TestClient
from unittest.mock import patch, ANY
from defi_repertoire.main import app
from defabipedia.types import Chain
from defi_repertoire.strategies.disassembling.disassembling_balancer import (
    WithdrawAllAssetsProportional,
)
from roles_royce.generic_method import TxData

client = TestClient(app)


def test_read_main():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "DeFi Repertoire API"}


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
                "/txns/disassembly/balancer/withdrawallassetsproportional/?"
                "blockchain=ethereum&"
                "avatar_safe_address=0x849D52316331967b6fF1198e5E32A0eB168D039d&",
                json=[
                    {
                        "bpt_address": "0x8353157092ED8Be69a9DF8F95af097bbF33Cb2aF",
                        "max_slippage": 0.2,
                        "amount": 10,
                    }
                ],
            )
            exit_strategy.assert_called_with(
                ctx=ANY,
                arguments=[
                    {
                        "bpt_address": "0x8353157092ED8Be69a9DF8F95af097bbF33Cb2aF",
                        "max_slippage": 0.2,
                        "amount": 10,
                    }
                ],
            )
            assert response.status_code == 200
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
