'use client';

import { useEffect, useState } from 'react';
import TourTooltip from './TourTooltip';
import { useOnboarding, TourConfig } from '@/hooks/useOnboarding';
import { getTourByPage } from '@/lib/tourConfigs';

interface OnboardingTourProps {
  activePage: string;
  enabled?: boolean;
}

export default function OnboardingTour({ activePage, enabled = true }: OnboardingTourProps) {
  const {
    active,
    currentTour,
    currentStep,
    totalSteps,
    currentStepData,
    progress,
    startTour,
    nextStep,
    prevStep,
    skipTour,
    closeTour,
    isTourCompleted,
  } = useOnboarding();

  // Auto-start tour on first visit to page
  useEffect(() => {
    if (!enabled) return;

    const tour = getTourByPage(activePage);
    if (!tour) return;

    // Check if already completed or skipped
    const completed = isTourCompleted(tour.id);
    
    // Only auto-start if user hasn't seen this tour
    if (!completed && tour.autoStart && !active) {
      // Small delay to let page elements render
      const timer = setTimeout(() => {
        startTour(tour, 0);
      }, 500);
      return () => clearTimeout(timer);
    }
  }, [activePage, enabled, active, isTourCompleted, startTour]);

  // Find target element for current step
  const targetElement = active && currentStepData
    ? document.querySelector(currentStepData.targetElement)
    : null;

  // Highlight effect for target element
  useEffect(() => {
    if (!active || !targetElement) return;

    // Add highlight class to target
    targetElement.classList.add('tour-highlight');
    targetElement.scrollIntoView({ behavior: 'smooth', block: 'center' });

    return () => {
      targetElement.classList.remove('tour-highlight');
    };
  }, [active, targetElement]);

  if (!active || !currentTour || !currentStepData) return null;

  return (
    <>
      {/* Backdrop overlay */}
      <div
        className="fixed inset-0 bg-black/60 z-[9998] pointer-events-none"
        style={{
          backdropFilter: 'blur(2px)',
        }}
      />

      {/* Spotlight effect - cut out area around target */}
      {targetElement && active && (
        <SpotlightOverlay element={targetElement} />
      )}

      {/* Tooltip */}
      <TourTooltip
        title={currentStepData.title}
        description={currentStepData.description}
        position={currentStepData.position || 'bottom'}
        step={currentStep}
        totalSteps={totalSteps}
        isLastStep={currentStep === totalSteps - 1}
        onNext={nextStep}
        onBack={prevStep}
        onClose={closeTour}
        onSkip={skipTour}
        targetElement={targetElement}
      />

      {/* Keyboard hint */}
      <div className="fixed bottom-4 left-1/2 -translate-x-1/2 z-[10000] pointer-events-none">
        <div className="bg-[#1E293B]/90 border border-[#475569] rounded-full px-4 py-2 text-xs text-[#94A3B8] font-mono flex items-center gap-4">
          <span>← Back</span>
          <span className="text-[#475569]">|</span>
          <span>Next →</span>
          <span className="text-[#475569]">|</span>
          <span>Esc Close</span>
        </div>
      </div>
    </>
  );
}

// Spotlight overlay component
function SpotlightOverlay({ element }: { element: Element }) {
  const [rect, setRect] = useState<{ top: number; left: number; width: number; height: number } | null>(null);

  useEffect(() => {
    const updateRect = () => {
      const rect = element.getBoundingClientRect();
      setRect({
        top: rect.top,
        left: rect.left,
        width: rect.width,
        height: rect.height,
      });
    };

    updateRect();
    window.addEventListener('resize', updateRect);
    window.addEventListener('scroll', updateRect, true);

    return () => {
      window.removeEventListener('resize', updateRect);
      window.removeEventListener('scroll', updateRect, true);
    };
  }, [element]);

  if (!rect) return null;

  return (
    <div className="fixed inset-0 z-[9998] pointer-events-none">
      <svg width="100%" height="100%" className="absolute inset-0">
        <defs>
          <mask id="spotlight-mask">
            <rect width="100%" height="100%" fill="white" />
            <rect
              x={rect.left - 8}
              y={rect.top - 8}
              width={rect.width + 16}
              height={rect.height + 16}
              rx="8"
              fill="black"
            />
          </mask>
        </defs>
        <rect
          width="100%"
          height="100%"
          fill="rgba(0, 0, 0, 0.7)"
          mask="url(#spotlight-mask)"
        />
      </svg>
      {/* Highlight border around element */}
      <div
        className="absolute border-2 border-[#3B82F6] rounded-lg shadow-[0_0_20px_rgba(59,130,246,0.5)] pointer-events-auto"
        style={{
          top: rect.top - 8,
          left: rect.left - 8,
          width: rect.width + 16,
          height: rect.height + 16,
        }}
      />
    </div>
  );
}