from roles_royce import roles
from roles_royce.generic_method import Transactable
from web3 import Web3
from web3.types import Address, ChecksumAddress, TxParams, TxReceipt

from defi_repertoire.strategies.base import GenericTxContext


class Disassembler:
    def send(
        self,
        ctx: GenericTxContext,
        roles_mod_address: str,
        role,
        txns: list[Transactable],
        private_key: str,
        w3: Web3 = None,
    ) -> TxReceipt:
        """Executes the multisend batched transaction built from the transactables.

        Args:
            txns (list[Transactable]): List of transactions to execute
            private_key (str): Private key of the account to execute the transactions from
            w3 (Web3): Web3 instance to execute the transactions from that would override the self.w3 instance if w3 is
                not None. Useful for nodes with MEV protection to be used only for eth_sendTransaction. Defaults to None

        Returns:
            Transaction receipt as a TxReceipt object
        """
        if w3 is None:
            w3 = ctx.w3
        return roles.send(
            txns,
            role=role,
            private_key=private_key,
            roles_mod_address=roles_mod_address,
            web3=w3,
        )

    def check(
        self,
        txns: list[Transactable],
        block: int | str = "latest",
        from_address: Address | ChecksumAddress | str | None = None,
        role: int = None,
        roles_mod_address: str = None,
        w3: Web3 = None,
    ) -> bool:
        """Checks whether the multisend batched transaction built from the transactables is successfully executed with static call.

        Args:
            txns (list[Transactable]): List of transactions to execute
            block: int | str = 'latest': block number to check the transaction at
            from_address (Address | ChecksumAddress | str, optional): from address that overrides the ones in txns.
        Returns:
            True if the transaction was successfully executed, False if it reverted.
        """
        if from_address:
            account = from_address
        else:
            raise ValueError(
                "Either from_address or self.signer_address must be provided."
            )
        return roles.check(
            txns,
            role=role,
            account=account,
            roles_mod_address=roles_mod_address,
            web3=w3,
            block=block,
        )

    def build(
        self,
        txns: list[Transactable],
        from_address: Address | ChecksumAddress | str | None = None,
        role: int = None,
        roles_mod_address: str = None,
        w3: Web3 = None,
    ) -> TxParams:
        """Builds a multisend batched transaction from the transactables.

        Args:
            txns (list[Transactable]): List of transactions to execute
            from_address (Address | ChecksumAddress | str, optional): from address that overrides the ones in txns.
        Returns:
            Transaction dictionary as a TxParams object.
        """
        if from_address is not None:
            account = from_address
        else:
            raise ValueError(
                "Either from_address or self.signer_address must be provided."
            )
        return roles.build(
            txns,
            role=role,
            account=account,
            roles_mod_address=roles_mod_address,
            web3=w3,
        )


def validate_percentage(percentage: float) -> float:
    if percentage <= 0 or percentage > 100:
        raise ValueError(
            "Percentage of liquidity to remove must be greater than 0 and less or equal than 100."
        )
    else:
        return percentage / 100
