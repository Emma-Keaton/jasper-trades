import { useState, useEffect } from "react";
import { X, Plus, Trash2, Wallet } from "lucide-react";
import { useConnect, useSignMessage } from "wagmi";
import { useWallet } from "@solana/wallet-adapter-react";
import { API_URL } from "@/lib/constants";
import { getOrCreateDeviceId } from "@/lib/deviceFingerprint";
import DataTable from "@/components/ui/data-table";

type Credential = {
  id: number;
  exchange: string;
  wallet_address?: string;
  chain?: string;
  created_at: string;
  updated_at: string;
  api_key?: string | null;
  api_secret?: string | null;
};

/** Convert bytes to a lowercase hex string (browser-safe, avoids Buffer polyfill). */
function bytesToHex(bytes: Uint8Array): string {
  return Array.from(bytes)
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

export default function CryptoConnector() {
  const [creds, setCreds] = useState<Credential[]>([]);
  const [editing, setEditing] = useState<Partial<Credential>>({});
  const [showForm, setShowForm] = useState(false);
  const [exchanges, setExchanges] = useState<string[]>([]);
  const [showWalletModal, setShowWalletModal] = useState(false);
  const [walletType, setWalletType] = useState<string>("solana");
  const deviceId = getOrCreateDeviceId();
  const deviceHeaders = { "X-Device-ID": deviceId };
  const { connectAsync, connectors } = useConnect();
  const { signMessageAsync } = useSignMessage();
  const solanaWallet = useWallet();

  // Load stored credentials
  useEffect(() => {
    const headers = { "X-Device-ID": deviceId };
    fetch(`${API_URL}/api/v1/crypto-connector`, { headers })
      .then((r) => r.json())
      .then(setCreds)
      .catch(() => console.error("failed to load crypto creds"));
    // Load exchange list dynamically from backend
    fetch(`${API_URL}/api/v1/exchanges/`)
      .then((r) => r.json())
      .then(setExchanges)
      .catch(() => console.error("failed to load exchanges"));
  }, [deviceId]);

  const resetForm = () => {
    setEditing({});
    setShowForm(false);
  };

  const handleSave = async () => {
    await fetch(`${API_URL}/api/v1/crypto-connector`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...deviceHeaders },
      body: JSON.stringify(editing),
    });
    const refreshed = await fetch(`${API_URL}/api/v1/crypto-connector`, {
      headers: deviceHeaders,
    }).then((r) => r.json());
    setCreds(refreshed);
    resetForm();
  };

  const handleDelete = async (id: number) => {
    if (!confirm("Delete this credential?")) return;
    await fetch(`${API_URL}/api/v1/crypto-connector/${id}`, {
      method: "DELETE",
      headers: deviceHeaders,
    });
    setCreds(creds.filter((c) => c.id !== id));
  };

  /* ------------------------- Real Wallet Connect -------------------------
   * Replaces the old text-input placeholder. Connects to the user's actual
   * wallet (Phantom/Solflare on Solana, MetaMask on EVM), reads the real
   * public address, requests a signed message (nonce) for proof-of-ownership,
   * and POSTs {address, chain, signature, nonce} to the backend.
   */
  const connectWallet = async (
    chain: "solana" | "ethereum"
  ): Promise<{ address: string; signature: string; nonce: string } | null> => {
    const nonce = `jasper-trades-${Date.now()}-${Math.random().toString(16).slice(2)}`;
    try {
      if (chain === "solana") {
        // Phantom/Solflare via the solana wallet-adapter providers.
        const preferred = ["Phantom", "Solflare"];
        const wallet = solanaWallet.wallets.find((w) =>
          preferred.includes(w.adapter.name)
        );
        if (!wallet) {
          alert("Connect wallet: install Phantom or Solflare, then reload.");
          return null;
        }
        if (wallet.readyState !== "Installed") {
          alert(`Please install ${wallet.adapter.name} and reload, then try again.`);
          return null;
        }
        if (solanaWallet.connected && solanaWallet.wallet?.adapter.name === wallet.adapter.name) {
          // already connected to the preferred wallet
        } else {
          solanaWallet.select(wallet.adapter.name);
          await solanaWallet.connect();
        }
        const address = wallet.adapter.publicKey?.toBase58();
        if (!address) throw new Error("No connected account");
        let signature = "";
        const signMessageFn = (
          wallet.adapter as unknown as {
            signMessage?: (m: Uint8Array) => Promise<Uint8Array | { signature: Uint8Array }>;
          }
        ).signMessage;
        if (signMessageFn) {
          const sig = await signMessageFn(new TextEncoder().encode(nonce));
          const boxed = sig as unknown as { signature?: Uint8Array };
          const raw = boxed.signature ?? (sig as unknown as Uint8Array);
          signature = bytesToHex(new Uint8Array(raw));
        }
        if (!signature) {
          alert("Connect wallet: this wallet cannot sign messages.");
          return null;
        }
        return { address, signature, nonce };
      } else {
        // EVM (MetaMask, Coinbase Wallet, etc.) via wagmi's injected connector.
        const evmConnector = connectors.find((c) => c.id === "injected");
        if (!evmConnector) {
          alert("Connect wallet: install a wallet extension like MetaMask, then reload.");
          return null;
        }
        const connected = await connectAsync({ connector: evmConnector });
        const address = connected.accounts?.[0] || "";
        if (!address) throw new Error("No account available");
        // viem signs with personal_sign over the UTF-8 nonce, matching the
        // backend's eth_account.encode_defunct(message) verification.
        const signature = await signMessageAsync({ message: nonce });
        return { address, signature, nonce };
      }
    } catch (e) {
      console.error("Wallet connect failed:", e);
      alert("Wallet connection was cancelled or failed.");
      return null;
    }
  };

  // Called by the modal "Connect" button with the chosen wallet type.
  const handleRealWalletConnect = async () => {
    const chain = walletType === "solana" ? "solana" : "ethereum";
    const connected = await connectWallet(chain);
    if (!connected) return;

    const payload = {
      exchange: chain,
      wallet_address: connected.address,
      chain,
      signature: connected.signature,
      nonce: connected.nonce,
    };
    const res = await fetch(`${API_URL}/api/v1/crypto-connector`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...deviceHeaders },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      alert("Failed to save connection. Check the backend signature verification.");
      return;
    }
    const refreshed = await fetch(`${API_URL}/api/v1/crypto-connector`, {
      headers: deviceHeaders,
    }).then((r) => r.json());
    setCreds(refreshed);
    setShowWalletModal(false);
  };

  return (
    <section className="p-6 bg-gray-900/50 rounded-lg mt-8">
      <h2 className="text-xl font-semibold text-gray-200 mb-4">
        Crypto Connector Configuration
      </h2>

      {/* Existing rows */}
      <DataTable
        columns={[
          { header: "Exchange / Chain", accessor: "exchange", sortable: true },
          { header: "Wallet / Address", accessor: "wallet_address", sortable: false },
          { header: "API Key", accessor: "api_key", sortable: false },
          { header: "API Secret", accessor: "api_secret", sortable: false },
        ]}
        data={creds}
        renderActions={(row) => (
          <button
            onClick={() => handleDelete(row.id)}
            aria-label={`Delete ${row.exchange} credential`}
            className="text-red-400 hover:text-red-200"
          >
            <Trash2 size={16} />
          </button>
        )}
      />

      {/* Add manual connector button */}
      <div className="mt-4 flex gap-4">
        <button
          onClick={() => {
            resetForm();
            setShowForm(true);
          }}
          className="flex items-center gap-2 text-green-400 hover:text-green-200"
        >
          <Plus size={16} /> Add Connector
        </button>
        <button
          onClick={() => setShowWalletModal(true)}
          className="flex items-center gap-2 text-blue-400 hover:text-blue-200"
        >
          <Wallet size={16} /> Connect Wallet
        </button>
      </div>

      {/* Manual Add/Edit Form */}
      {showForm && (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50">
          <div className="bg-gray-800 p-6 rounded-lg w-96">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-medium text-gray-200">
                {editing.id ? "Edit" : "Add"} Connector
              </h3>
              <button onClick={resetForm} className="text-gray-500 hover:text-gray-300">
                <X size={20} />
              </button>
            </div>

            <label htmlFor="cc-exchange" className="block text-sm text-gray-400 mb-1">Exchange / Chain</label>
            <select
              id="cc-exchange"
              value={editing.exchange || ""}
              onChange={(e) => setEditing({ ...editing, exchange: e.target.value })}
              className="w-full mb-3 p-2 bg-gray-700 text-gray-100 rounded"
            >
              <option value="">Select…</option>
              {exchanges.map((ex) => (
                <option key={ex} value={ex}>
                  {ex}
                </option>
              ))}
            </select>

            <label htmlFor="cc-api-key" className="block text-sm text-gray-400 mb-1">API Key (optional)</label>
            <input
              id="cc-api-key"
              type="text"
              value={editing.api_key || ""}
              onChange={(e) => setEditing({ ...editing, api_key: e.target.value })}
              className="w-full mb-3 p-2 bg-gray-700 text-gray-100 rounded"
            />

            <label htmlFor="cc-api-secret" className="block text-sm text-gray-400 mb-1">API Secret (optional)</label>
            <input
              id="cc-api-secret"
              type="password"
              value={editing.api_secret || ""}
              onChange={(e) => setEditing({ ...editing, api_secret: e.target.value })}
              className="w-full mb-3 p-2 bg-gray-700 text-gray-100 rounded"
            />

            <label htmlFor="cc-wallet-address" className="block text-sm text-gray-400 mb-1">Wallet address (optional)</label>
            <input
              id="cc-wallet-address"
              type="text"
              value={editing.wallet_address || ""}
              onChange={(e) => setEditing({ ...editing, wallet_address: e.target.value })}
              className="w-full mb-3 p-2 bg-gray-700 text-gray-100 rounded"
            />

            <label htmlFor="cc-chain" className="block text-sm text-gray-400 mb-1">Chain (optional)</label>
            <select
              id="cc-chain"
              value={editing.chain || ""}
              onChange={(e) => setEditing({ ...editing, chain: e.target.value })}
              className="w-full mb-4 p-2 bg-gray-700 text-gray-100 rounded"
            >
              <option value="">none</option>
              <option value="ethereum">Ethereum</option>
              <option value="solana">Solana</option>
              <option value="bsc">BSC</option>
            </select>

            <button
              onClick={handleSave}
              className="w-full py-2 bg-green-600 hover:bg-green-500 text-white rounded"
            >
              Save
            </button>
          </div>
        </div>
      )}

      {/* Wallet‑Connect Modal */}
      {showWalletModal && (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50">
          <div className="bg-gray-800 p-6 rounded-lg w-96">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-medium text-gray-200">Connect Wallet</h3>
              <button onClick={() => setShowWalletModal(false)} className="text-gray-500 hover:text-gray-300">
                <X size={20} />
              </button>
            </div>
            <label htmlFor="cc-wallet-type" className="block text-sm text-gray-400 mb-1">Wallet type</label>
            <select
              id="cc-wallet-type"
              value={walletType}
              onChange={(e) => setWalletType(e.target.value)}
              className="w-full mb-3 p-2 bg-gray-700 text-gray-100 rounded"
            >
              <option value="solana">Phantom / Solflare (Solana)</option>
              <option value="ethereum">MetaMask (Ethereum / BSC)</option>
            </select>
            <p className="text-xs text-gray-400 mb-3">
              You will be asked to approve the connection and sign a message in
              your wallet extension (this proves you own the address).
            </p>
            <button
              onClick={handleRealWalletConnect}
              className="w-full py-2 bg-blue-600 hover:bg-blue-500 text-white rounded flex items-center justify-center gap-2"
            >
              <Wallet size={16} /> Connect {walletType === "solana" ? "Wallet (Phantom/Solflare)" : "Wallet (MetaMask)"}
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
