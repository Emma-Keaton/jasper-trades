import type { Metadata, Viewport } from 'next';
import { Plus_Jakarta_Sans, JetBrains_Mono } from 'next/font/google';
import './globals.css';
import { CurrencyProvider } from '@/lib/currencyContext';
import { ThemeProvider } from '@/lib/theme';
import { Providers } from '@/app/providers';

const sans = Plus_Jakarta_Sans({
  subsets: ['latin'],
  variable: '--font-sans',
  display: 'swap',
});

const display = Plus_Jakarta_Sans({
  subsets: ['latin'],
  variable: '--font-display',
  display: 'swap',
});

const mono = JetBrains_Mono({
  subsets: ['latin'],
  variable: '--font-mono',
  display: 'swap',
});

export const viewport: Viewport = {
  themeColor: '#0d9488',
  minimumScale: 1,
  initialScale: 1,
  width: 'device-width',
};

export const metadata: Metadata = {
  title: 'Jasper Trades - Your AI Trader',
  description: 'An AI trader that watches markets and trades with practice money. Simple, guided, and beginner-friendly.',
  manifest: '/manifest.json',
  icons: {
    icon: '/favicon.ico',
    shortcut: '/favicon-32.png',
    apple: '/apple-touch-icon.png',
  },
  appleWebApp: {
    capable: true,
    statusBarStyle: 'default',
    title: 'Jasper Trades',
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  // ThemeInit applies the saved / OS theme before first paint to avoid a flash.
  return (
    <html lang="en" className={`${sans.variable} ${display.variable} ${mono.variable}`} suppressHydrationWarning>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `
(function(){try{var t=localStorage.getItem('jasper_theme');if(t!=='light'&&t!=='dark'){t=window.matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light';}if(t==='dark'){document.documentElement.classList.add('dark');}}catch(e){}})();
`,
          }}
        />
      </head>
      <body className="min-h-dvh bg-slate-50 text-slate-900 dark:bg-slate-950 dark:text-slate-100" suppressHydrationWarning>
        <ThemeProvider>
          <CurrencyProvider>
            <Providers>{children}</Providers>
          </CurrencyProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}

