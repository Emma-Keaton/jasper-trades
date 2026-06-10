'use client';

import { useEffect, useState, useRef } from 'react';
import { X, ChevronLeft, ChevronRight, Check } from 'lucide-react';

interface TourTooltipProps {
  title: string;
  description: string;
  position: 'top' | 'bottom' | 'left' | 'right' | 'center';
  step: number;
  totalSteps: number;
  isLastStep: boolean;
  onNext: () => void;
  onBack: () => void;
  onClose: () => void;
  onSkip: () => void;
  targetElement?: Element | null;
}

export default function TourTooltip({
  title,
  description,
  position,
  step,
  totalSteps,
  isLastStep,
  onNext,
  onBack,
  onClose,
  onSkip,
  targetElement,
}: TourTooltipProps) {
  const [positionStyle, setPositionStyle] = useState<React.CSSProperties>({});
  const [arrowStyle, setArrowStyle] = useState<React.CSSProperties>({});
  const tooltipRef = useRef<HTMLDivElement>(null);

  // Calculate position based on target element and desired position
  useEffect(() => {
    if (!targetElement) return;

    const updatePosition = () => {
      const rect = targetElement.getBoundingClientRect();
      const tooltipRect = tooltipRef.current?.getBoundingClientRect();
      
      if (!tooltipRect) return;

      const gap = 12; // Space between element and tooltip
      let top = 0;
      let left = 0;

      switch (position) {
        case 'top':
          top = rect.top - tooltipRect.height - gap;
          left = rect.left + (rect.width - tooltipRect.width) / 2;
          break;
        case 'bottom':
          top = rect.bottom + gap;
          left = rect.left + (rect.width - tooltipRect.width) / 2;
          break;
        case 'left':
          top = rect.top + (rect.height - tooltipRect.height) / 2;
          left = rect.left - tooltipRect.width - gap;
          break;
        case 'right':
          top = rect.top + (rect.height - tooltipRect.height) / 2;
          left = rect.right + gap;
          break;
        case 'center':
          top = window.innerHeight / 2 - tooltipRect.height / 2;
          left = window.innerWidth / 2 - tooltipRect.width / 2;
          break;
      }

      // Ensure tooltip stays within viewport
      const padding = 16;
      if (top < padding) top = padding;
      if (left < padding) left = padding;
      if (top + tooltipRect.height > window.innerHeight - padding) {
        top = window.innerHeight - tooltipRect.height - padding;
      }
      if (left + tooltipRect.width > window.innerWidth - padding) {
        left = window.innerWidth - tooltipRect.width - padding;
      }

      setPositionStyle({
        top: `${top}px`,
        left: `${left}px`,
        position: 'fixed',
        zIndex: 9999,
      });

      // Calculate arrow position
      let arrowTop: string | undefined;
      let arrowLeft: string | undefined;
      let arrowRight: string | undefined;
      let arrowBottom: string | undefined;

      switch (position) {
        case 'top':
          arrowBottom = '100%';
          arrowLeft = '50%';
          break;
        case 'bottom':
          arrowTop = '100%';
          arrowLeft = '50%';
          break;
        case 'left':
          arrowRight = '100%';
          arrowTop = '50%';
          break;
        case 'right':
          arrowLeft = '100%';
          arrowTop = '50%';
          break;
      }

      setArrowStyle({
        position: 'absolute',
        width: '0',
        height: '0',
        border: '6px solid transparent',
        borderBottomColor: position === 'top' ? '#3B82F6' : undefined,
        borderTopColor: position === 'bottom' ? '#3B82F6' : undefined,
        borderRightColor: position === 'left' ? '#3B82F6' : undefined,
        borderLeftColor: position === 'right' ? '#3B82F6' : undefined,
        ...(arrowTop && { top: arrowTop }),
        ...(arrowBottom && { bottom: arrowBottom }),
        ...(arrowLeft && { left: arrowLeft }),
        ...(arrowRight && { arrowRight }),
        transform: 'translate(-50%, -50%)',
      });
    };

    updatePosition();
    
    // Recalculate on resize/scroll
    window.addEventListener('resize', updatePosition);
    window.addEventListener('scroll', updatePosition, true);
    
    return () => {
      window.removeEventListener('resize', updatePosition);
      window.removeEventListener('scroll', updatePosition, true);
    };
  }, [targetElement, position]);

  // Keyboard navigation
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'ArrowRight' || e.key === 'Enter') {
        onNext();
      } else if (e.key === 'ArrowLeft') {
        onBack();
      } else if (e.key === 'Escape') {
        onClose();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onNext, onBack, onClose]);

  return (
    <div
      ref={tooltipRef}
      className="w-[320px] md:w-[380px] bg-[#1E293B] border-2 border-[#3B82F6] rounded-lg shadow-2xl"
      style={positionStyle}
    >
      {/* Arrow pointer */}
      <div style={arrowStyle} />

      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-[#475569]">
        <div className="flex items-center gap-2">
          {/* Progress dots */}
          <div className="flex gap-1">
            {Array.from({ length: totalSteps }).map((_, i) => (
              <div
                key={i}
                className={`w-2 h-2 rounded-full transition-colors ${
                  i === step ? 'bg-[#3B82F6]' : 'bg-[#475569]'
                }`}
              />
            ))}
          </div>
        </div>
        <div className="flex items-center gap-2 text-xs text-[#94A3B8]">
          <span className="font-mono">{step + 1} / {totalSteps}</span>
          <button
            onClick={onClose}
            className="p-1 hover:bg-[#334155] rounded text-[#94A3B8] hover:text-white"
            title="Close (Esc)"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="p-4">
        <h3 className="text-white font-bold mb-2 text-lg">{title}</h3>
        <p className="text-[#94A3B8] text-sm leading-relaxed">
          {description}
        </p>
      </div>

      {/* Footer with navigation */}
      <div className="flex items-center justify-between p-4 border-t border-[#475569] bg-[#0F172A]/30">
        <button
          onClick={onSkip}
          className="text-[#94A3B8] hover:text-white text-sm hover:underline"
        >
          Skip Tour
        </button>

        <div className="flex items-center gap-2">
          <button
            onClick={onBack}
            disabled={step === 0}
            className="p-2 bg-[#1E293B] border border-[#475569] rounded hover:bg-[#334155] disabled:opacity-50 disabled:cursor-not-allowed"
            title="Back (←)"
          >
            <ChevronLeft className="w-5 h-5 text-white" />
          </button>

          {isLastStep ? (
            <button
              onClick={onNext}
              className="flex items-center gap-2 px-4 py-2 bg-[#10B981] hover:bg-[#059669] rounded-lg text-white font-medium"
              title="Complete (Enter)"
            >
              <Check className="w-5 h-5" />
              Done
            </button>
          ) : (
            <button
              onClick={onNext}
              className="flex items-center gap-2 px-4 py-2 bg-[#3B82F6] hover:bg-[#2563EB] rounded-lg text-white font-medium"
              title="Next (→)"
            >
              Next
              <ChevronRight className="w-5 h-5" />
            </button>
          )}
        </div>
      </div>

      {/* Progress bar */}
      <div className="h-1 bg-[#0F172A] rounded-t-lg overflow-hidden">
        <div
          className="h-full bg-[#3B82F6] transition-all duration-300"
          style={{ width: `${((step + 1) / totalSteps) * 100}%` }}
        />
      </div>
    </div>
  );
}