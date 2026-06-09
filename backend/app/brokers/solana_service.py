"""
Solana/Jupiter Broker Service - DeFi trading on Solana.
Uses Jupiter DEX aggregator for optimal swap routing.

Docs: https://docs.jup.ag/
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
import structlog

from app.brokers.base import (
    BaseBrokerService,
    OrderResult,
    PositionData,
    AccountData,
)
from app.config import settings

logger = structlog.get_logger(__name__)

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False
    logger.warning("httpx not installed. Solana broker unavailable.")


# Common Solana token mints
SOLANA_TOKENS = {
    "SOL": "So11111111111111111111111111111111111111112",
    "USDC": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
    "USDT": "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8Benw5B",
    "BONK": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
    "JUP": "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN",
    "RAY": "4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R",
    "ORCA": "orcaEKTdK7LKz57vaAYr9QeNsVEPfiu6QeMU1kektZE",
}


class SolanaBrokerService(BaseBrokerService):
    """
    Solana/Jupiter Broker Service - DeFi trading via Jupiter DEX aggregator.

    Features:
    - Swap tokens via Jupiter aggregator
    - Best price routing across DEXes
    - Slippage control
    - Priority fee support

    Requirements:
    - Solana RPC endpoint
    - Wallet with SOL for transactions
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(name="solana", config=config or {})

        self.rpc_url = config.get("rpc_url") if config else settings.SOLANA_RPC_URL
        self.jupiter_api_key = config.get("jupiter_key") if config else settings.JUPITER_API_KEY

        # Jupiter API endpoints
        self.jupiter_url = "https://quote-api.jup.ag/v6"

        # HTTP client
        self.http_client: Optional[httpx.AsyncClient] = None

        # Wallet (for signing transactions)
        self.wallet_address: Optional[str] = None
        self.wallet_keypair: Optional[Any] = None

        if not HTTPX_AVAILABLE:
            logger.error("httpx library required for Solana broker")

    async def connect(self) -> bool:
        """
        Initialize connection to Solana RPC and Jupiter.

        Returns:
            True if initialization successful, False otherwise
        """
        if not HTTPX_AVAILABLE:
            return False

        try:
            # Create HTTP client
            self.http_client = httpx.AsyncClient(
                base_url=self.rpc_url,
                timeout=30.0,
                headers={"Content-Type": "application/json"},
            )

            # Test RPC connection
            result = await self._rpc_call("getHealth")
            
            if result == "ok":
                logger.info("Connected to Solana RPC")
                self.is_connected = True
                return True

            # Even if getHealth fails, try genesis hash
            result = await self._rpc_call("getGenesisHash")
            if result:
                logger.info("Connected to Solana RPC")
                self.is_connected = True
                return True

            logger.error("Failed to connect to Solana RPC")
            return False

        except Exception as e:
            logger.error(f"Solana connection error: {e}")
            self.is_connected = False
            return False

    async def disconnect(self):
        """Close HTTP client."""
        if self.http_client:
            await self.http_client.aclose()
            self.http_client = None
        self.is_connected = False
        logger.info("Disconnected from Solana")

    async def submit_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        order_type: str = "market",
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None,
        time_in_force: str = "day",
        client_order_id: Optional[str] = None,
    ) -> OrderResult:
        """
        Submit a swap order on Jupiter.

        Args:
            symbol: Token symbol (e.g., "SOL", "USDC") or trading pair (e.g., "SOL/USDC")
            side: "buy" (receive token) or "sell" (send token)
            quantity: Amount to sell (for sell) or amount to receive (for buy)
            order_type: "market" (Jupiter only supports market swaps)
            limit_price: Not supported (for future implementation)
            time_in_force: Not applicable (swaps execute immediately)

        Returns:
            OrderResult with swap details
        """
        if not self.is_connected:
            return OrderResult(
                success=False,
                message="Not connected to Solana RPC",
            )

        if not self.wallet_address:
            return OrderResult(
                success=False,
                message="Wallet not configured. Set wallet address before trading.",
            )

        try:
            # Parse symbol to get input/output tokens
            input_mint, output_mint, amount = await self._parse_swap_params(symbol, side, quantity)

            if not input_mint or not output_mint:
                return OrderResult(
                    success=False,
                    message=f"Unknown token in pair: {symbol}",
                )

            # Get quote from Jupiter
            quote = await self._get_quote(input_mint, output_mint, amount)

            if not quote or "error" in quote:
                return OrderResult(
                    success=False,
                    message=f"Jupiter quote error: {quote.get('error', 'Unknown error')}",
                )

            # Get swap transaction
            swap_data = await self._get_swap_transaction(quote, self.wallet_address)

            if not swap_data or "error" in swap_data:
                return OrderResult(
                    success=False,
                    message=f"Swap transaction error: {swap_data.get('error', 'Unknown error')}",
                )

            logger.info(
                "Jupiter swap prepared",
                input_token=input_mint[:8] + "...",
                output_token=output_mint[:8] + "...",
                amount_in=amount,
                expected_out=quote.get("outAmount", 0),
            )

            # Note: Actual transaction signing would happen here
            # For now, return the prepared swap data

            out_amount = float(quote.get("outAmount", 0)) / (10 ** quote.get("outDecimals", 6))

            return OrderResult(
                success=True,
                order_id=quote.get("signature") or f"swap_{datetime.utcnow().timestamp()}",
                message=f"Swap prepared: {quantity} → {out_amount}",
                filled_quantity=out_amount,
                filled_price=None,  # DEX pricing is complex
                commission=float(quote.get("priceImpactPct", 0)) * 100,  # Price impact as "commission"
            )

        except Exception as e:
            logger.error(f"Swap order error: {e}")
            return OrderResult(
                success=False,
                message=f"Swap order failed: {str(e)}",
            )

    async def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an order.

        Note: DEX swaps cannot be cancelled once broadcast.
        This method always returns False.

        Returns:
            False (swaps are irreversible)
        """
        logger.warning("Cannot cancel Solana swap - DEX transactions are irreversible")
        return False

    async def get_position(self, symbol: str) -> Optional[PositionData]:
        """
        Get token balance for a symbol.

        Args:
            symbol: Token symbol (e.g., "SOL", "USDC")

        Returns:
            PositionData if balance exists, None otherwise
        """
        if not self.is_connected:
            return None

        if not self.wallet_address:
            return None

        try:
            # Get token mint
            mint = SOLANA_TOKENS.get(symbol.upper())
            if not mint:
                return None

            # Get token balance
            balance = await self._get_token_balance(mint)

            if balance == 0:
                return None

            # Get current price in USDC
            current_price = None
            if symbol.upper() != "USDC":
                price_data = await self._get_price(symbol.upper())
                current_price = price_data.get("price")

            market_value = balance * current_price if current_price else None

            return PositionData(
                symbol=symbol.upper(),
                quantity=balance,
                avg_price=0,  # Not tracked for DEX
                current_price=current_price,
                market_value=market_value,
                unrealized_pnl=None,
                unrealized_pnl_percent=None,
                side="long",
            )

        except Exception as e:
            logger.warning(f"Error getting position for {symbol}: {e}")
            return None

    async def get_positions(self) -> List[PositionData]:
        """
        Get all token balances in wallet.

        Returns:
            List of PositionData objects
        """
        if not self.is_connected:
            return []

        if not self.wallet_address:
            return []

        try:
            # Get all token accounts
            response = await self._rpc_call(
                "getTokenAccountsByOwner",
                [
                    self.wallet_address,
                    {"programId": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ys629DM3MTDY"},
                    {"encoding": "jsonParsed"},
                ],
            )

            positions = []

            if response and "value" in response:
                for account in response["value"]:
                    parsed = account["account"]["data"]["parsed"]["info"]
                    token_amount = parsed["tokenAmount"]

                    balance = float(token_amount["uiAmount"]) if token_amount["uiAmount"] else 0
                    if balance == 0:
                        continue

                    # Get mint
                    mint = parsed["mint"]
                    symbol = self._symbol_from_mint(mint)

                    # Get price
                    current_price = None
                    if symbol != "USDC":
                        price_data = await self._get_price(symbol)
                        current_price = price_data.get("price")

                    positions.append(
                        PositionData(
                            symbol=symbol,
                            quantity=balance,
                            avg_price=0,
                            current_price=current_price,
                            market_value=balance * current_price if current_price else None,
                            unrealized_pnl=None,
                            unrealized_pnl_percent=None,
                            side="long",
                        )
                    )

            return positions

        except Exception as e:
            logger.error(f"Error getting positions: {e}")
            return []

    async def get_account(self) -> AccountData:
        """
        Get account (wallet) information.

        Returns:
            AccountData with wallet details
        """
        if not self.is_connected:
            raise RuntimeError("Not connected to Solana")

        if not self.wallet_address:
            raise RuntimeError("Wallet address not configured")

        try:
            # Get SOL balance
            sol_balance = await self._get_sol_balance()

            # Get USDC balance (as proxy for "cash")
            usdc_balance = await self._get_token_balance(SOLANA_TOKENS["USDC"])

            # Get total portfolio value in USDC
            total_value = usdc_balance + (sol_balance * await self._get_sol_price())

            return AccountData(
                account_id=self.wallet_address[:8] + "...",
                cash=usdc_balance,
                portfolio_value=total_value,
                buying_power=usdc_balance,
                equity=total_value,
                last_equity=None,  # Not tracked
                day_trading_buying_power=None,
            )

        except Exception as e:
            logger.error(f"Error getting account: {e}")
            raise

    async def get_clock(self) -> Dict[str, Any]:
        """
        Get Solana network status.

        Returns:
            Dict with network status
        """
        if not self.is_connected:
            return {"is_open": False, "error": "Not connected"}

        try:
            # Get slot and block time
            slot = await self._rpc_call("getSlot")
            block_time = await self._rpc_call("getBlockTime", [slot])

            return {
                "is_open": True,  # Solana is always available
                "slot": slot,
                "timestamp": datetime.fromtimestamp(block_time).isoformat() if block_time else None,
                "note": "Solana network operates 24/7",
            }

        except Exception as e:
            logger.error(f"Error getting clock: {e}")
            return {"is_open": False, "error": str(e)}

    async def get_order_status(self, order_id: str) -> Dict[str, Any]:
        """
        Get status of a transaction.

        Args:
            order_id: Transaction signature

        Returns:
            Dict with transaction status
        """
        if not self.is_connected:
            return {"error": "Not connected"}

        try:
            result = await self._rpc_call(
                "getTransaction",
                [
                    order_id,
                    {"encoding": "json", "maxSupportedTransactionVersion": 0},
                ],
            )

            if not result:
                return {"error": "Transaction not found", "signature": order_id}

            return {
                "signature": order_id,
                "slot": result.get("slot"),
                "status": "confirmed" if result.get("meta", {}).get("err") is None else "failed",
                "timestamp": datetime.fromtimestamp(result.get("blockTime", 0)).isoformat(),
            }

        except Exception as e:
            logger.error(f"Error getting order status: {e}")
            return {"error": str(e)}

    async def _rpc_call(self, method: str, params: Optional[List] = None) -> Any:
        """Make an RPC call to Solana."""
        if not self.http_client:
            return None

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params or [],
        }

        response = await self.http_client.post("", json=payload)
        response.raise_for_status()

        result = response.json()
        return result.get("result")

    async def _get_quote(self, input_mint: str, output_mint: str, amount: float) -> Dict:
        """Get swap quote from Jupiter."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.jupiter_url}/quote",
                params={
                    "inputMint": input_mint,
                    "outputMint": output_mint,
                    "amount": int(amount * 1_000_000),  # Assume 6 decimals
                    "slippageBps": 50,  # 0.5% slippage
                },
            )
            response.raise_for_status()
            return response.json()

    async def _get_swap_transaction(self, quote: Dict, wallet_address: str) -> Dict:
        """Get swap transaction from Jupiter."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.jupiter_url}/swap",
                json={
                    "quoteResponse": quote,
                    "userPublicKey": wallet_address,
                    "wrapAndUnwrapSol": True,
                },
            )
            response.raise_for_status()
            return response.json()

    async def _parse_swap_params(
        self, symbol: str, side: str, quantity: float
    ) -> tuple[Optional[str], Optional[str], float]:
        """Parse symbol and side into input/output mints and amount."""
        # Handle trading pair (e.g., "SOL/USDC")
        if "/" in symbol:
            parts = symbol.split("/")
            input_symbol = parts[0] if side.lower() == "sell" else parts[1]
            output_symbol = parts[1] if side.lower() == "sell" else parts[0]
        else:
            # Just a token symbol - assume trading against USDC
            if side.lower() == "sell":
                input_symbol = symbol
                output_symbol = "USDC"
            else:
                input_symbol = "USDC"
                output_symbol = symbol

        input_mint = SOLANA_TOKENS.get(input_symbol.upper())
        output_mint = SOLANA_TOKENS.get(output_symbol.upper())

        # Get decimals for amount conversion
        input_decimals = 9 if input_symbol.upper() == "SOL" else 6

        return input_mint, output_mint, quantity * (10 ** input_decimals)

    def _symbol_from_mint(self, mint: str) -> str:
        """Get token symbol from mint address."""
        for symbol, m in SOLANA_TOKENS.items():
            if m == mint:
                return symbol
        return mint[:8] + "..."  # Unknown token

    async def _get_token_balance(self, mint: str) -> float:
        """Get token balance for wallet."""
        # Find token account
        response = await self._rpc_call(
            "getTokenAccountsByOwner",
            [
                self.wallet_address,
                {"mint": mint},
                {"encoding": "jsonParsed"},
            ],
        )

        if not response or not response.get("value"):
            return 0

        account = response["value"][0]["account"]["data"]["parsed"]["info"]
        token_amount = account["tokenAmount"]
        return float(token_amount.get("uiAmount", 0))

    async def _get_sol_balance(self) -> float:
        """Get SOL balance in lamports."""
        if not self.wallet_address:
            return 0

        balance = await self._rpc_call("getBalance", [self.wallet_address])
        return (balance or 0) / 1e9  # Convert lamports to SOL

    async def _get_sol_price(self) -> float:
        """Get current SOL price in USDC."""
        price_data = await self._get_price("SOL")
        return price_data.get("price", 0)

    async def _get_price(self, symbol: str) -> Dict[str, Any]:
        """Get current price for a token."""
        mint = SOLANA_TOKENS.get(symbol.upper())
        if not mint:
            return {"price": 0}

        async with httpx.AsyncClient() as client:
            # Use Jupiter price API
            response = await client.get(
                "https://api.jup.ag/price/v2/price",
                params={"ids": mint},
            )
            response.raise_for_status()
            data = response.json()
            price_data = data.get("data", {}).get(mint, {})
            return {
                "price": float(price_data.get("price", 0)),
                "symbol": symbol,
            }

    def __repr__(self) -> str:
        return f"SolanaBrokerService(rpc={self.rpc_url[:20]}..., connected={self.is_connected})"