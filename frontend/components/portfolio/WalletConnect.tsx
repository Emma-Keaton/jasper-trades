'use client';

import React, { useState, useCallback, useEffect } from 'react';
import Image from 'next/image';
import { useAccount, useConnect, useDisconnect } from 'wagmi';
import { useWallet } from '@solana/wallet-adapter-react';
import { Modal, Button } from '@/components/ui';
import { Wallet, ExternalLink, Copy, Loader2, CheckCircle2, XCircle, Smartphone } from 'lucide-react';
import { SetupGuideButton } from '@/components/settings/SetupGuide';
import { walletSetupSteps } from '@/components/settings/setupGuides';
import QRCode from 'qrcode';

type ChainType = 'evm' | 'solana';
type ConnectionStatus = 'idle' | 'connecting' | 'connected' | 'error';

interface WalletOption {
  id: string;
  name: string;
  icon?: string;
  installed?: boolean;
  url?: string;
}

// Install / download pages keyed by EVM connector id.
const EVM_INSTALL_URLS: Record<string, string> = {
  injected: 'https://metamask.io/download/',
  metaMask: 'https://metamask.io/download/',
  coinbaseWallet: 'https://www.coinbase.com/wallet/downloads',
};

// Mobile universal deep-links: clicking these opens the wallet app on phone.
const SOLANA_APP_DEEP_LINKS: Record<string, string> = {
  Phantom: 'https://phantom.app/ul/browse',
  Solflare: 'https://solflare.com/ul',
  Backpack: 'https://backpack.app/ul',
};

