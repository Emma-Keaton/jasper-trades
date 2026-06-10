"use client";

import { useMemo, useState, useRef } from 'react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import { Maximize, Minimize, Briefcase } from 'lucide-react';

interface EquityChartDataPoint {
  x: number | string;
  y: number;
}

interface EquityChartProps {
  data: EquityChartDataPoint[];
  timeframe?: '1D' | '1W' | '1M' | '3M' | '1Y' | 'ALL';
  onTimeframeChange?: (timeframe: string) => void;
}

export default function EquityChart({ data, timeframe = '1M', onTimeframeChange }: EquityChartProps) {
  const [isFullscreen, setIsFullscreen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const chartData = useMemo(() => {
    if (!data || data.length === 0) return [];

    return data.map((point, index) => ({
      index,
      value: point.y,
      label: typeof point.x === 'string' ? point.x :
        index === 0 ? 'Start' :
        index === data.length - 1 ? 'Now' : ''
    }));
  }, [data]);

  const maxValue = useMemo(() => {
    if (data.length === 0) return 0;
    return Math.max(...data.map(d => d.y));
  }, [data]);

  const minValue = useMemo(() => {
    if (data.length === 0) return 0;
    return Math.min(...data.map(d => d.y));
  }, [data]);

  const isPositive = data.length > 0 && data[data.length - 1].y >= data[0].y;

  const hasValidData = data && data.length > 0 && data.some(d => typeof d.y === 'number' && d.y > 0);

  // Guard: Don't render chart if no valid data - prevents Recharts "width/height -1" error
  if (!hasValidData) {
    return (
      <div
        ref={containerRef}
        className="relative w-full h-[350px] bg-[#1E293B] rounded-lg border border-[#475569] overflow-hidden flex items-center justify-center"
      >
        <div className="text-center text-gray-400">
          <div className="w-16 h-16 bg-gray-700 rounded-full flex items-center justify-center mx-auto mb-4">
            <Briefcase className="w-8 h-8 text-gray-500" />
          </div>
          <p className="text-sm mb-2">No portfolio data available yet</p>
          <p className="text-xs font-mono">Start trading to see your equity curve</p>
        </div>
      </div>
    );
  }

  const toggleFullscreen = async () => {
    if (!containerRef.current) return;
    if (!document.fullscreenElement) {
      try {
        await containerRef.current.requestFullscreen();
        setIsFullscreen(true);
      } catch (err) {
        console.error('Fullscreen error:', err);
      }
    } else {
      await document.exitFullscreen();
      setIsFullscreen(false);
    }
  };

  const CustomTooltip = ({ active, payload }: any) => {
    if (active && payload && payload.length) {
      const currentValue = payload[0].value;

      return (
        <div className="bg-[#0F172A] border border-[#475569] rounded-lg px-4 py-3 shadow-2xl">
          <p className="text-xs text-[#94A3B8] mb-1 font-mono">
            {payload[0].payload.label || `Point ${payload[0].payload.index + 1}`}
          </p>
          <p className="text-lg font-black text-white">
            ${currentValue.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </p>
        </div>
      );
    }
    return null;
  };

  // Y-axis domain: always start from 0, add 15% headroom at top
  const yAxisMin = 0;
  const yAxisMax = maxValue > 0 ? maxValue * 1.15 : 1000;

  // Guard: Don't render chart if no data - prevents Recharts "width/height -1" error
  if (!chartData || chartData.length === 0) {
    return (
      <div
        ref={containerRef}
        className="relative w-full h-[350px] bg-[#1E293B] rounded-lg border border-[#475569] overflow-hidden flex items-center justify-center"
      >
        <div className="text-center text-gray-400">
          <p className="text-sm mb-2">No portfolio data available yet</p>
          <p className="text-xs font-mono">Start trading to see your equity curve</p>
        </div>
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className={`relative w-full bg-[#1E293B] rounded-lg border border-[#475569] overflow-hidden ${isFullscreen ? 'h-full' : 'h-[350px]'}`}
    >
      {/* Header with timeframe and fullscreen */}
      <div className="absolute top-0 left-0 right-0 z-10 flex items-center justify-between p-3 bg-gradient-to-b from-[#1E293B] to-transparent pointer-events-none">
        {/* Timeframe buttons */}
        {onTimeframeChange && (
          <div className="flex items-center gap-1 bg-[#0F172A]/90 backdrop-blur-sm border border-[#475569] rounded-lg p-1 pointer-events-auto">
            {['1W', '1M', '3M', '1Y', 'ALL'].map((btn) => (
              <button
                key={btn}
                onClick={() => onTimeframeChange(btn)}
                className={`text-[10px] font-bold px-2 py-1 rounded transition outline-none ${
                  timeframe === btn
                    ? 'bg-[#3B82F6] text-white'
                    : 'text-[#94A3B8] hover:text-[#F8FAFC] hover:bg-[#334155]'
                }`}
              >
                {btn}
              </button>
            ))}
          </div>
        )}

        {/* Fullscreen button */}
        <button
          onClick={toggleFullscreen}
          className="p-2 bg-[#0F172A]/90 backdrop-blur-sm border border-[#475569] rounded-lg text-[#94A3B8] hover:text-white hover:bg-[#334155] transition pointer-events-auto"
          title={isFullscreen ? 'Exit Fullscreen' : 'Fullscreen'}
        >
          {isFullscreen ? <Minimize className="w-4 h-4" /> : <Maximize className="w-4 h-4" />}
        </button>
      </div>

      {/* Chart */}
      <div className="absolute inset-0 pt-16" style={{ height: 'calc(100% - 4rem)' }}>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart
            data={chartData}
            margin={{ top: 10, right: 20, bottom: 30, left: 60 }}
          >
            <defs>
              <linearGradient id="colorPositive" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#10B981" stopOpacity={0.4} />
                <stop offset="95%" stopColor="#10B981" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="colorNegative" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#EF4444" stopOpacity={0.4} />
                <stop offset="95%" stopColor="#EF4444" stopOpacity={0} />
              </linearGradient>
            </defs>

            <CartesianGrid
              strokeDasharray="3 3"
              vertical={false}
              stroke="#334155"
              opacity={0.5}
            />

            <XAxis
              dataKey="label"
              tick={{ fill: '#94A3B8', fontSize: 11, fontFamily: 'monospace' }}
              axisLine={{ stroke: '#475569' }}
              tickLine={{ stroke: '#475569' }}
              dy={5}
            />

            <YAxis
              domain={[yAxisMin, yAxisMax]}
              tick={{ fill: '#94A3B8', fontSize: 11, fontFamily: 'monospace' }}
              axisLine={{ stroke: '#475569' }}
              tickLine={{ stroke: '#475569' }}
              tickFormatter={(value) => {
                if (value >= 1000000) return `$${(value/1000000).toFixed(1)}M`;
                if (value >= 1000) return `$${(value/1000).toFixed(0)}K`;
                return `$${value}`;
              }}
              width={55}
            />

            <Tooltip content={<CustomTooltip />} />

            <Area
              type="monotone"
              dataKey="value"
              stroke={isPositive ? '#10B981' : '#EF4444'}
              strokeWidth={3}
              fill={isPositive ? 'url(#colorPositive)' : 'url(#colorNegative)'}
              animationDuration={1500}
              isAnimationActive={true}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* Footer stats */}
      <div className="absolute bottom-0 left-0 right-0 z-10 flex items-center justify-between px-4 py-2 bg-gradient-to-t from-[#1E293B] to-transparent pointer-events-none">
        <div className="flex items-center gap-4 text-[10px] font-mono">
          <div className="flex items-center gap-1.5">
            <span className="text-[#94A3B8]">Start:</span>
            <span className="font-bold text-white">
              {data.length > 0 ? 
                (data[0].y >= 1000000 ? `$${(data[0].y/1000000).toFixed(2)}M` :
                 data[0].y >= 1000 ? `$${(data[0].y/1000).toFixed(1)}K` :
                 `$${data[0].y.toFixed(0)}`) :
                '$0'
              }
            </span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="text-[#94A3B8]">Current:</span>
            <span className="font-bold text-[#3B82F6]">
              {data.length > 0 ?
                (data[data.length - 1].y >= 1000000 ? `$${(data[data.length - 1].y/1000000).toFixed(2)}M` :
                 data[data.length - 1].y >= 1000 ? `$${(data[data.length - 1].y/1000).toFixed(1)}K` :
                 `$${data[data.length - 1].y.toFixed(0)}`) :
                '$0'
              }
            </span>
          </div>
        </div>
        <div className="text-[10px] font-mono text-[#94A3B8]">
          Interactive chart
        </div>
      </div>
    </div>
  );
}