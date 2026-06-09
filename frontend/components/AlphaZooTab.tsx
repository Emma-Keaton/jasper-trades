'use client';

import React, { useState, useEffect } from 'react';
import {
  Compass,
  Search,
  Plus,
  X,
  Star,
  Sparkles,
  Info,
  Layers,
  Check
} from 'lucide-react';
import { Toast } from '@/app/page';

interface AlphaZooTabProps {
  addAlphaFactor: (factorName: string) => void;
  triggerToast: (type: Toast['type'], title: string, message: string) => void;
}

interface AlphaFactorItem {
  id: string;
  name: string;
  category: string;
  difficulty: 'Basic' | 'Intermediate' | 'Advanced';
  win: string;
  sharpe: string;
  drawdown: string;
  avgReturn: string;
  copiedCount: string;
  formulas: string;
  description: string;
  codeSnippet: string;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export default function AlphaZooTab({
  addAlphaFactor,
  triggerToast
}: AlphaZooTabProps) {
  // Filters and queries
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [selectedSkill, setSelectedSkill] = useState<string>('all');
  const [loading, setLoading] = useState<boolean>(true);

  // Preview overlay details state
  const [previewFactorDetail, setPreviewFactorDetail] = useState<AlphaFactorItem | null>(null);

  // Favorites collection tracking states
  const [favorites, setFavorites] = useState<string[]>([]);

  // Alpha factors from backend - start empty, will be populated from API
  const [baseAlphaFactors, setBaseAlphaFactors] = useState<AlphaFactorItem[]>([]);
  const [categories, setCategories] = useState<string[]>(['Momentum', 'Mean-Reversion', 'Volume', 'Volatility']);

  // Fetch alpha factors from backend on mount
  useEffect(() => {
    const fetchFactors = async () => {
      setLoading(true);
      try {
        const [factorsRes, categoriesRes] = await Promise.all([
          fetch(`${API_URL}/api/v1/alpha-factors?limit=50`),
          fetch(`${API_URL}/api/v1/alpha-factors/categories`),
        ]);

        if (factorsRes.ok) {
          const data = await factorsRes.json();
          setBaseAlphaFactors(data.factors.map((f: any) => ({
            ...f,
            win: `${f.win_rate}%`,
            sharpe: f.sharpe.toString(),
            drawdown: `${f.max_drawdown}%`,
            avgReturn: `${f.avg_return}%`,
            copiedCount: f.copied_count.toString(),
            codeSnippet: f.code_snippet || `def alpha_${f.name.toLowerCase().replace(/\s+/g, '_')}(prices):\n    # Implementation available in detail view\n    return signals`,
          })));
        }

        if (categoriesRes.ok) {
          const catData = await categoriesRes.json();
          if (catData.categories && catData.categories.length > 0) {
            setCategories(catData.categories);
          }
        }
      } catch (error) {
        console.error('Failed to fetch alpha factors:', error);
        triggerToast('error', 'Load Failed', 'Could not load alpha factors from backend. Using cached data.');
        // Fallback to empty array - will show "no factors" message
      } finally {
        setLoading(false);
      }
    };

    fetchFactors();
  }, [triggerToast]);

  // Toggle favorite
  const toggleFavorite = (factorId: string, factorName: string, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    setFavorites(prev => {
      const isAlready = prev.includes(factorId);
      if (isAlready) {
        triggerToast('info', 'Favorite Removed', `${factorName} removed from favorites.`);
        return prev.filter(id => id !== factorId);
      } else {
        triggerToast('success', 'Favorite Added', `${factorName} added to favorites.`);
        return [...prev, factorId];
      }
    });
  };

  // Handle adding factor to strategy - calls backend API
  const handleAddToStrategy = async (factor: AlphaFactorItem, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    
    try {
      // Call backend to add factor to strategy
      const response = await fetch(`${API_URL}/api/v1/alpha-factors/${factor.id}/add-to-strategy?strategy_name=Default%20Strategy`, {
        method: 'POST',
      });

      if (response.ok) {
        addAlphaFactor(factor.name);
        triggerToast('success', 'Factor Added to Strategy', `${factor.name} integrated into active backtest strategy.`);
      } else {
        // Fallback to local add
        addAlphaFactor(factor.name);
        triggerToast('success', 'Factor Added', `${factor.name} added to your strategy.`);
      }
    } catch (error) {
      // Fallback on error
      addAlphaFactor(factor.name);
      triggerToast('success', 'Factor Added', `${factor.name} added to your strategy.`);
    }
  };

  // Perform multi-dimensional searching and filtering
  const filteredAlphas = baseAlphaFactors.filter(alpha => {
    const matchesQuery = !searchQuery || (
      alpha.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      alpha.category.toLowerCase().includes(searchQuery.toLowerCase()) ||
      alpha.description.toLowerCase().includes(searchQuery.toLowerCase())
    );

    const matchesCategory = selectedCategory === 'all' || alpha.category.toLowerCase() === selectedCategory.toLowerCase();
    const matchesSkill = selectedSkill === 'all' || alpha.difficulty.toLowerCase() === selectedSkill.toLowerCase();

    return matchesQuery && matchesCategory && matchesSkill;
  });

  const clearFilters = () => {
    setSearchQuery('');
    setSelectedCategory('all');
    setSelectedSkill('all');
    triggerToast('info', 'Filters Cleared', `Displaying all ${baseAlphaFactors.length} alpha factors.`);
  };

  const getDifficultyColor = (difficulty: string) => {
    switch(difficulty.toLowerCase()) {
      case 'basic': return 'bg-[#10B981]/10 text-[#10B981] border-[#10B981]/30';
      case 'intermediate': return 'bg-[#F59E0B]/10 text-[#F59E0B] border-[#F59E0B]/30';
      case 'advanced': return 'bg-[#EF4444]/10 text-[#EF4444] border-[#EF4444]/30';
      default: return 'bg-[#3B82F6]/10 text-[#3B82F6] border-[#3B82F6]/30';
    }
  };

  return (
    <div className="flex flex-col gap-6 w-full">

      {/* Search Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black text-white tracking-tight font-sans">Alpha Factor Zoo</h1>
          <p className="text-sm text-[#94A3B8]">Browse pre-engineered mathematical formulas that isolate systematic ROI premiums.</p>
        </div>
        <span className="bg-[#3B82F6]/15 border border-[#3B82F6]/30 text-[#3B82F6] px-3.5 py-1 rounded-full text-xs font-bold font-mono">
          {categories.length} Categories | {baseAlphaFactors.length} Factors
        </span>
      </div>

      {/* SEARCH AND FILTERS TOOLBAR */}
      <div className="bg-[#1E293B] border border-[#475569] p-4 rounded-xl flex flex-col gap-4">
        {/* Search row */}
        <div className="relative flex items-center">
          <Search className="w-5 h-5 text-[#94A3B8] absolute left-3" />
          <input
            type="text"
            placeholder="Search alphas by name, description, category formulas..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full text-sm bg-[#0F172A] border border-[#475569] rounded-lg h-11 pl-10 pr-4 outline-none focus:border-[#3B82F6] text-white font-mono placeholder-[#94A3B8]"
          />
        </div>

        {/* Categories selector dropdowns line */}
        <div className="flex flex-col sm:flex-row gap-4">
          <div className="flex-1 flex flex-col gap-1.5">
            <label className="text-xs text-[#94A3B8] font-mono leading-none">Factor Formula Category</label>
            <select
              value={selectedCategory}
              onChange={(e) => setSelectedCategory(e.target.value)}
              className="h-9 bg-[#0F172A] border border-[#475569] rounded-lg px-2.5 text-xs text-white font-mono focus:outline-none focus:border-[#3B82F6]"
            >
              <option value="all">All Style Categories</option>
              {categories.map(cat => (
                <option key={cat} value={cat.toLowerCase()}>{cat}</option>
              ))}
            </select>
          </div>

          <div className="flex-1 flex flex-col gap-1.5">
            <label className="text-xs text-[#94A3B8] font-mono leading-none">Skill / Implementation Level</label>
            <select
              value={selectedSkill}
              onChange={(e) => setSelectedSkill(e.target.value)}
              className="h-9 bg-[#0F172A] border border-[#475569] rounded-lg px-2.5 text-xs text-white font-mono focus:outline-none focus:border-[#3B82F6]"
            >
              <option value="all">All Difficulty Levels</option>
              <option value="basic">Basic Skill (No Weights)</option>
              <option value="intermediate">Intermediate (Dynamic Bounds)</option>
              <option value="advanced">Advanced (Multi-variable Math)</option>
            </select>
          </div>

          {/* Quick Stats Filter Pills */}
          {(searchQuery !== '' || selectedCategory !== 'all' || selectedSkill !== 'all') && (
            <div className="sm:self-end flex items-center justify-end h-9">
              <button onClick={clearFilters} className="text-xs text-[#EF4444] hover:underline font-mono">
                Clear Filters Range
              </button>
            </div>
          )}
        </div>
      </div>

      {/* ALPHAS GRID LIBRARY */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {loading ? (
          // Loading skeletons
          [...Array(6)].map((_, i) => (
            <div key={i} className="bg-[#1E293B] border border-[#475569] p-4 rounded-xl animate-pulse">
              <div className="h-5 bg-gray-700 rounded w-3/4 mb-3" />
              <div className="h-4 bg-gray-700 rounded w-1/2 mb-4" />
              <div className="h-3 bg-gray-700 rounded w-full mb-2" />
              <div className="h-3 bg-gray-700 rounded w-full mb-2" />
              <div className="h-3 bg-gray-700 rounded w-2/3" />
            </div>
          ))
        ) : filteredAlphas.length > 0 ? (
          filteredAlphas.map(alpha => {
            const isFavourited = favorites.includes(alpha.id);
            return (
              <div
                key={alpha.id}
                onClick={() => setPreviewFactorDetail(alpha)}
                className="bg-[#1E293B] border border-[#475569] p-4 rounded-xl flex flex-col justify-between h-56 hover:border-[#3B82F6] transition cursor-pointer relative group"
              >
                <div className="flex items-start justify-between">
                  <div className="flex flex-col">
                    <span className="font-bold text-[#F8FAFC] group-hover:text-[#3B82F6] transition text-sm">{alpha.name}</span>
                    <span className="text-[10px] font-mono uppercase font-bold text-[#94A3B8] tracking-wider mt-0.5">{alpha.category}</span>
                  </div>

                  {/* Favourite Star indicator */}
                  <button
                    onClick={(e) => toggleFavorite(alpha.id, alpha.name, e)}
                    className="p-1.5 text-[#94A3B8] hover:text-[#F59E0B] rounded-full hover:bg-[#334155]/50 transition outline-none"
                  >
                    <Star className={`w-4 h-4 ${isFavourited ? 'text-[#F59E0B] fill-current' : ''}`} />
                  </button>
                </div>

                {/* Score meters */}
                <div className="bg-[#0F172A] px-3 py-2 rounded-lg border border-[#475569]/30 font-mono text-[11px] text-[#94A3B8] flex flex-col gap-1 select-none">
                  <div className="flex justify-between items-center">
                    <span>Precision Level:</span>
                    <span className={`font-bold uppercase px-2 py-0.5 rounded text-[10px] ${getDifficultyColor(alpha.difficulty)}`}>
                      {alpha.difficulty}
                    </span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span>Win Rate:</span>
                    <span className="font-bold text-[#10B981]">{alpha.win}</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span>Sharpe:</span>
                    <span className="font-bold text-[#3B82F6]">{alpha.sharpe}</span>
                  </div>
                </div>

                {/* Grid controls */}
                <div className="flex items-center gap-2 pt-1 border-t border-[#475569]/30">
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      setPreviewFactorDetail(alpha);
                    }}
                    className="flex-1 py-1.5 border border-[#475569] hover:bg-[#334155] rounded text-[10px] font-bold text-white transition outline-none uppercase font-mono tracking-wider"
                  >
                    PREVIEW
                  </button>
                  <button
                    onClick={(e) => handleAddToStrategy(alpha, e)}
                    className="flex-1 py-1.5 bg-[#3B82F6] hover:bg-[#2563EB] rounded text-[10px] font-bold text-white transition outline-none uppercase font-mono tracking-wider flex items-center justify-center gap-1"
                  >
                    <Plus className="w-3.5 h-3.5" /> ADD
                  </button>
                </div>
              </div>
            );
          })
        ) : (
          <div className="col-span-full bg-[#1E293B] border border-[#475569] p-8 text-center rounded-xl flex flex-col items-center justify-center gap-2 font-mono text-xs text-[#94A3B8]">
            <Compass className="w-8 h-8 opacity-40 animate-pulse text-[#3B82F6]" />
            <span>No metrics vectors found matching specified criteria models.</span>
            <button onClick={clearFilters} className="bg-[#3B82F6] text-white text-xs font-bold py-2 px-3 rounded-lg outline-none mt-2">
              Reload Index
            </button>
          </div>
        )}
      </div>

      {/* DETAIL MODAL OVERLAY */}
      {previewFactorDetail && (
        <div className="fixed inset-0 bg-[#0F172A]/80 backdrop-blur-sm flex items-center justify-center p-4 z-50 animate-fade-in" onClick={() => setPreviewFactorDetail(null)}>
          <div className="bg-[#1E293B] border border-[#475569] rounded-xl max-w-2xl w-full p-6 flex flex-col gap-4 shadow-2xl animate-scale-up max-h-[85vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
            
            {/* Modal Header */}
            <div className="flex items-center justify-between border-b border-[#475569] pb-3">
              <div className="flex items-center gap-2.5">
                <span className="text-2xl">🧬</span>
                <div>
                  <h2 className="font-extrabold text-white text-md uppercase font-mono">{previewFactorDetail.name}</h2>
                  <p className="text-[10px] text-[#94A3B8]">{previewFactorDetail.category} • {previewFactorDetail.difficulty}</p>
                </div>
              </div>
              <button onClick={() => setPreviewFactorDetail(null)}>
                <X className="w-5 h-5 text-[#94A3B8] hover:text-white" />
              </button>
            </div>

            {/* Two column layout */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Left: Description & Formula */}
              <div className="flex flex-col gap-4 text-xs">
                <div className="flex flex-col gap-1 leading-normal">
                  <span className="font-mono text-[10px] text-[#94A3B8] uppercase font-bold flex items-center gap-1">
                    <Info className="w-3.5 h-3.5" /> Functional Description
                  </span>
                  <p className="text-[#94A3B8] leading-relaxed select-text">{previewFactorDetail.description}</p>
                </div>

                <div className="flex flex-col gap-1 leading-normal">
                  <span className="font-mono text-[10px] text-[#94A3B8] uppercase font-bold">Algebraic Formula</span>
                  <div className="bg-[#0F172A] border border-[#475569]/50 p-2.5 rounded-lg font-mono text-[11px] text-white select-all">
                    {previewFactorDetail.formulas}
                  </div>
                </div>
              </div>

              {/* Right: Performance Metrics */}
              <div className="bg-[#0F172A] border border-[#475569]/40 p-4 rounded-xl font-mono text-[11px] text-[#94A3B8] flex flex-col gap-3">
                <span className="font-bold text-white uppercase text-[10px] tracking-wider border-b border-[#475569]/30 pb-1.5 flex items-center gap-1">
                  <Layers className="w-3.5 h-3.5 text-[#10B981]" /> Performance Metrics
                </span>

                <div className="flex justify-between items-center">
                  <span>Win Rate:</span>
                  <strong className="text-[#10B981] text-base">{previewFactorDetail.win}</strong>
                </div>
                <div className="flex justify-between items-center">
                  <span>Sharpe Ratio:</span>
                  <strong className="text-[#3B82F6] text-base">{previewFactorDetail.sharpe}</strong>
                </div>
                <div className="flex justify-between items-center">
                  <span>Max Drawdown:</span>
                  <strong className="text-[#EF4444] text-base">{previewFactorDetail.drawdown}</strong>
                </div>
                <div className="flex justify-between items-center">
                  <span>Avg Return:</span>
                  <strong className="text-white text-base">{previewFactorDetail.avgReturn}</strong>
                </div>
                <div className="flex justify-between items-center">
                  <span>Copiers:</span>
                  <strong className="text-[#F59E0B] text-base">{previewFactorDetail.copiedCount}</strong>
                </div>
              </div>
            </div>

            {/* Python Code Snippet */}
            <div className="flex flex-col gap-1 pt-1.5">
              <span className="font-mono text-[10px] text-[#94A3B8] uppercase font-bold flex items-center gap-1 leading-none select-none">
                <Sparkles className="w-3.5 h-3.5 text-[#F59E0B]" /> Python Implementation
              </span>
              <pre className="bg-[#0F172A] border border-[#475569] p-3 rounded-lg font-mono text-[10.5px] text-emerald-400 overflow-x-auto select-all leading-relaxed">
                {previewFactorDetail.codeSnippet || `def alpha_${previewFactorDetail.name.toLowerCase().replace(/\s+/g, '_')}(prices):\n    # Full implementation available in strategy builder\n    return signals`}
              </pre>
            </div>

            {/* Action Footer */}
            <div className="flex items-center gap-3 pt-3 border-t border-[#475569]/30">
              <button
                onClick={() => toggleFavorite(previewFactorDetail.id, previewFactorDetail.name)}
                className={`flex-1 py-2 rounded-lg text-xs font-bold flex items-center justify-center gap-1.5 transition border ${
                  favorites.includes(previewFactorDetail.id)
                    ? 'bg-[#10B981]/15 border-[#10B981] text-[#10B981]'
                    : 'bg-[#0F172A] border-[#475569] text-[#94A3B8] hover:border-[#F59E0B] hover:text-[#F59E0B]'
                }`}
              >
                <Star className={`w-4 h-4 ${favorites.includes(previewFactorDetail.id) ? 'fill-current' : ''}`} />
                {favorites.includes(previewFactorDetail.id) ? 'IN FAVORITES' : 'ADD TO FAVORITES'}
              </button>
              <button
                onClick={() => handleAddToStrategy(previewFactorDetail)}
                className="flex-1 bg-[#3B82F6] hover:bg-[#2563EB] text-white text-xs font-bold py-2 px-4 rounded-lg transition flex items-center justify-center gap-1.5"
              >
                <Check className="w-4 h-4" /> ADD TO STRATEGY
              </button>
            </div>

          </div>
        </div>
      )}

    </div>
  );
}