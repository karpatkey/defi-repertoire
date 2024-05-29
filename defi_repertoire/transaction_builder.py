from dataclasses import dataclass, field

from defabipedia.types import Blockchain, Chain
from web3 import Web3
from web3.types import Address, ChecksumAddress, TxParams, TxReceipt
from typing_extensions import TypedDict

from roles_royce import roles
from roles_royce.generic_method import Transactable
from roles_royce.utils import to_checksum_address

RolesModMasterCopy = {
    Chain.ETHEREUM: '0xD8DfC1d938D7D163C5231688341e9635E9011889',
    Chain.GNOSIS: '0xD8DfC1d938D7D163C5231688341e9635E9011889'}

@dataclass
class TransactionBuilder:
    w3: Web3
    avatar_safe_address: Address | ChecksumAddress | str
    role: int
    blockchain: Blockchain = field(init=False)

    def __post_init__(self):
        self.avatar_safe_address = to_checksum_address(self.avatar_safe_address)
        self.blockchain = Chain.get_blockchain_from_web3(self.w3)

    def send(self, roles_mod_address: str, txns: list[Transactable], private_key: str, w3: Web3 = None) -> TxReceipt:
        """Executes the multisend batched transaction built from the transactables.

        Args:
            txns (list[Transactable]): List of transactions to execute
            roles_mod_address (str): Address of the roles modifier contract
            private_key (str): Private key of the account to execute the transactions from
            w3 (Web3): Web3 instance to execute the transactions from that would override the self.w3 instance if w3 is
                not None. Useful for nodes with MEV protection to be used only for eth_sendTransaction. Defaults to None

        Returns:
            Transaction receipt as a TxReceipt object
        """
        if w3 is None:
            w3 = self.w3
        return roles.send(
            txns, role=self.role, private_key=private_key, roles_mod_address=roles_mod_address, web3=w3
        )

    def check(
            self,
            roles_mod_address: str,
            txns: list[Transactable],
            from_address: Address | ChecksumAddress | str,
            block: int | str = "latest"
    ) -> bool:
        """Checks whether the multisend batched transaction built from the transactables is successfully executed with static call.

        Args:
            txns (list[Transactable]): List of transactions to execute
            block: int | str = 'latest': block number to check the transaction at
            from_address (Address | ChecksumAddress | str, optional): from address that overrides the ones in txns.
        Returns:
            True if the transaction was successfully executed, False if it reverted.
        """
        return roles.check(
            txns, role=self.role, account=from_address, roles_mod_address=roles_mod_address, web3=self.w3, block=block
        )

    def build(self, txns: list[Transactable], from_address: Address | ChecksumAddress | str | None = None) -> TxParams:
        """Builds a multisend batched transaction from the transactables.

        Args:
            txns (list[Transactable]): List of transactions to execute
            from_address (Address | ChecksumAddress | str, optional): from address that overrides the ones in txns.
        Returns:
            Transaction dictionary as a TxParams object.
        """
        if from_address is not None:
            account = from_address
        elif self.signer_address is not None:
            account = self.signer_address
        else:
            raise ValueError("Either from_address or self.signer_address must be provided.")
        return roles.build(
            txns, role=self.role, account=account, roles_mod_address=RolesModMasterCopy[self.blockchain], web3=self.w3
        )

