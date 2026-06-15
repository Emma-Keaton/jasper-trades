'use client';

import React, { useState } from 'react';
import { polymarketAPI } from '@/lib/api-client';
import { Loader2, TrendingUp, Search } from 'lucide-react';

export function PolymarketPanel() {
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<any[]>([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [view, setView] = useState<'search' | 'trending'>('trending');

  const loadTrending = async () => {
    setLoading(true);
    setView('trending');
    const response = await polymarketAPI.getTrending();
    if (response.data) {
      setResults(Array.isArray(response.data) ? response.data : []);
    }
    setLoading(false);
  };

  const handleSearch = async (query: string) => {
    if (!query) return;
    setLoading(true);
    setView('search');
    const response = await polymarketAPI.search(query);
    if (response.data) {
      // Handle both array and wrapped response
      const items = Array.isArray(response.data) 
        ? response.data 
        : response.data.results || [];
      setResults(items);
    }
    setLoading(false);
  };

  React.useEffect(() => {
    loadTrending();
  }, []);

  return (
    <div className="space-y-4">
      {/* Search Bar */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#64748B]" />
        <input
          type="text"
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSearch(searchTerm)}
          placeholder="Search prediction markets..."
          className="w-full bg-[#0F172A] border border-[#475569] rounded-lg pl-10 pr-20 py-2.5 text-sm text-[#F8FAFC] focus:outline-none focus:border-[#3B82F6]"
        />
        <button
          onClick={() => handleSearch(searchTerm)}
          disabled={loading || !searchTerm}
          className="absolute right-2 top-1/2 -translate-y-1/2 bg-[#3B82F6] hover:bg-[#2563EB] text-white text-xs font-bold py-1.5 px-3 rounded transition disabled:opacity-50"
        >
          Search
        </button>
      </div>

      {/* View Toggle */}
      <div className="flex gap-2">
        <button
          onClick={loadTrending}
          className={`flex items-center gap-2 px-3 py-1.5 rounded text-xs font-mono transition ${
            view === 'trending'
              ? 'bg-[#3B82F6] text-white'
              : 'bg-[#1E293B] text-[#94A3B8] hover:bg-[#334155]'
          }`}
        >
          <TrendingUp className="w-3 h-3" />
          Trending
        </button>
      </div>

      {/* Results */}
      {loading ? (
        <div className="flex items-center justify-center py-8 text-[#94A3B8]">
          <Loader2 className="w-6 h-6 animate-spin mr-2" />
          <span>Loading markets...</span>
        </div>
      ) : results.length > 0 ? (
        <div className="space-y-2 max-h-96 overflow-y-auto">
          {results.map((market: any, index: number) => (
            <div
              key={market.id || market.slug || index}
              className="p-3 bg-[#1E293B] border border-[#475569] rounded-lg hover:border-[#3B82F6]/50 transition cursor-pointer"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <h4 className="text-sm font-bold text-[#F8FAFC] truncate">
                    {market.title || market.name || 'Unnamed Market'}
                  </h4>
                  {market.description && (
                    <p className="text-xs text-[#94A3B8] mt-1 line-clamp-2">
                      {market.description}
                    </p>
                  )}
                  {market.category && (
                    <span className="inline-block mt-2 text-[10px] px-1.5 py-0.5 rounded bg-[#3B82F6]/20 text-[#3B82F6] font-mono">
                      {market.category}
                    </span>
                  )}
                </div>
                {market.volume_24h && (
                  <div className="text-right">
                    <div className="text-xs text-[#94A3B8]">24h Volume</div>
                    <div className="text-sm font-bold text-[#10B981]">
                      {typeof market.volume_24h === 'number'
                        ? `$${market.volume_24h.toLocaleString()}`
                        : market.volume_24h}
                    </div>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="text-center py-8 text-[#94A3B8] text-sm">
          {view === 'trending' ? 'No trending markets' : 'No results found'}
        </div>
      )}
    </div>
  );
}