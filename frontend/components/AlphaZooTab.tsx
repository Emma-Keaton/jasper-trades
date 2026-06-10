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

interface AlphaZooTabProps {
  addAlphaFactor: (factorName: string) => void;
  triggerToast: (type: Toast['type'], title: string, message: string) => void;
}

export default function AlphaZooTab({
  addAlphaFactor,
  triggerToast
}: AlphaZooTabProps) {
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [selectedSkill, setSelectedSkill] = useState<string>('all');
  const [loading, setLoading] = useState<boolean>(true);
  const [previewFactorDetail, setPreviewFactorDetail] = useState<AlphaFactorItem | null>(null);
  const [favorites, setFavorites] = useState<string[]>([]);
  const [baseAlphaFactors, setBaseAlphaFactors] = useState<AlphaFactorItem[]>([]);
  const [categories, setCategories] = useState<string[]>(['Momentum', 'Mean-Reversion', 'Volume', 'Volatility']);

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
          setBaseAlphaFactors(data.factors?.map((f: any) => ({
            ...f,
            win: `${f.win_rate}%`,
            sharpe: f.sharpe.toString(),
            drawdown: `${f.max_drawdown}%`,
            avgReturn: `${f.avg_return}%`,
            copiedCount: f.copied_count.toString(),
            codeSnippet: f.code_snippet || `def alpha_${f.name.toLowerCase().replace(/\s+/g, '_')}(prices):\n    return signals`,
          })) || []);
        }

        if (categoriesRes.ok) {
          const catData = await categoriesRes.json();
          if (catData.categories) setCategories(catData.categories);
        }
      } catch (error) {
        console.error('Failed to fetch alpha factors:', error);
        triggerToast('error', 'Load Failed', 'Could not load alpha factors from backend.');
      } finally {
        setLoading(false);
      }
    };

    fetchFactors();
  }, [triggerToast]);

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

  const handleAddToStrategy = async (factor: AlphaFactorItem, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    try {
      const response = await fetch(`${API_URL}/api/v1/alpha-factors/${factor.id}/add-to-strategy?strategy_name=Default%20Strategy`, { method: 'POST' });
      if (response.ok) {
        addAlphaFactor(factor.name);
        triggerToast('success', 'Factor Added to Strategy', `${factor.name} integrated into active backtest strategy.`);
      } else {
        addAlphaFactor(factor.name);
        triggerToast('success', 'Factor Added', `${factor.name} added to your strategy.`);
      }
    } catch (error) {
      addAlphaFactor(factor.name);
      triggerToast('success', 'Factor Added', `${factor.name} added to your strategy.`);
    }
  };

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
    <div 
      data-onboarding="alphazoo-tour"
      className="flex flex-col gap-6 w-full"
    >

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

      {/* SEARCH TOOLBAR */}
      <div 
        data-onboarding="search-bar"
        className="bg-[#1E293B] border border-[#475569] p-4 rounded-xl flex flex-col gap-4"
      >
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

        <div 
          data-onboarding="category-filters"
          className="flex flex-col sm:flex-row gap-4"
        >
          <div className="flex-1 flex flex-col gap-1.5">
            <label className="text-xs text-[#94A3B8] font-mono">Category Type Filter</label>
            <select
              value={selectedCategory}
              onChange={(e) => setSelectedCategory(e.target.value)}
              className="h-10 bg-[#0F172A] border border-[#475569] rounded-lg px-3 text-xs text-white font-mono focus:outline-none focus:border-[#3B82F6]"
            >
              <option value="all">All Categories</option>
              {categories.map(cat => (
                <option key={cat} value={cat.toLowerCase()}>{cat}</option>
              ))}
            </select>
          </div>

          <div className="flex-1 flex flex-col gap-1.5">
            <label className="text-xs text-[#94A3B8] font-mono">Complexity Skill Level</label>
            <select
              value={selectedSkill}
              onChange={(e) => setSelectedSkill(e.target.value)}
              className="h-10 bg-[#0F172A] border border-[#475569] rounded-lg px-3 text-xs text-white font-mono focus:outline-none focus:border-[#3B82F6]"
            >
              <option value="all">All Difficulty Levels</option>
              <option value="basic">Basic</option>
              <option value="intermediate">Intermediate</option>
              <option value="advanced">Advanced</option>
            </select>
          </div>

          {(searchQuery || selectedCategory !== 'all' || selectedSkill !== 'all') && (
            <div className="flex items-end">
              <button
                onClick={clearFilters}
                className="h-10 px-4 bg-[#EF4444]/10 hover:bg-[#EF4444]/20 text-[#EF4444] border border-[#EF4444]/30 rounded-lg text-xs font-bold transition outline-none"
              >
                CLEAR
              </button>
            </div>
          )}
        </div>
      </div>

      {/* ALPHA FACTORS LIST */}
      {loading ? (
        <div className="flex items-center justify-center py-24">
          <div className="flex flex-col items-center gap-4">
            <div className="w-12 h-12 border-4 border-[#3B82F6] border-t-transparent rounded-full animate-spin" />
            <p className="text-[#94A3B8] font-mono text-sm">Loading alpha factor library...</p>
          </div>
        </div>
      ) : filteredAlphas.length === 0 ? (
        <div className="bg-[#1E293B] border border-[#475569] p-12 text-center rounded-xl">
          <Compass className="w-12 h-12 text-[#94A3B8] mx-auto mb-4 opacity-50" />
          <h3 className="text-lg font-bold text-white mb-2">No Alpha Factors Found</h3>
          <p className="text-sm text-[#94A3B8] mb-4">Try adjusting your search or filter criteria.</p>
          <button onClick={clearFilters} className="text-xs bg-[#3B82F6] hover:bg-[#2563EB] text-white px-4 py-2 rounded-lg transition">
            Reset All Filters
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {filteredAlphas.map(factor => {
            const isFav = favorites.includes(factor.id);
            return (
              <div
                key={factor.id}
                onClick={() => setPreviewFactorDetail(factor)}
                className="bg-[#1E293B] border border-[#475569] p-4 rounded-xl hover:border-[#3B82F6]/50 transition cursor-pointer group relative overflow-hidden"
              >
                {/* Difficulty badge */}
                <div 
                  data-onboarding="difficulty-badge"
                  className={`absolute top-3 right-3 px-2 py-0.5 rounded text-[9px] font-bold uppercase border ${getDifficultyColor(factor.difficulty)}`}
                >
                  {factor.difficulty}
                </div>

                {/* Factor name */}
                <h3 className="font-black text-white text-md mb-1 group-hover:text-[#3B82F6] transition">{factor.name}</h3>
                <p className="text-[10px] text-[#94A3B8] font-mono mb-3">{factor.category} Complex</p>

                {/* Metrics grid */}
                <div className="grid grid-cols-3 gap-2 text-[10px] font-mono mb-3">
                  <div className="flex flex-col gap-0.5">
                    <span className="text-[#94A3B8]" data-onboarding="win-rate">Win Rate</span>
                    <span className="font-bold text-[#10B981]">{factor.win}</span>
                  </div>
                  <div className="flex flex-col gap-0.5">
                    <span className="text-[#94A3B8]" data-onboarding="sharpe-ratio">Sharpe</span>
                    <span className="font-bold text-[#3B82F6]">{factor.sharpe}</span>
                  </div>
                  <div className="flex flex-col gap-0.5">
                    <span className="text-[#94A3B8]">Max DD</span>
                    <span className="font-bold text-[#EF4444]">{factor.drawdown}</span>
                  </div>
                </div>

                <p className="text-xs text-[#94A3B8] leading-relaxed line-clamp-2 mb-4">{factor.description}</p>

                {/* Action buttons */}
                <div className="flex items-center gap-2 pt-3 border-t border-[#475569]/30">
                  <button
                    onClick={(e) => { e.stopPropagation(); handleAddToStrategy(factor, e); }}
                    data-onboarding="add-to-strategy"
                    className="flex-1 bg-[#3B82F6] hover:bg-[#2563EB] text-white text-[10px] font-bold py-2 px-3 rounded-lg transition flex items-center justify-center gap-1.5 outline-none"
                  >
                    <Plus className="w-3.5 h-3.5" /> ADD TO STRATEGY
                  </button>

                  <button
                    onClick={(e) => toggleFavorite(factor.id, factor.name, e)}
                    className={`p-2 rounded-lg border transition outline-none ${
                      isFav
                        ? 'bg-[#10B981]/15 border-[#10B981] text-[#10B981]'
                        : 'border-[#475569] text-[#94A3B8] hover:bg-[#334155] hover:text-[#F8FAFC]'
                    }`}
                  >
                    <Star className={`w-4 h-4 ${isFav ? 'fill-current' : ''}`} />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* DETAIL MODAL */}
      {previewFactorDetail && (
        <div className="fixed inset-0 bg-[#0F172A]/90 backdrop-blur-sm flex items-center justify-center p-4 z-50" onClick={() => setPreviewFactorDetail(null)}>
          <div className="bg-[#1E293B] border border-[#475569] rounded-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto p-6" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-start justify-between gap-4 mb-4 border-b border-[#475569] pb-4">
              <div className="flex flex-col gap-1">
                <h2 className="text-xl font-black text-white">{previewFactorDetail.name}</h2>
                <p className="text-xs text-[#94A3B8] font-mono">{previewFactorDetail.category} | {previewFactorDetail.difficulty} Difficulty</p>
              </div>
              <button onClick={() => setPreviewFactorDetail(null)} className="text-[#94A3B8] hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="grid grid-cols-2 gap-4 mb-4 font-mono text-xs">
              <div className="bg-[#0F172A] p-3 rounded-lg border border-[#475569]/30">
                <span className="text-[#94A3B8]" data-onboarding="win-rate">Win Rate</span>
                <p className="text-lg font-bold text-[#10B981]">{previewFactorDetail.win}</p>
              </div>
              <div className="bg-[#0F172A] p-3 rounded-lg border border-[#475569]/30">
                <span className="text-[#94A3B8]" data-onboarding="sharpe-ratio">Sharpe Ratio</span>
                <p className="text-lg font-bold text-[#3B82F6]">{previewFactorDetail.sharpe}</p>
              </div>
              <div className="bg-[#0F172A] p-3 rounded-lg border border-[#475569]/30">
                <span className="text-[#94A3B8]">Avg Return</span>
                <p className="text-lg font-bold text-white">{previewFactorDetail.avgReturn}</p>
              </div>
              <div className="bg-[#0F172A] p-3 rounded-lg border border-[#475569]/30">
                <span className="text-[#94A3B8]">Copied By</span>
                <p className="text-lg font-bold text-[#F59E0B]">{previewFactorDetail.copiedCount} users</p>
              </div>
            </div>

            <div className="mb-4">
              <h3 className="font-bold text-white text-sm mb-2">Formula Description</h3>
              <p className="text-xs text-[#94A3B8] leading-relaxed">{previewFactorDetail.description}</p>
            </div>

            <div className="mb-4">
              <h3 className="font-bold text-white text-sm mb-2 flex items-center gap-2">
                <Layers className="w-4 h-4" /> Python Implementation
              </h3>
              <pre className="bg-[#0F172A] border border-[#475569] p-4 rounded-lg overflow-x-auto text-xs text-[#F8FAFC] font-mono max-h-48">
                <code>{previewFactorDetail.codeSnippet}</code>
              </pre>
            </div>

            <button
              onClick={() => handleAddToStrategy(previewFactorDetail)}
              className="w-full bg-[#3B82F6] hover:bg-[#2563EB] text-white text-xs font-bold py-3 px-6 rounded-lg transition flex items-center justify-center gap-2"
            >
              <Check className="w-4 h-4" /> ADD TO STRATEGY
            </button>
          </div>
        </div>
      )}

    </div>
  );
}