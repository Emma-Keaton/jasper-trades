'use client';

import React, { type ReactNode, useEffect, useState } from 'react';
import { QueryClientProvider } from '@tanstack/react-query';
import { WagmiProvider, createConfig, http } from 'wagmi';
import { mainnet, polygon, optimism, arbitrum, base, avalanche } from 'wagmi/chains';
import { injected, walletConnect } from 'wagmi/connectors';
import { QueryClient } from '@tanstack/react-query';
import { ConnectionProvider, WalletProvider } from '@solana/wallet-adapter-react';
import { WalletModalProvider } from '@solana/wallet-adapter-react-ui';
import { PhantomWalletAdapter } from '@solana/wallet-adapter-phantom';
import { SolflareWalletAdapter } from '@solana/wallet-adapter-solflare';
import { WalletAdapterNetwork } from '@solana/wallet-adapter-base';
import { clusterApiUrl } from '@solana/web3.js';
import { API_URL } from '@/lib/constants';

const chains = [mainnet, polygon, optimism, arbitrum, base, avalanche] as const;

const transports = {
  [mainnet.id]: http(),
  [polygon.id]: http(),
  [optimism.id]: http(),
  [arbitrum.id]: http(),
  [base.id]: http(),
  [avalanche.id]: http(),
};

function makeConfig(projectId?: string) {
  return createConfig({
    chains,
    connectors: [
      injected(),
      ...(projectId ? [walletConnect({ projectId })] : []),
    ],
    ssr: false,
    transports,
  });
}

// Solana config (mainnet only)
const network = WalletAdapterNetwork.Mainnet;
const endpoint = clusterApiUrl(network);
const wallets = [new PhantomWalletAdapter(), new SolflareWalletAdapter()];

export function Providers({ children }: { children: ReactNode }) {
  const [config, setConfig] = useState(() => makeConfig());
  const [queryClient] = useState(() => new QueryClient());

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${API_URL}/api/v1/settings/public`);
        if (!res.ok) return;
        const data = await res.json();
        if (!cancelled && data?.walletconnect_project_id) {
          setConfig(makeConfig(data.walletconnect_project_id));
        }
      } catch {
        // backend unreachable: keep injected-only config
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <WagmiProvider config={config}>
      <QueryClientProvider client={queryClient}>
        <ConnectionProvider endpoint={endpoint}>
          <WalletProvider wallets={wallets} autoConnect>
            <WalletModalProvider>
              {children}
            </WalletModalProvider>
          </WalletProvider>
        </ConnectionProvider>
      </QueryClientProvider>
    </WagmiProvider>
  );
}
