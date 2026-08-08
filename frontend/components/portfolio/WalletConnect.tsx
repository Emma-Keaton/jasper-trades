'use client';

import React, { useState, useCallback } from 'react';
import { useAccount, useConnect, useDisconnect } from 'wagmi';
import { useWallet } from '@solana/wallet-adapter-react';
import { Modal } from '@/components/ui/modal';
import { Button } from '@/components/ui/button';
import { Wallet, ExternalLink, Copy } from 'lucide-react';

type ChainType = 'evm' | 'solana';

export default function WalletConnect() {
  const { address: evmAddress, isConnected: evmConnected, chain: evmChain } = useAccount();
  const { connect: connectEvm, connectors } = useConnect();
  const { disconnect: disconnectEvm } = useDisconnect();
  const { publicKey, disconnect: disconnectSolana, wallets: solanaWallets, select } = useWallet();

  const [open, setOpen] = useState(false);
  const [chainType, setChainType] = useState<ChainType>('evm');
  const [copied, setCopied] = useState(false);

  const evmConnectors = connectors.filter((c) => c.id === 'injected' || c.id === 'walletConnect');

  const connectedAddress = chainType === 'evm' ? evmAddress : publicKey?.toBase58();
  const connected = chainType === 'evm' ? evmConnected : !!publicKey;
  const chainName = chainType === 'evm' ? evmChain?.name : 'Solana';

  const handleDisconnect = useCallback(() => {
    if (chainType === 'evm') {
      disconnectEvm();
    } else {
      disconnectSolana();
    }
    setOpen(false);
  }, [chainType, disconnectEvm, disconnectSolana]);

  const handleCopy = useCallback(async (text: string) => {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }, []);

  const openExplorer = () => {
    if (!connectedAddress) return;
    const url =
      chainType === 'evm'
        ? `${(evmChain?.blockExplorers?.default ?? { url: 'https://etherscan.io' }).url}/address/${connectedAddress}`
        : `https://explorer.solana.com/address/${connectedAddress}`;
    window.open(url, '_blank', 'noopener,noreferrer');
  };

  return (
    <div>
      <Button variant="secondary" onClick={() => setOpen(true)} className="flex items-center gap-2">
        <Wallet className="h-4 w-4" />
        {connected ? `${chainName} · ${connectedAddress?.slice(0, 6)}...${connectedAddress?.slice(-4)}` : 'Connect Wallet'}
      </Button>

      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title="Connect a wallet"
        description="Choose a chain and connect your wallet. Mainnet only."
        size="sm"
      >
        <div className="flex gap-2 mb-5">
          <button
            onClick={() => setChainType('evm')}
            className={`flex-1 rounded-control border px-3 py-2 text-sm font-semibold transition ${
              chainType === 'evm'
                ? 'border-brand-500 bg-brand-50 text-brand-700 dark:bg-brand-500/10 dark:text-brand-300'
                : 'border-slate-200 text-slate-700 hover:border-slate-300 dark:border-slate-700 dark:text-slate-200'
            }`}
          >
            EVM
          </button>
          <button
            onClick={() => setChainType('solana')}
            className={`flex-1 rounded-control border px-3 py-2 text-sm font-semibold transition ${
              chainType === 'solana'
                ? 'border-brand-500 bg-brand-50 text-brand-700 dark:bg-brand-500/10 dark:text-brand-300'
                : 'border-slate-200 text-slate-700 hover:border-slate-300 dark:border-slate-700 dark:text-slate-200'
            }`}
          >
            Solana
          </button>
        </div>

        <div className="space-y-4">
          {connected ? (
            <div className="space-y-3 rounded-control border border-slate-200 bg-slate-50 p-4 dark:border-slate-700 dark:bg-slate-800/60">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold uppercase text-slate-500 dark:text-slate-400">Connected</span>
                <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-xs font-bold text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300">
                  {chainName}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <code className="flex-1 break-all rounded bg-white px-2 py-1 text-xs dark:bg-slate-900">{connectedAddress}</code>
                <button
                  onClick={() => handleCopy(connectedAddress ?? '')}
                  className="rounded p-1.5 text-slate-500 transition hover:bg-slate-200 dark:hover:bg-slate-700"
                  aria-label="Copy address"
                >
                  <Copy className="h-4 w-4" />
                </button>
                <button
                  onClick={openExplorer}
                  className="rounded p-1.5 text-slate-500 transition hover:bg-slate-200 dark:hover:bg-slate-700"
                  aria-label="Open in explorer"
                >
                  <ExternalLink className="h-4 w-4" />
                </button>
              </div>
              {copied && <p className="text-xs text-emerald-600 dark:text-emerald-300">Copied to clipboard</p>}
            </div>
          ) : (
            <div className="space-y-2">
              {chainType === 'evm' ? (
                <div className="space-y-2">
                  {evmConnectors.map((connector) => (
                    <button
                      key={connector.id}
                      onClick={() => connectEvm({ connector })}
                      className="flex w-full items-center justify-between rounded-control border border-slate-200 px-4 py-3 text-sm font-semibold text-slate-900 transition hover:border-brand-300 dark:border-slate-700 dark:text-slate-100"
                    >
                      <span className="capitalize">{connector.id}</span>
                      <ExternalLink className="h-4 w-4 text-slate-400" />
                    </button>
                  ))}
                </div>
              ) : (
                <div className="space-y-2">
                  {solanaWallets.map((w) => {
                    const installed = w.readyState === 'Installed';
                    return (
                      <button
                        key={w.adapter.name}
                        onClick={() => select(w.adapter.name)}
                        className="flex w-full items-center justify-between rounded-control border border-slate-200 px-4 py-3 text-sm font-semibold text-slate-900 transition hover:border-brand-300 dark:border-slate-700 dark:text-slate-100"
                      >
                        <span className="flex items-center gap-2">
                          {w.adapter.icon && (
                            <img src={w.adapter.icon} alt={w.adapter.name} className="h-5 w-5 rounded object-contain" />
                          )}
                          <span>{w.adapter.name}</span>
                        </span>
                        <span className={`text-xs ${installed ? 'text-emerald-600 dark:text-emerald-400' : 'text-slate-400'}`}>
                          {installed ? 'Installed' : 'Not detected'}
                        </span>
                      </button>
                    );
                  })}
                  {solanaWallets.length === 0 && (
                    <div className="rounded-control border border-dashed border-slate-300 p-4 text-center text-sm text-slate-600 dark:border-slate-700 dark:text-slate-300">
                      No Solana wallets available. Install Phantom or Solflare and reload.
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {connected ? (
            <div className="flex justify-end">
              <Button variant="danger" onClick={handleDisconnect}>Disconnect</Button>
            </div>
          ) : (
            <div className="flex justify-end">
              <Button variant="ghost" onClick={() => setOpen(false)}>Close</Button>
            </div>
          )}
        </div>
      </Modal>
    </div>
  );
}
