import CryptoConnector from "@/components/settings/CryptoConnector";

export default function Page() {
  return (
    <main className="min-h-screen bg-gray-950 text-gray-100 p-8">
      <h1 className="text-2xl font-bold mb-6">Crypto Connector</h1>
      <CryptoConnector />
    </main>
  );
}