export default function WalletConnect() {
  const { address: evmAddress, isConnected: evmConnected, chain: evmChain } = useAccount();
  const { connect: connectEvm, connectors } = useConnect();
  const { disconnect: disconnectEvm } = useDisconnect();

  const { publicKey, disconnect: disconnectSolana, wallets: solanaWallets, select, connect, connected } = useWallet();

  const [open, setOpen] = useState(false);
  const [chainType, setChainType] = useState<ChainType>('evm');
  const [copied, setCopied] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const [, setConnectionStatus] = useState<ConnectionStatus>('idle');

  // WalletConnect QR state
  const [wcUri, setWcUri] = useState<string | null>(null);
  const [wcQrDataUrl, setWcQrDataUrl] = useState<string | null>(null);

  const hasEthereumProvider = typeof window !== 'undefined' && !!(window as any).ethereum;

  // Best-effort detection of which injected wallet is installed.
  const detectedInjected = React.useMemo(() => {
    if (typeof window === 'undefined') return null;
    const provider = (window as any).ethereum;
    if (!provider) return null;
    if (provider.isMetaMask) return 'metaMask';
    if (provider.isCoinbaseWallet) return 'coinbaseWallet';
    if (provider.isRainbow) return 'rainbow';
    return 'injected';
  }, []);

  // Build EVM connector options with proper names/icons
  const evmWalletOptions: WalletOption[] = React.useMemo(() => {
    return connectors.map((connector) => {
      const id = connector.id;
      let name = id.charAt(0).toUpperCase() + id.slice(1);
      let icon = '';

      // Map common connector IDs to friendly names and icons
      if (id === 'injected') {
        name = 'Browser Wallet';
        if (detectedInjected === 'metaMask') { name = 'MetaMask'; icon = 'https://upload.wikimedia.org/wikipedia/commons/3/36/MetaMask_Fox.svg'; }
        else if (detectedInjected === 'coinbaseWallet') { name = 'Coinbase Wallet'; icon = 'https://static.coinbase.com/assets/cb-logo.svg'; }
        else if (detectedInjected === 'rainbow') { name = 'Rainbow'; icon = 'https://rainbow.me/logo.png'; }
      } else if (id === 'walletConnect') {
        name = 'WalletConnect';
        icon = 'https://walletconnect.com/icons/wallets/1d5c87d69e5d5f5ad5c9d9e5d5f5ad5c9d9e5d5f5.png';
      }

      // Whether this EVM wallet is currently available in the browser.
      const installed =
        id === 'walletConnect'
          ? true
          : id === 'injected'
          ? !!hasEthereumProvider
          : false;

      return { id, name, icon, installed };
    });
  }, [connectors, detectedInjected, hasEthereumProvider]);

  // Build Solana wallet options
  const solanaWalletOptions: WalletOption[] = React.useMemo(() => {
    return solanaWallets.map((w) => ({
      id: w.adapter.name,
      name: w.adapter.name,
      icon: w.adapter.icon || undefined,
      installed: w.readyState === 'Installed',
      url: w.adapter.url,
    }));
  }, [solanaWallets]);

  const connectedAddress = chainType === 'evm' ? evmAddress : connected ? publicKey?.toBase58() : undefined;
  const is_connected = chainType === 'evm' ? evmConnected : connected;
  const chainName = chainType === 'evm'
    ? (evmChain?.name || 'EVM')
    : 'Solana';

  // Subscribe to the WalletConnect connector so we can surface the pairing URI
  // as a QR code + deep link (required to connect from a phone).
  const wcConnector = connectors.find((c) => c.id === 'walletConnect');

  useEffect(() => {
    if (!wcConnector?.emitter) return;
    const handler = async ({ type, data }: { type: string; data?: unknown }) => {
      if (type === 'display_uri' && typeof data === 'string') {
        setWcUri(data);
        try {
          const url = await QRCode.toDataURL(data, { width: 224, margin: 2, color: { dark: '#0f172a', light: '#ffffff' } });
          setWcQrDataUrl(url);
        } catch (e) {
          console.error('Failed to render WalletConnect QR:', e);
          setWcQrDataUrl(null);
        }
      }
    };
    wcConnector.emitter.on('message', handler);
    return () => {
      wcConnector.emitter?.off('message', handler);
    };
  }, [wcConnector]);

  const clearWc = useCallback(() => {
    setWcUri(null);
    setWcQrDataUrl(null);
  }, []);

  const handleDisconnect = useCallback(async () => {
    try {
      if (chainType === 'evm') {
        await disconnectEvm();
      } else {
        await disconnectSolana();
      }
      setConnectionStatus('idle');
      setConnectionError(null);
      clearWc();
      setOpen(false);
    } catch (err) {
      setConnectionError(err instanceof Error ? err.message : 'Failed to disconnect');
    }
  }, [chainType, disconnectEvm, disconnectSolana, clearWc]);

  const handleCopy = useCallback(async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setConnectionError('Failed to copy');
    }
  }, []);

  const openExplorer = useCallback(() => {
    if (!connectedAddress) return;
    const url = chainType === 'evm'
      ? `${(evmChain?.blockExplorers?.default ?? { url: 'https://etherscan.io' }).url}/address/${connectedAddress}`
      : `https://explorer.solana.com/address/${connectedAddress}?cluster=mainnet`;
    window.open(url, '_blank', 'noopener,noreferrer');
  }, [chainType, evmChain, connectedAddress]);

  const handleConnect = useCallback(async (walletId: string) => {
    setConnecting(true);
    setConnectionError(null);
    setConnectionStatus('connecting');

    try {
      if (chainType === 'evm') {
        const connector = connectors.find(c => c.id === walletId);
        if (!connector) throw new Error('Connector not found');
        clearWc();
        await connectEvm({ connector });
        clearWc();
        setConnectionStatus('connected');
        setOpen(false);
      } else {
        // For Solana, select then connect (only ever called for installed wallets)
        const wallet = solanaWallets.find(w => w.adapter.name === walletId);
        if (!wallet) throw new Error('Wallet not found');
        select(wallet.adapter.name);
        await connect();
        setConnectionStatus('connected');
        setOpen(false);
      }
    } catch (err) {
      console.error('Wallet connection failed:', err);
      clearWc();
      setConnectionError(err instanceof Error ? err.message : 'Connection failed');
      setConnectionStatus('error');
    } finally {
      setConnecting(false);
    }
  }, [chainType, connectors, connectEvm, solanaWallets, select, connect, clearWc]);

  // Opening a fast link calls the specific wallet app (or its install page).
  const openWalletApp = useCallback((wallet: WalletOption) => {
    if (chainType === 'evm') {
      const url = EVM_INSTALL_URLS[wallet.id.toLowerCase()] || (wallet.name === 'MetaMask' ? EVM_INSTALL_URLS.metaMask : null);
      if (url) {
        window.open(url, '_blank', 'noopener,noreferrer');
      } else if (wallet.id === 'walletConnect') {
        setConnectionStatus('idle');
        handleConnect('walletConnect');
      }
      return;
    }
    const deepLink = SOLANA_APP_DEEP_LINKS[wallet.name];
    window.open(deepLink || wallet.url || 'https://phantom.app/ul/browse', '_blank', 'noopener,noreferrer');
  }, [chainType, handleConnect]);

  // Reset status when switching chains
  useEffect(() => {
    setConnectionStatus('idle');
    setConnectionError(null);
    clearWc();
  }, [chainType, clearWc]);

  return (
    <div>
      <Button
        variant="secondary"
        onClick={() => { setConnectionStatus('idle'); clearWc(); setOpen(true); }}
        className="flex items-center gap-2"
        disabled={connecting}
      >
        {connecting ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : is_connected ? (
          <CheckCircle2 className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />
        ) : (
          <Wallet className="h-4 w-4" />
        )}
        {is_connected
          ? `${chainName} · ${connectedAddress?.slice(0, 6)}...${connectedAddress?.slice(-4)}`
          : 'Connect Wallet'}
      </Button>

      <Modal
        open={open}
        onClose={() => {
          if (connecting) return;
          clearWc();
          setOpen(false);
        }}
        title="Connect a wallet"
        description="Choose a chain and connect your wallet. Mainnet only."
        size="sm"
      >
        <div className="mb-4 flex items-center justify-between gap-2">
          <p className="text-xs text-slate-500 dark:text-slate-400">
            New here? Follow the walkthrough to get set up.
          </p>
          <SetupGuideButton
            title="Connect a wallet"
            intro="A wallet is your key to crypto. Follow these steps to install one, create it, and link it to Jasper."
            steps={walletSetupSteps}
          />
        </div>
        <div className="flex gap-2 mb-5">
          <button
            onClick={() => setChainType('evm')}
            className={`flex-1 rounded-control border px-3 py-2.5 text-sm font-semibold transition ${
              chainType === 'evm'
                ? 'border-brand-500 bg-brand-50 text-brand-700 dark:bg-brand-500/10 dark:text-brand-300'
                : 'border-slate-200 text-slate-700 hover:border-slate-300 dark:border-slate-700 dark:text-slate-200'
            }`}
          >
            EVM
          </button>
          <button
            onClick={() => setChainType('solana')}
            className={`flex-1 rounded-control border px-3 py-2.5 text-sm font-semibold transition ${
              chainType === 'solana'
                ? 'border-brand-500 bg-brand-50 text-brand-700 dark:bg-brand-500/10 dark:text-brand-300'
                : 'border-slate-200 text-slate-700 hover:border-slate-300 dark:border-slate-700 dark:text-slate-200'
            }`}
          >
            Solana
          </button>
        </div>

        {connectionError && (
          <div className="mb-4 flex items-start gap-2 rounded-control border border-rose-200 bg-rose-50 p-3 text-xs text-rose-700 dark:border-rose-500/30 dark:bg-rose-500/10 dark:text-rose-300">
            <XCircle className="mt-0.5 h-4 w-4 shrink-0" />
            <span>{connectionError}. Please try again.</span>
          </div>
        )}

        {/* WalletConnect pairing QR */}
        {chainType === 'evm' && wcUri && wcQrDataUrl && (
          <div className="mb-4 space-y-3 rounded-control border border-slate-200 bg-slate-50 p-4 dark:border-slate-700 dark:bg-slate-800/60">
            <p className="text-xs font-semibold text-slate-700 dark:text-slate-200">
              Scan with your mobile wallet
            </p>
            <div className="flex justify-center">
              <Image
                src={wcQrDataUrl}
                alt="WalletConnect QR code"
                width={224}
                height={224}
                unoptimized
                className="h-56 w-56 rounded-lg"
              />
            </div>
            <div className="flex items-center gap-2">
              <code className="flex-1 truncate rounded bg-slate-100 px-2 py-1.5 text-[10px] text-slate-600 dark:bg-slate-800 dark:text-slate-300">
                {wcUri}
              </code>
              <button
                onClick={() => handleCopy(wcUri)}
                className="rounded p-1.5 text-slate-500 transition hover:bg-slate-100 dark:hover:bg-slate-800"
                aria-label="Copy pairing URI"
              >
                {copied ? <CheckCircle2 className="h-4 w-4 text-emerald-500" /> : <Copy className="h-4 w-4" />}
              </button>
              <a
                href={wcUri}
                className="rounded p-1.5 text-brand-600 transition hover:bg-brand-50 dark:hover:bg-brand-500/10"
                aria-label="Open in wallet app"
              >
                <Smartphone className="h-4 w-4" />
              </a>
            </div>
            <p className="text-[11px] text-slate-400 dark:text-slate-500">
              Or tap <strong>Open in wallet app</strong> to jump straight into your mobile wallet.
            </p>
          </div>
        )}

        <div className="space-y-3">
          {is_connected ? (
            <div className="space-y-3 rounded-control border border-emerald-200 bg-emerald-50 p-4 dark:border-emerald-500/30 dark:bg-emerald-500/10">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold uppercase text-emerald-700 dark:text-emerald-300">Connected</span>
                <span className="rounded-full bg-emerald-100 px-2.5 py-0.5 text-xs font-bold text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-300">
                  {chainName}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <code className="flex-1 break-all rounded bg-white/70 px-2 py-1.5 text-xs font-mono dark:bg-slate-900/50">
                  {connectedAddress}
                </code>
                <button
                  onClick={() => handleCopy(connectedAddress ?? '')}
                  className="rounded p-1.5 text-emerald-600 transition hover:bg-emerald-100 dark:hover:bg-emerald-500/20"
                  aria-label="Copy address"
                >
                  {copied ? <CheckCircle2 className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                </button>
                <button
                  onClick={openExplorer}
                  className="rounded p-1.5 text-emerald-600 transition hover:bg-emerald-100 dark:hover:bg-emerald-500/20"
                  aria-label="Open in explorer"
                >
                  <ExternalLink className="h-4 w-4" />
                </button>
              </div>
              {copied && <p className="text-xs font-medium text-emerald-600 dark:text-emerald-400">Copied to clipboard</p>}
            </div>
          ) : (
            <>
              {chainType === 'evm' ? (
                evmWalletOptions.length > 0 ? (
                  <div className="space-y-2">
                    {evmWalletOptions.map((wallet) => {
                      const connectable = wallet.id === 'walletConnect' || (wallet.installed ?? true);
                      return (
                        <div
                          key={wallet.id}
                          className="flex w-full items-center gap-3 rounded-control border border-slate-200 px-4 py-3 dark:border-slate-700"
                        >
                          <button
                            onClick={() => (connectable ? handleConnect(wallet.id) : openWalletApp(wallet))}
                            disabled={connecting}
                            className="flex min-w-0 flex-1 items-center gap-3 text-left"
                          >
                            {wallet.icon ? (
                              <Image src={wallet.icon} alt={wallet.name} width={20} height={20} unoptimized className="h-5 w-5 rounded" />
                            ) : (
                              <Wallet className="h-5 w-5 text-slate-400" />
                            )}
                            <span className="flex-1 truncate text-sm font-semibold text-slate-900 dark:text-slate-100">
                              {wallet.name}
                            </span>
                            {connecting && (
                              <Loader2 className="h-4 w-4 animate-spin text-brand-600 dark:text-brand-400" />
                            )}
                          </button>
                          {wallet.id === 'injected' && !hasEthereumProvider && (
                            <span className="text-[11px] font-semibold text-amber-600 dark:text-amber-400">
                              Not installed
                            </span>
                          )}
                          <button
                            onClick={() => openWalletApp(wallet)}
                            className="rounded p-1.5 text-slate-400 transition hover:bg-slate-100 hover:text-brand-600 dark:hover:bg-slate-800"
                            aria-label={`Open ${wallet.name} app`}
                            title={wallet.id === 'walletConnect' ? 'Show pairing QR' : 'Open wallet app / install'}
                          >
                            <ExternalLink className="h-4 w-4" />
                          </button>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <div className="rounded-control border border-dashed border-slate-300 p-4 text-center text-sm text-slate-500 dark:border-slate-700 dark:text-slate-400">
                    No EVM wallets detected. Install a wallet extension to continue.
                    <a
                      href="https://metamask.io/download/"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="mt-3 block font-semibold text-brand-600 hover:underline dark:text-brand-400"
                    >
                      Install MetaMask →
                    </a>
                  </div>
                )
              ) : (
                solanaWalletOptions.length > 0 ? (
                  <div className="space-y-2">
                    {solanaWalletOptions.map((wallet) => (
                      <div
                        key={wallet.id}
                        className="flex w-full items-center gap-3 rounded-control border border-slate-200 px-4 py-3 dark:border-slate-700"
                      >
                        <button
                          onClick={() => wallet.installed ? handleConnect(wallet.id) : openWalletApp(wallet)}
                          disabled={connecting}
                          className="flex min-w-0 flex-1 items-center gap-3 text-left"
                        >
                          {wallet.icon ? (
                            <Image src={wallet.icon} alt={wallet.name} width={20} height={20} unoptimized className="h-5 w-5 rounded" />
                          ) : (
                            <Wallet className="h-5 w-5 text-slate-400" />
                          )}
                          <span className="flex-1 truncate text-sm font-semibold text-slate-900 dark:text-slate-100">
                            {wallet.name}
                          </span>
                          <span className={`text-[11px] font-semibold ${wallet.installed ? 'text-emerald-600 dark:text-emerald-400' : 'text-amber-600 dark:text-amber-400'}`}>
                            {wallet.installed ? 'Installed' : 'Install'}
                          </span>
                          {connecting && (
                            <Loader2 className="h-4 w-4 animate-spin text-brand-600 dark:text-brand-400" />
                          )}
                        </button>
                        <button
                          onClick={() => openWalletApp(wallet)}
                          className="rounded p-1.5 text-slate-400 transition hover:bg-slate-100 hover:text-brand-600 dark:hover:bg-slate-800"
                          aria-label={`Open ${wallet.name} app`}
                          title="Open wallet app"
                        >
                          <ExternalLink className="h-4 w-4" />
                        </button>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="rounded-control border border-dashed border-slate-300 p-4 text-center text-sm text-slate-500 dark:border-slate-700 dark:text-slate-400">
                    No Solana wallets detected. Install Phantom or Solflare and reload.
                    <a
                      href="https://phantom.app/download"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="mt-3 block font-semibold text-brand-600 hover:underline dark:text-brand-400"
                    >
                      Install Phantom →
                    </a>
                  </div>
                )
              )}
            </>
          )}
        </div>

        {is_connected ? (
          <div className="mt-5 flex justify-end">
            <Button variant="danger" onClick={handleDisconnect} disabled={connecting}>
              Disconnect
            </Button>
          </div>
        ) : (
          <div className="mt-5 flex justify-end">
            <Button variant="ghost" onClick={() => { clearWc(); !connecting && setOpen(false); }} disabled={connecting}>
              Close
            </Button>
          </div>
        )}
      </Modal>
    </div>
  );
}