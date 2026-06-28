'use client';

import React, { useState, useEffect } from 'react';
import { Newspaper, TrendingUp, Search, RefreshCw, AlertCircle } from 'lucide-react';
import { useCurrencyFormatter } from '@/lib/currencyContext';

interface NewsItem {
  id: string;
  source: 'twitter' | 'reddit' | 'xueqiu' | 'v2ex' | 'polymarket' | 'rss';
  title: string;
  content: string;
  url: string;
  author?: string;
  timestamp: string;
  tickers_mentioned?: string[];
  sentiment_score?: number;
  impact_score?: number;
}

interface MarketIntelProps {
  enabled?: boolean;
}

export default function MarketIntelligence({ enabled = true }: MarketIntelProps) {
  const { formatMoney } = useCurrencyFormatter();
  const [news, setNews] = useState<NewsItem[]>([]);
  const [trending, setTrending] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedSource, setSelectedSource] = useState<string>('all');
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);

  const fetchNews = async () => {
    try {
      const response = await fetch('/api/v1/market-intelligence/news?limit=20');
      const data = await response.json();
      
      if (data.success) {
        setNews(data.news || []);
        setLastUpdate(new Date());
      }
    } catch (error) {
      console.error('Failed to fetch news:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchTrending = async () => {
    try {
      const response = await fetch('/api/v1/market-intelligence/trending?limit=10');
      const data = await response.json();
      
      if (data.success) {
        setTrending(data.trending || []);
      }
    } catch (error) {
      console.error('Failed to fetch trending:', error);
    }
  };

  useEffect(() => {
    if (!enabled) return;
    
    fetchNews();
    fetchTrending();
    
    // Auto-refresh every 60 seconds
    const interval = setInterval(() => {
      fetchNews();
      fetchTrending();
    }, 60000);
    
    return () => clearInterval(interval);
  }, [enabled]);

  const filteredNews = news.filter(item => {
    const matchesSource = selectedSource === 'all' || item.source === selectedSource;
    const matchesSearch = !searchQuery || 
      item.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      item.content.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesSource && matchesSearch;
  });

  const getSourceIcon = (source: string) => {
    switch (source) {
      case 'twitter': return '🐦';
      case 'reddit': return '🤖';
      case 'xueqiu': return '📈';
      case 'v2ex': return '💻';
      case 'polymarket': return '🎯';
      case 'rss': return '📰';
      default: return '📰';
    }
  };

  const getSourceColor = (source: string) => {
    switch (source) {
      case 'twitter': return 'bg-blue-500/10 border-blue-500/30 text-blue-400';
      case 'reddit': return 'bg-orange-500/10 border-orange-500/30 text-orange-400';
      case 'xueqiu': return 'bg-red-500/10 border-red-500/30 text-red-400';
      case 'v2ex': return 'bg-green-500/10 border-green-500/30 text-green-400';
      case 'polymarket': return 'bg-purple-500/10 border-purple-500/30 text-purple-400';
      case 'rss': return 'bg-yellow-500/10 border-yellow-500/30 text-yellow-400';
      default: return 'bg-gray-500/10 border-gray-500/30 text-gray-400';
    }
  };

  const getSentimentColor = (score?: number) => {
    if (!score) return 'text-gray-400';
    if (score > 65) return 'text-green-400';
    if (score < 35) return 'text-red-400';
    return 'text-yellow-400';
  };

  if (!enabled) {
    return (
      <div className="bg-[#1E293B] rounded-lg p-6 border border-[#475569]">
        <div className="flex items-center gap-2 mb-4">
          <AlertCircle className="w-5 h-5 text-yellow-500" />
          <h3 className="text-lg font-bold text-[#F8FAFC]">Market Intelligence Disabled</h3>
        </div>
        <p className="text-[#94A3B8] text-sm mb-4">
          Agent Reach market intelligence is not enabled. To activate:
        </p>
        <ol className="list-decimal list-inside text-[#94A3B8] text-sm space-y-1 mb-4">
          <li>Install: <code className="bg-[#0F172A] px-2 py-1 rounded text-cyan-400">pip install agent-reach</code></li>
          <li>Configure: <code className="bg-[#0F172A] px-2 py-1 rounded text-cyan-400">AGENT_REACH_ENABLED=true</code></li>
          <li>Restart backend server</li>
        </ol>
        <p className="text-[#94A3B8] text-xs">
          See AGENT_REACH_INTEGRATION_PLAN.md for setup instructions.
        </p>
      </div>
    );
  }

  if (loading && news.length === 0) {
    return (
      <div className="bg-[#1E293B] rounded-lg p-6 border border-[#475569]">
        <div className="h-6 w-48 bg-gray-700 rounded animate-pulse mb-4" />
        <div className="space-y-3">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-20 bg-gray-800 rounded animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="bg-[#1E293B] rounded-lg p-6 border border-[#475569]">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Newspaper className="w-5 h-5 text-[#3B82F6]" />
          <h3 className="text-lg font-bold text-[#F8FAFC]">Market Intelligence</h3>
          {lastUpdate && (
            <span className="text-xs text-[#94A3B8] font-mono">
              Updated {lastUpdate.toLocaleTimeString()}
            </span>
          )}
        </div>
        <button
          onClick={() => {
            setLoading(true);
            fetchNews();
            fetchTrending();
          }}
          className="p-2 hover:bg-[#334155] rounded-lg transition text-[#94A3B8] hover:text-[#F8FAFC]"
          title="Refresh data"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* Search and Filters */}
      <div className="flex flex-col sm:flex-row gap-3 mb-4">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#94A3B8]" />
          <input
            type="text"
            placeholder="Search news..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full bg-[#0F172A] border border-[#475569] rounded-lg h-9 pl-10 pr-4 text-sm focus:outline-none focus:border-[#3B82F6] text-[#F8FAFC] placeholder-[#94A3B8]"
          />
        </div>
        <select
          value={selectedSource}
          onChange={(e) => setSelectedSource(e.target.value)}
          className="bg-[#0F172A] border border-[#475569] rounded-lg h-9 px-3 text-sm focus:outline-none focus:border-[#3B82F6] text-[#F8FAFC]"
        >
          <option value="all">All Sources</option>
          <option value="twitter">Twitter</option>
          <option value="reddit">Reddit</option>
          <option value="v2ex">V2EX</option>
          <option value="xueqiu">Xueqiu</option>
          <option value="polymarket">Polymarket</option>
          <option value="rss">RSS</option>
        </select>
      </div>

      {/* Trending Stocks */}
      {trending.length > 0 && (
        <div className="mb-4 p-3 bg-[#0F172A] rounded-lg border border-[#475569]">
          <div className="flex items-center gap-2 mb-2">
            <TrendingUp className="w-4 h-4 text-[#10B981]" />
            <span className="text-xs font-semibold text-[#F8FAFC]">Trending Stocks</span>
          </div>
          <div className="flex flex-wrap gap-2">
            {trending.map((item, idx) => (
              <span
                key={idx}
                className="inline-flex items-center gap-1 px-2 py-1 rounded bg-[#3B82F6]/10 border border-[#3B82F6]/30 text-[#3B82F6] text-xs font-mono"
              >
                {item.symbol}
                <span className="text-[#94A3B8]">({item.mention_count})</span>
              </span>
            ))}
          </div>
        </div>
      )}

      {/* News Feed */}
      <div className="space-y-3 max-h-[400px] overflow-y-auto">
        {filteredNews.length === 0 ? (
          <div className="text-center py-8 text-[#94A3B8] text-sm">
            {searchQuery ? 'No news matches your search' : 'No news available'}
          </div>
        ) : (
          filteredNews.map((item) => (
            <div
              key={item.id}
              className="p-3 bg-[#0F172A] rounded-lg border border-[#475569] hover:border-[#3B82F6] transition cursor-pointer"
              onClick={() => window.open(item.url, '_blank')}
            >
              <div className="flex items-start justify-between mb-2">
                <div className="flex items-center gap-2">
                  <span className="text-sm">{getSourceIcon(item.source)}</span>
                  <span className={`text-xs px-2 py-0.5 rounded border ${getSourceColor(item.source)}`}>
                    {item.source.toUpperCase()}
                  </span>
                  {item.tickers_mentioned && item.tickers_mentioned.length > 0 && (
                    <span className="text-xs font-mono text-[#3B82F6]">
                      {item.tickers_mentioned.join(', ')}
                    </span>
                  )}
                </div>
                <span className="text-xs text-[#94A3B8] font-mono">
                  {new Date(item.timestamp).toLocaleTimeString()}
                </span>
              </div>
              
              <h4 className="text-sm font-semibold text-[#F8FAFC] mb-1 line-clamp-2">
                {item.title}
              </h4>
              
              <p className="text-xs text-[#94A3B8] line-clamp-2 mb-2">
                {item.content}
              </p>
              
              <div className="flex items-center justify-between">
                {item.author && (
                  <span className="text-xs text-[#94A3B8]">@{item.author}</span>
                )}
                {item.sentiment_score && (
                  <span className={`text-xs font-semibold ${getSentimentColor(item.sentiment_score)}`}>
                    Sentiment: {item.sentiment_score.toFixed(0)}
                  </span>
                )}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}