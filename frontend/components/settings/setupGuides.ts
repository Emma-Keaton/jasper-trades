import type { GuideStep } from '@/components/settings/SetupGuide';

export const walletSetupSteps: GuideStep[] = [
  {
    title: 'Choose a chain',
    body: 'Pick which network your wallet lives on. EVM covers Ethereum, Polygon, BNB Chain and most on-chain apps. Solana is its own network with wallets like Phantom and Solflare.',
  },
  {
    title: 'Install a wallet',
    body: 'Never used a wallet before? Install MetaMask (EVM) or Phantom (Solana) from the official download page. It takes under a minute and no account or email is required.',
    href: 'https://metamask.io/download/',
    hrefLabel: 'Install MetaMask',
  },
  {
    title: 'Create your wallet',
    body: 'Follow the in-app prompts to create a new wallet. You will get a secret recovery phrase — write it down and store it somewhere safe. Never share it with anyone, including us.',
    hint: 'Write down your recovery phrase on paper before continuing. Anyone with it can spend your funds.',
  },
  {
    title: 'Connect here',
    body: 'Once installed, reload this page, pick your chain, and tap the wallet you just set up. Approve the connection in your wallet and your address will appear here. You are ready to go.',
    hint: 'If you are on a phone, tap the wallet that offers a QR code and scan it with your wallet app instead.',
  },
];

export const brokerKeySetupSteps: GuideStep[] = [
  {
    title: 'Log in to your exchange',
    body: 'Open your exchange website and sign in to your account. You need an account that supports API keys — most major exchanges do.',
  },
  {
    title: 'Find API management',
    body: 'Look for API Management, Developer, or Security in your account settings. There is usually a quick link under the exchange picker in this panel.',
    href: 'https://www.binance.com/en/my/settings/api-management',
    hrefLabel: 'See an example (Binance)',
  },
  {
    title: 'Create an API key',
    body: 'Create a new API key and give it a name like “Jasper”. Enable read/trade permissions if you want Jasper to execute trades. Disable withdrawals — Jasper will never withdraw your funds.',
    hint: 'Never enable withdrawal permissions on any API key you give to a trading bot.',
  },
  {
    title: 'Copy the key and secret',
    body: 'Copy the API key and secret into the fields in this panel. The secret is only shown once — keep it safe. Then tap Link exchange to finish.',
    hint: 'Your secret is encrypted before it is stored and never shown on screen again.',
  },
];

export const tigerSetupSteps: GuideStep[] = [
  {
    title: 'Open Tiger Brokers',
    body: 'Tiger Brokers is a licensed US broker covering US stocks and CN/HK markets via OpenAPI. Create an account if you have not already.',
    href: 'https://www.tigerbrokers.com/',
    hrefLabel: 'Open Tiger Brokers',
  },
  {
    title: 'Enable OpenAPI',
    body: 'In your Tiger app, go to Settings > OpenAPI and enable API trading. You will receive your Tiger ID and API keys.',
    hint: 'OpenAPI must be enabled to generate keys. Some markets require a funded account first.',
  },
  {
    title: 'Generate API keys',
    body: 'Generate an API key and private key from the OpenAPI page. Copy them into the Tiger card in this panel.',
    hint: 'The private key is used to sign live orders — it is encrypted before storage and never displayed again.',
  },
  {
    title: 'Test the connection',
    body: 'Tap Test connection to verify the keys work and your account is reachable. When it returns your account balance, you are fully wired for live US stock trading.',
  },
];