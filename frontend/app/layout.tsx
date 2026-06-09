import type {Metadata, Viewport} from 'next';
import { Inter, JetBrains_Mono } from 'next/font/google';
import './globals.css';

const inter = Inter({
  subsets: ['latin'],
  variable: '--font-sans',
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ['latin'],
  variable: '--font-mono',
});

export const viewport: Viewport = {
  themeColor: '#3B82F6',
  minimumScale: 1,
  initialScale: 1,
  width: 'device-width',
};

export const metadata: Metadata = {
  title: 'Jasper Trades - AI-Powered Trading Dashboard',
  description: 'High-fidelity responsive frontend dashboard for Jasper Trades AI-powered trading.',
  manifest: '/manifest.json',
  icons: {
    icon: '/favicon.ico',
    shortcut: '/logo.png',
    apple: '/apple-touch-icon.png',
  },
  appleWebApp: {
    capable: true,
    statusBarStyle: 'black-translucent',
    title: 'Jasper Trades',
  },
};

export default function RootLayout({children}: {children: React.ReactNode}) {
  return (
    <html lang="en" className={`${inter.variable} ${jetbrainsMono.variable}`}>
      <body className="bg-[#0F172A] text-[#F8FAFC] antialiased" suppressHydrationWarning>
        {children}
      </body>
    </html>
  );
}
