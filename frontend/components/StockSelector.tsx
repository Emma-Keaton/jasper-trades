'use client';

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Search, X, Check, ChevronDown } from 'lucide-react';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface StockSymbol {
  symbol: string;
  name: string;
  exchange: string;
  type: string;
  currency: string;
}

interface StockSelectorProps {
  value?: string;
  onChange: (symbol: string) => void;
  placeholder?: string;
  multiple?: boolean;
  className?: string;
  filterByExchange?: 'US' | 'NGX' | 'all';
}

export default function StockSelector({
  value,
  onChange,
  placeholder = 'Search stocks...',
  multiple = false,
  className = '',
  filterByExchange = 'all',
}: StockSelectorProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [symbols, setSymbols] = useState<StockSymbol[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedSymbols, setSelectedSymbols] = useState<string[]>([]);
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Debounce search
  const debouncedSearch = useCallback(
    debounce((term: string) => {
      if (term.length >= 2) {
        fetchSymbols(term);
      } else if (term.length === 0) {
        fetchSymbols('');
      }
    }, 300),
    []
  );

  useEffect(() => {
    if (value && !selectedSymbols.includes(value)) {
      setSelectedSymbols([value]);
    }
  }, [value]);

  useEffect(() => {
    // Initial load - fetch popular symbols
    fetchSymbols('');
  }, []);

  useEffect(() => {
    if (searchTerm) {
      debouncedSearch(searchTerm);
    }
  }, [searchTerm, debouncedSearch]);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const getDeviceId = () => {
    let deviceId = localStorage.getItem('device_id');
    if (!deviceId) {
      deviceId = 'dev_' + Math.random().toString(36).substring(2, 15);
      localStorage.setItem('device_id', deviceId);
    }
    return deviceId;
  };

  const fetchSymbols = async (search: string) => {
    setLoading(true);
    try {
      const deviceId = getDeviceId();
      const params = new URLSearchParams({
        search,
        exchange: filterByExchange,
      });

      const res = await fetch(`${API_URL}/api/v1/symbols?${params}`, {
        headers: { 'X-Device-ID': deviceId },
      });

      if (res.ok) {
        const data = await res.json();
        setSymbols(data.symbols || []);
      }
    } catch (err) {
      console.error('Failed to fetch symbols:', err);
      // Fallback to empty list
      setSymbols([]);
    } finally {
      setLoading(false);
    }
  };

  const handleSelect = (symbol: string) => {
    if (multiple) {
      const newSelected = selectedSymbols.includes(symbol)
        ? selectedSymbols.filter(s => s !== symbol)
        : [...selectedSymbols, symbol];
      
      setSelectedSymbols(newSelected);
      onChange(newSelected.join(','));
    } else {
      setSelectedSymbols([symbol]);
      onChange(symbol);
      setSearchTerm('');
      setIsOpen(false);
    }
  };

  const handleClear = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (multiple) {
      setSelectedSymbols([]);
      onChange('');
    } else {
      setSelectedSymbols([]);
      onChange('');
      setSearchTerm('');
    }
    inputRef.current?.focus();
  };

  const toggleDropdown = () => {
    setIsOpen(!isOpen);
    if (!isOpen) {
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  };

  const getDisplayValue = () => {
    if (multiple && selectedSymbols.length > 0) {
      return `${selectedSymbols.length} stock(s) selected`;
    }
    if (value) {
      const symbol = symbols.find(s => s.symbol === value);
      return symbol ? `${symbol.symbol} - ${symbol.name}` : value;
    }
    return '';
  };

  const filteredSymbols = symbols.filter(symbol => {
    if (filterByExchange !== 'all' && symbol.exchange !== filterByExchange) {
      return false;
    }
    if (searchTerm) {
      const term = searchTerm.toLowerCase();
      return (
        symbol.symbol.toLowerCase().includes(term) ||
        symbol.name.toLowerCase().includes(term)
      );
    }
    return true;
  });

  const getExchangeBadgeColor = (exchange: string) => {
    switch (exchange) {
      case 'NGX':
        return 'bg-green-500/20 text-green-400 border-green-500/30';
      case 'NASDAQ':
        return 'bg-blue-500/20 text-blue-400 border-blue-500/30';
      case 'NYSE':
        return 'bg-purple-500/20 text-purple-400 border-purple-500/30';
      default:
        return 'bg-gray-500/20 text-gray-400 border-gray-500/30';
    }
  };

  return (
    <div ref={containerRef} className={`relative ${className}`}>
      {/* Trigger Button */}
      <button
        type="button"
        onClick={toggleDropdown}
        className="w-full h-11 bg-[#0F172A] border border-[#475569] rounded-lg px-3 py-2 text-sm text-[#F8FAFC] font-mono focus:outline-none focus:border-[#3B82F6] transition flex items-center justify-between gap-2"
      >
        <span className="flex-1 text-left truncate">
          {getDisplayValue() || placeholder}
        </span>
        {getDisplayValue() && (
          <button
            onClick={handleClear}
            className="p-1 hover:bg-[#334155] rounded transition"
          >
            <X className="w-4 h-4" />
          </button>
        )}
        <ChevronDown className={`w-4 h-4 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
      </button>

      {/* Dropdown Panel */}
      {isOpen && (
        <div className="absolute z-50 w-full mt-2 bg-[#1E293B] border border-[#475569] rounded-xl shadow-xl overflow-hidden">
          {/* Search Input */}
          <div className="p-3 border-b border-[#475569]">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#64748B]" />
              <input
                ref={inputRef}
                type="text"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                placeholder="Search by symbol or name..."
                className="w-full bg-[#0F172A] border border-[#475569] rounded-lg pl-10 pr-10 py-2.5 text-sm text-[#F8FAFC] focus:outline-none focus:border-[#3B82F6] placeholder:text-[#64748B]"
                autoFocus
              />
              {searchTerm && (
                <button
                  onClick={() => setSearchTerm('')}
                  className="absolute right-3 top-1/2 -translate-y-1/2 p-1 hover:bg-[#334155] rounded"
                >
                  <X className="w-3 h-3 text-[#64748B]" />
                </button>
              )}
            </div>
          </div>

          {/* Results */}
          <div className="max-h-64 overflow-y-auto">
            {loading ? (
              <div className="p-4 text-center text-[#94A3B8] text-sm">
                <div className="animate-pulse">Loading symbols...</div>
              </div>
            ) : filteredSymbols.length > 0 ? (
              <div className="p-2">
                {filteredSymbols.map((symbol) => {
                  const isSelected = multiple
                    ? selectedSymbols.includes(symbol.symbol)
                    : value === symbol.symbol;

                  return (
                    <button
                      key={symbol.symbol}
                      onClick={() => handleSelect(symbol.symbol)}
                      className={`w-full p-3 rounded-lg mb-1 last:mb-0 text-left transition flex items-center gap-3 ${
                        isSelected
                          ? 'bg-[#3B82F6]/20 border border-[#3B82F6]/40'
                          : 'hover:bg-[#334155] border border-transparent'
                      }`}
                    >
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="font-bold text-white text-sm">
                            {symbol.symbol}
                          </span>
                          <span className={`text-[10px] px-1.5 py-0.5 rounded border font-mono uppercase ${getExchangeBadgeColor(symbol.exchange)}`}>
                            {symbol.exchange}
                          </span>
                        </div>
                        <div className="text-xs text-[#94A3B8] truncate mt-0.5">
                          {symbol.name}
                        </div>
                      </div>
                      {isSelected && (
                        <Check className="w-4 h-4 text-[#3B82F6] flex-shrink-0" />
                      )}
                    </button>
                  );
                })}
              </div>
            ) : (
              <div className="p-4 text-center text-[#94A3B8] text-sm">
                {searchTerm ? (
                  <>
                    <div className="mb-1">No stocks found</div>
                    <div className="text-xs">Try searching for "{searchTerm}"</div>
                  </>
                ) : (
                  'No symbols available'
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// Debounce utility function
function debounce<T extends (...args: any[]) => any>(
  func: T,
  wait: number
): (...args: Parameters<T>) => void {
  let timeout: NodeJS.Timeout | null = null;

  return (...args: Parameters<T>) => {
    if (timeout) clearTimeout(timeout);
    timeout = setTimeout(() => func(...args), wait);
  };
}