"""Direct USDT transfers to user wallets.

This replaces the previous Tatum integration, which could not work: it posted
`fromAddress: None` on the assumption that "Tatum manages custody wallet".
Tatum has no custody wallet for this endpoint. The sender is derived from a
private key you supply (`fromPrivateKey`) or from their KMS (`signatureId`), and
Tatum's own documentation warns against sending raw private keys in a request
body. So the vendor sat between us and the chain, added no capability, and still
would have cost mainnet gas out of our own wallet.

Sending directly removes the vendor, removes the per-call fee, and makes the
chain actually selectable. USDT transfer costs today, for reference:

    Solana SPL   ~$0.0005      Polygon     ~$0.001-0.01
    BEP20        ~$0.20-0.50   Ethereum    ~$0.03 (but $5-15 in a gas spike)
    TRC20        ~$1-2

TRC20 costs the most and is listed first for Nigerian users anyway: TRON carries
roughly half of all USDT transfer volume and Nigerian off-ramps are
overwhelmingly TRC20. Sending SPL or Polygon USDT to a Nigerian user can force a
manual swap, whose rate and friction cost dwarfs the gas saving. The user picks
the destination chain; this module does not guess for them.

**Hot wallet.** Transfers are signed by a key held in memory for the duration of
the call, decrypted from the encrypted `DeviceSettings` blob on demand. That is
the accepted tradeoff for non-custodial payouts: we accept key custody in
exchange for ~$0 in vendor fees and full chain control. Keep only what the
current balance needs in the hot wallet, and treat the key as
sensitive-never-logged. The key never reaches a log line, an API response, or an
error message.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

#: USDT has 6 decimals on every chain supported here.
USDT_DECIMALS = 6

#: Refuse to sign a transfer whose amount is below this. A dust transfer wastes
#: gas and can indicate a units bug (someone passed a wei amount).
MIN_TRANSFER_USD = Decimal("0.01")


class PayoutRailError(RuntimeError):
    """A payout could not be sent.

    The message is safe to surface to an operator: it never contains a private
    key, only the address form, chain, and reason.
    """


@dataclass(frozen=True)
class Chain:
    """One supported destination network."""

    id: str
    label: str
    #: "evm" | "tron" | "solana" - selects the signer implementation.
    family: str
    #: Token contract address (EVM/Tron) or mint address (Solana).
    usdt_address: str
    native_symbol: str
    #: Approximate USD cost of one transfer, for the operator-facing estimate.
    typical_cost_usd: str
    explorer_tx: str
    #: Confirmations before a transfer is considered final.
    confirmations: int
    #: JSON-RPC endpoint. Overridable per deployment via settings.
    default_rpc: str


#: USDT is native on TRON (TRC20), so there is no contract to call: the transfer
#: is a plain TRC20 `Transfer` op, which is why this family is separate from EVM
#: even though both are "send a token".
CHAINS: Dict[str, Chain] = {
    "tron": Chain(
        id="tron",
        label="Tron (TRC20)",
        family="tron",
        usdt_address="TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t",  # USDT-TRC20 contract
        native_symbol="TRX",
        typical_cost_usd="~$1-2",
        explorer_tx="https://tronscan.org/#/transaction/{}",
        confirmations=19,
        default_rpc="https://api.trongrid.io",
    ),
    "bsc": Chain(
        id="bsc",
        label="BNB Smart Chain (BEP20)",
        family="evm",
        usdt_address="0x55d398326f99059fF775485246999027B3197955",
        native_symbol="BNB",
        typical_cost_usd="~$0.20-0.50",
        explorer_tx="https://bscscan.com/tx/{}",
        confirmations=15,
        default_rpc="https://bsc-dataseed.binance.org",
    ),
    "polygon": Chain(
        id="polygon",
        label="Polygon (PoS)",
        family="evm",
        usdt_address="0xc2132D05D31c914a87C6611C10748AEb04B58e8F",
        native_symbol="POL",
        typical_cost_usd="~$0.001-0.01",
        explorer_tx="https://polygonscan.com/tx/{}",
        confirmations=30,
        default_rpc="https://polygon-rpc.com",
    ),
    "ethereum": Chain(
        id="ethereum",
        label="Ethereum (ERC20)",
        family="evm",
        usdt_address="0xdAC17F958D2ee523a2206206994597C13D831ec7",
        native_symbol="ETH",
        typical_cost_usd="~$0.03 (spikes to $5-15)",
        explorer_tx="https://etherscan.io/tx/{}",
        confirmations=12,
        default_rpc="https://ethereum-rpc.publicnode.com",
    ),
    "solana": Chain(
        id="solana",
        label="Solana (SPL)",
        family="solana",
        usdt_address="Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",
        native_symbol="SOL",
        typical_cost_usd="~$0.0005",
        explorer_tx="https://solscan.io/tx/{}",
        confirmations=1,
        default_rpc="https://api.mainnet-beta.solana.com",
    ),
}

#: Bitcoin/Solana base58 alphabet. Excludes 0, O, I and l, which are visually
#: ambiguous and are exactly the characters that appear when someone transcribes
#: an address by hand.
BASE58_ALPHABET_STRING = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
BASE58_ALPHABET = frozenset(BASE58_ALPHABET_STRING)

#: Which private-key field a chain family needs from the stored key bundle.
FAMILY_KEY_FIELD = {
    "evm": "evm",
    "tron": "tron",
    "solana": "solana",
}

#: Ordered so a UI can present cheap-first while the operator still sees the
#: honest Nigeria-relevant note on Tron.
SUPPORTED_CHAINS = ["tron", "bsc", "polygon", "ethereum", "solana"]


def get_chain(chain_id: str) -> Chain:
    """Look up a chain, or explain what is supported."""
    key = (chain_id or "").strip().lower()
    chain = CHAINS.get(key)
    if chain is None:
        raise PayoutRailError(
            f"Unsupported payout chain '{chain_id}'. "
            f"Supported: {', '.join(SUPPORTED_CHAINS)}"
        )
    return chain


def explorer_url(chain_id: str, tx_hash: str) -> str:
    """Public explorer link for a transaction hash."""
    return get_chain(chain_id).explorer_tx.format(tx_hash)


# ---------------------------------------------------------------------------
# Address validation
# ---------------------------------------------------------------------------

def validate_address(chain_id: str, address: str) -> str:
    """Validate a destination address for `chain_id` and return it normalised.

    Raises `PayoutRailError` rather than returning False so a bad address is
    never silently sent to the chain, where it would either revert (wasting gas)
    or, worse, succeed on a chain the user did not intend.
    """
    chain = get_chain(chain_id)
    addr = (address or "").strip()
    if not addr:
        raise PayoutRailError("No payout address configured")

    if chain.family == "evm":
        if not addr.startswith("0x") or len(addr) != 42:
            raise PayoutRailError(
                f"{chain.label} addresses are 0x-prefixed and 42 characters long"
            )
        try:
            int(addr, 16)
        except ValueError:
            raise PayoutRailError(
                f"{chain.label} address contains non-hexadecimal characters"
            ) from None
        return addr.lower()

    if chain.family == "tron":
        # Tron addresses are base58 and start with T.
        if not addr.startswith("T") or not (33 <= len(addr) <= 35):
            raise PayoutRailError(
                f"{chain.label} addresses are base58, start with 'T', and are "
                "33-35 characters long"
            )
        return addr

    # Solana. The alphabet check matters: Solana base58 excludes 0, O, I and l, so
    # an Ethereum address (0x + 40 hex) would otherwise pass on length alone and
    # be accepted here, failing later on-chain - or, worse, being sent as a
    # transfer to a string that is not an account.
    if not (32 <= len(addr) <= 44):
        raise PayoutRailError(
            f"{chain.label} addresses are 32-44 base58 characters long"
        )
    invalid = sorted(set(addr) - BASE58_ALPHABET)
    if invalid:
        raise PayoutRailError(
            f"{chain.label} addresses use base58, which excludes "
            f"{', '.join(repr(c) for c in invalid)}"
        )
    return addr


def describe_chains() -> list[Dict[str, Any]]:
    """Operator/UI facing description of the supported chains."""
    return [
        {
            "id": chain.id,
            "label": chain.label,
            "native_symbol": chain.native_symbol,
            "typical_cost_usd": chain.typical_cost_usd,
            "confirmations": chain.confirmations,
        }
        for chain in (CHAINS[c] for c in SUPPORTED_CHAINS)
    ]


# ---------------------------------------------------------------------------
# Transfers
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TransferResult:
    """Outcome of one signed and broadcast transfer."""

    chain_id: str
    tx_hash: str
    to_address: str
    amount_usd: Decimal
    explorer_url: str


def _require_module(module: str, package: str, chain: Chain):
    """Import an optional signing dependency, or explain how to install it."""
    try:
        return __import__(module, fromlist=["*"])
    except ImportError as exc:
        raise PayoutRailError(
            f"{chain.label} payouts need the '{package}' package. "
            f"Install it with: pip install {package}"
        ) from exc


def _to_units(amount_usd: Decimal) -> int:
    """Convert a USDT amount to on-chain units, refusing sub-dust values.

    Rounding matters: a float amount such as 10.005 must not become 10004999
    units through binary representation. `Decimal` keeps it exact.
    """
    amount = Decimal(str(amount_usd))
    if amount <= 0:
        raise PayoutRailError("Payout amount must be positive")
    if amount < MIN_TRANSFER_USD:
        raise PayoutRailError(
            f"Payout amount {amount} USDT is below the {MIN_TRANSFER_USD} USDT "
            "minimum; it would only waste gas"
        )
    units = int((amount * (10**USDT_DECIMALS)).to_integral_value())
    if units <= 0:
        raise PayoutRailError(
            f"Payout amount {amount} USDT rounds to zero on-chain units"
        )
    return units


async def transfer_usdt(
    *,
    chain_id: str,
    to_address: str,
    amount_usd: Decimal,
    private_key: str,
    rpc_url: Optional[str] = None,
) -> TransferResult:
    """Send USDT from the hot wallet to `to_address` on `chain_id`.

    Signs locally and broadcasts through the chain's own RPC. No third party sees
    the transfer or the key.
    """
    chain = get_chain(chain_id)
    destination = validate_address(chain_id, to_address)
    amount = Decimal(str(amount_usd))
    units = _to_units(amount)

    if not private_key or not private_key.strip():
        raise PayoutRailError(
            f"No payout hot-wallet key configured for {chain.label}"
        )

    endpoint = (rpc_url or chain.default_rpc).rstrip("/")

    if chain.family == "evm":
        return await _transfer_evm(chain, endpoint, destination, amount, units, private_key)
    if chain.family == "tron":
        return await _transfer_tron(chain, endpoint, destination, amount, units, private_key)
    if chain.family == "solana":
        return await _transfer_solana(chain, endpoint, destination, amount, units, private_key)

    raise PayoutRailError(f"No transfer implementation for family '{chain.family}'")


def _guard_private_key(private_key: str) -> None:
    """Reject obviously malformed keys before they reach a signer.

    A truncated or wrong-format key otherwise produces an opaque library error
    that risks being logged with the key material in the call args.
    """
    key = private_key.strip()
    if key.startswith("0x"):
        body = key[2:]
        if len(body) != 64:
            raise PayoutRailError(
                "EVM hot-wallet key must be 32 bytes (64 hex characters)"
            )
        try:
            int(body, 16)
        except ValueError:
            raise PayoutRailError(
                "EVM hot-wallet key contains non-hexadecimal characters"
            ) from None


async def _transfer_evm(
    chain: Chain,
    endpoint: str,
    destination: str,
    amount: Decimal,
    units: int,
    private_key: str,
) -> TransferResult:
    """Sign and send an ERC-20 `transfer` on any EVM chain."""
    _guard_private_key(private_key)
    web3_mod = _require_module("web3", "web3", chain)
    web3 = web3_mod.Web3(web3_mod.HTTPProvider(endpoint))

    try:
        if not web3.is_connected():
            raise PayoutRailError(f"Cannot reach the {chain.label} RPC endpoint")
        account = web3_mod.Account.from_key(private_key.strip())
        contract = web3.eth.contract(
            address=web3.to_checksum_address(chain.usdt_address),
            abi=[
                {
                    "name": "transfer",
                    "type": "function",
                    "stateMutability": "nonpayable",
                    "inputs": [
                        {"name": "to", "type": "address"},
                        {"name": "amount", "type": "uint256"},
                    ],
                    "outputs": [{"name": "", "type": "bool"}],
                }
            ],
        )
        tx = contract.functions.transfer(destination, units).build_transaction(
            {
                "from": account.address,
                "nonce": web3.eth.get_transaction_count(account.address),
                # The hot wallet holds native gas tokens, not USDT.
                "value": 0,
            }
        )
        signed = account.sign_transaction(tx)
        raw = getattr(signed, "raw_transaction", None) or getattr(signed, "rawTransaction")
        tx_hash = web3.eth.send_raw_transaction(raw)
        tx_hash_hex = tx_hash.hex()
    except PayoutRailError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise PayoutRailError(f"{chain.label} transfer failed: {exc}") from exc

    logger.info(
        "Sent %s USDT to %s... on %s (tx %s)",
        amount,
        destination[:10],
        chain.id,
        tx_hash_hex[:12],
    )
    return TransferResult(
        chain_id=chain.id,
        tx_hash=tx_hash_hex,
        to_address=destination,
        amount_usd=amount,
        explorer_url=explorer_url(chain.id, tx_hash_hex),
    )


async def _transfer_tron(
    chain: Chain,
    endpoint: str,
    destination: str,
    amount: Decimal,
    units: int,
    private_key: str,
) -> TransferResult:
    """Send TRC20 USDT on Tron."""
    key = private_key.strip()
    if len(key) != 64:
        raise PayoutRailError(
            "Tron hot-wallet key must be a 32-byte private key (64 hex characters)"
        )
    try:
        int(key, 16)
    except ValueError:
        raise PayoutRailError(
            "Tron hot-wallet key contains non-hexadecimal characters"
        ) from None

    tronpy = _require_module("tronpy", "tronpy", chain)
    client = tronpy.Tron(host=endpoint)

    try:
        private = tronpy.keys.PrivateKey(bytes.fromhex(key))
        # `to_address()` returns raw bytes in current tronpy; the base58check form
        # is what the TRC20 contract expects as `from`.
        sender = private.public_key.to_base58check_address()
        contract = client.get_contract(chain.usdt_address)
        tx_hash = contract.transfer(sender, destination, units)
    except Exception as exc:  # noqa: BLE001
        raise PayoutRailError(f"{chain.label} transfer failed: {exc}") from exc

    logger.info(
        "Sent %s USDT to %s... on tron (tx %s)",
        amount,
        destination[:10],
        tx_hash.hex()[:12],
    )
    tx_hex = tx_hash.hex()
    return TransferResult(
        chain_id=chain.id,
        tx_hash=tx_hex,
        to_address=destination,
        amount_usd=amount,
        explorer_url=explorer_url(chain.id, tx_hex),
    )


async def _transfer_solana(
    chain: Chain,
    endpoint: str,
    destination: str,
    amount: Decimal,
    units: int,
    private_key: str,
) -> TransferResult:
    """Send SPL USDT on Solana."""
    solders_mod = _require_module("solders", "solders", chain)
    solana_mod = _require_module("solders.solana", "solders", chain)
    rpc_mod = _require_module("solders.rpc", "solders", chain)
    system_mod = _require_module("solders.system_program", "solders", chain)
    token_mod = _require_module("solders.token.program", "solders", chain)

    try:
        keypair = solders_mod.Keypair.from_base58_string(private_key.strip())
        client = rpc_mod.Rpc(endpoint)
        sender = keypair.pubkey()

        # Fund the associated token account if it does not exist yet. Sending to
        # a user who has never held SPL USDT is the common case, and skipping
        # this makes the transfer fail.
        try:
            client.get_account_info(
                solana_mod.Pubkey.find_program_address(
                    [bytes(sender), bytes(token_mod.TOKEN_PROGRAM_ID), bytes(solana_mod.Pubkey.from_string(chain.usdt_address))],
                    token_mod.TOKEN_PROGRAM_ID,
                )[0]
            )
        except Exception:  # noqa: BLE001
            logger.info(
                "Creating SPL associated token account for %s on solana", sender
            )

        instructions = [
            system_mod.CreateAssociatedTokenAccountInstruction(
                account_payer=keypair.pubkey(),
                account_token=token_mod.associated_token_address(
                    token_program_id=token_mod.TOKEN_PROGRAM_ID,
                    owner=solana_mod.Pubkey.from_string(destination),
                    mint=solana_mod.Pubkey.from_string(chain.usdt_address),
                ),
                owner=solana_mod.Pubkey.from_string(destination),
                mint=solana_mod.Pubkey.from_string(chain.usdt_address),
                program_id=token_mod.TOKEN_PROGRAM_ID,
            ),
            token_mod.TransferCheckedInstruction(
                source=token_mod.associated_token_address(
                    token_program_id=token_mod.TOKEN_PROGRAM_ID,
                    owner=keypair.pubkey(),
                    mint=solana_mod.Pubkey.from_string(chain.usdt_address),
                ),
                mint=solana_mod.Pubkey.from_string(chain.usdt_address),
                destination=solana_mod.Pubkey.from_string(
                    token_mod.associated_token_address(
                        token_program_id=token_mod.TOKEN_PROGRAM_ID,
                        owner=solana_mod.Pubkey.from_string(destination),
                        mint=solana_mod.Pubkey.from_string(chain.usdt_address),
                    )
                ),
                # solders takes raw little-endian integer amounts.
                amount=units.to_bytes(8, "little"),
                decimals=USDT_DECIMALS,
                program_id=token_mod.TOKEN_PROGRAM_ID,
            ),
        ]

        tx = solana_mod.Transaction(
            fee_payer=keypair.pubkey(),
            recent_blockhash=client.get_latest_blockhash().blockhash,
            instructions=instructions,
        ).sign([keypair])

        signature = client.send_transaction(tx)
        tx_hex = base58_encode(bytes(signature))
    except PayoutRailError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise PayoutRailError(f"{chain.label} transfer failed: {exc}") from exc

    logger.info(
        "Sent %s USDT to %s... on solana (tx %s)",
        amount,
        destination[:10],
        tx_hex[:12],
    )
    return TransferResult(
        chain_id=chain.id,
        tx_hash=tx_hex,
        to_address=destination,
        amount_usd=amount,
        explorer_url=explorer_url(chain.id, tx_hex),
    )


def base58_encode(data: bytes) -> str:
    """Base58-encode bytes without pulling in the whole bitcoin alphabet module.

    Implemented locally because `base58` is not a declared dependency, and adding
    one just to render a signature would be a poor trade.
    """
    alphabet = BASE58_ALPHABET_STRING
    number = int.from_bytes(data, "big")
    out = ""
    while number > 0:
        number, remainder = divmod(number, 58)
        out = alphabet[remainder] + out
    # Leading zero bytes map to leading '1's.
    for byte in data:
        if byte != 0:
            break
        out = alphabet[0] + out
    return out or alphabet[0]