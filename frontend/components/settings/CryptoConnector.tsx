import { useState, useEffect } from "react";
import { X, Plus, Save, Trash2, Wallet } from "lucide-react";
import { API_URL } from "@/lib/constants";

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

export default function CryptoConnector() {
  const [creds, setCreds] = useState<Credential[]>([]);
  const [editing, setEditing] = useState<Partial<Credential>>({});
  const [showForm, setShowForm] = useState(false);
  const [exchanges, setExchanges] = useState<string[]>([]);
  const [showWalletModal, setShowWalletModal] = useState(false);
  const [walletType, setWalletType] = useState<string>("solana");
  const [walletAddress, setWalletAddress] = useState<string>("");

  // Load stored credentials
  useEffect(() => {
    fetch(`${API_URL}/api/v1/crypto-connector`, { credentials: "include" })
      .then((r) => r.json())
      .then(setCreds)
      .catch(() => console.error("failed to load crypto creds"));
    // Load exchange list dynamically from backend
    fetch(`${API_URL}/api/v1/exchanges/`, { credentials: "include" })
      .then((r) => r.json())
      .then(setExchanges)
      .catch(() => console.error("failed to load exchanges"));
  }, []);

  const resetForm = () => {
    setEditing({});
    setShowForm(false);
  };

  const handleSave = async () => {
    await fetch(`${API_URL}/api/v1/crypto-connector`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(editing),
      credentials: "include",
    });
    const refreshed = await fetch(`${API_URL}/api/v1/crypto-connector`, {
      credentials: "include",
    }).then((r) => r.json());
    setCreds(refreshed);
    resetForm();
  };

  const handleDelete = async (id: number) => {
    if (!confirm("Delete this credential?")) return;
    await fetch(`${API_URL}/api/v1/crypto-connector/${id}`, {
      method: "DELETE",
      credentials: "include",
    });
    setCreds(creds.filter((c) => c.id !== id));
  };

  // Wallet‑Connect modal submission
  const handleWalletConnect = async () => {
    const exchange = walletType === "solana" ? "solana" : "ethereum";
    const chain = walletType === "solana" ? "solana" : "ethereum";
    const payload = {
      exchange,
      wallet_address: walletAddress,
      chain,
    };
    await fetch(`${API_URL}/api/v1/crypto-connector`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      credentials: "include",
    });
    const refreshed = await fetch(`${API_URL}/api/v1/crypto-connector`, {
      credentials: "include",
    }).then((r) => r.json());
    setCreds(refreshed);
    setShowWalletModal(false);
    setWalletAddress("");
  };

  return (
    <section className="p-6 bg-gray-900/50 rounded-lg mt-8">
      <h2 className="text-xl font-semibold text-gray-200 mb-4">
        Crypto Connector Configuration
      </h2>

      {/* Existing rows */}
      <table className="w-full text-sm text-left text-gray-300">
        <thead className="border-b border-gray-700">
          <tr>
            <th className="pb-2">Exchange / Chain</th>
            <th className="pb-2">Wallet / Address</th>
            <th className="pb-2">Actions</th>
          </tr>
        </thead>
        <tbody>
          {creds.map((c) => (
            <tr
              key={c.id}
              className="border-b border-gray-800 hover:bg-gray-800/30"
            >
              <td className="py-2 capitalize">{c.exchange}</td>
              <td className="py-2">{c.wallet_address || "-"}</td>
              <td className="py-2 flex gap-2">
                <button
                  onClick={() => {
                    setEditing(c);
                    setShowForm(true);
                  }}
                  className="p-1 text-gray-400 hover:text-gray-100"
                >
                  <Save size={16} />
                </button>
                <button
                  onClick={() => handleDelete(c.id)}
                  className="p-1 text-red-500 hover:text-red-300"
                >
                  <Trash2 size={16} />
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

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

            <label className="block text-sm text-gray-400 mb-1">Exchange / Chain</label>
            <select
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

            <label className="block text-sm text-gray-400 mb-1">API Key (optional)</label>
            <input
              type="text"
              value={editing.api_key || ""}
              onChange={(e) => setEditing({ ...editing, api_key: e.target.value })}
              className="w-full mb-3 p-2 bg-gray-700 text-gray-100 rounded"
            />

            <label className="block text-sm text-gray-400 mb-1">API Secret (optional)</label>
            <input
              type="password"
              value={editing.api_secret || ""}
              onChange={(e) => setEditing({ ...editing, api_secret: e.target.value })}
              className="w-full mb-3 p-2 bg-gray-700 text-gray-100 rounded"
            />

            <label className="block text-sm text-gray-400 mb-1">Wallet address (optional)</label>
            <input
              type="text"
              value={editing.wallet_address || ""}
              onChange={(e) => setEditing({ ...editing, wallet_address: e.target.value })}
              className="w-full mb-3 p-2 bg-gray-700 text-gray-100 rounded"
            />

            <label className="block text-sm text-gray-400 mb-1">Chain (optional)</label>
            <select
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
            <label className="block text-sm text-gray-400 mb-1">Wallet type</label>
            <select
              value={walletType}
              onChange={(e) => setWalletType(e.target.value)}
              className="w-full mb-3 p-2 bg-gray-700 text-gray-100 rounded"
            >
              <option value="solana">Phantom / Solflare (Solana)</option>
              <option value="ethereum">MetaMask (Ethereum)</option>
            </select>
            <label className="block text-sm text-gray-400 mb-1">Wallet address</label>
            <input
              type="text"
              placeholder="0x… or Solana address"
              value={walletAddress}
              onChange={(e) => setWalletAddress(e.target.value)}
              className="w-full mb-4 p-2 bg-gray-700 text-gray-100 rounded"
            />
            <button
              onClick={handleWalletConnect}
              className="w-full py-2 bg-blue-600 hover:bg-blue-500 text-white rounded"
            >
              Connect
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
