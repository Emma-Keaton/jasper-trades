'use client';

import React, { useState } from 'react';
import { useOnboarding } from './OnboardingProvider';

interface InteractiveTooltipProps {
  position?: 'top' | 'bottom' | 'left' | 'right';
  targetRect?: DOMRect | null;
}

export default function InteractiveTooltip({ position = 'right', targetRect }: InteractiveTooltipProps) {
  const { currentStep, nextStep, prevStep, endTour, markTourComplete, currentStepIndex, totalSteps } = useOnboarding();
  const [showCancelConfirm, setShowCancelConfirm] = useState(false);

  if (!currentStep || !targetRect) {
    return null;
  }

  const { title, description, tip, action, skipAction } = currentStep;

  // Check if this is the last step
  const isLastStep = currentStepIndex === totalSteps;

  // Calculate tooltip position
  const getTooltipPosition = () => {
    const padding = 16;
    const tooltipWidth = 320;
    const tooltipHeight = 200;

    // Default positions
    let left = targetRect.left + targetRect.width + padding;
    let top = targetRect.top;

    // Adjust based on position prop
    switch (position) {
      case 'top':
        left = targetRect.left;
        top = targetRect.top - tooltipHeight - padding;
        break;
      case 'bottom':
        left = targetRect.left;
        top = targetRect.top + targetRect.height + padding;
        break;
      case 'left':
        left = targetRect.left - tooltipWidth - padding;
        top = targetRect.top;
        break;
      case 'right':
        left = targetRect.left + targetRect.width + padding;
        top = targetRect.top;
        break;
    }

    // Boundary checks - keep tooltip in viewport
    const viewportWidth = window.innerWidth;
    const viewportHeight = window.innerHeight;

    if (left < padding) {
      left = padding;
    }
    if (left + tooltipWidth > viewportWidth - padding) {
      left = viewportWidth - tooltipWidth - padding;
    }
    if (top < padding) {
      top = padding;
    }
    if (top + tooltipHeight > viewportHeight - padding) {
      top = viewportHeight - tooltipHeight - padding;
    }

    return { left, top };
  };

  const tooltipPos = getTooltipPosition();

  // Handle tour completion
  const handleFinishTour = () => {
    // Mark current tour as complete
    const tourKey = getTourKeyFromPath();
    markTourComplete(tourKey);
    endTour();
  };

  // Handle tour cancellation (ESC or X button)
  const handleCancelTour = () => {
    const tourKey = getTourKeyFromPath();
    // Mark as complete so it doesn't show again on reload
    markTourComplete(tourKey);
    endTour();
  };

  // Helper to get tour key from current path
  const getTourKeyFromPath = () => {
    const path = window.location.pathname.slice(1);
    const tourKey = path || 'dashboard';
    return tourKey;
  };

  // Show cancellation confirmation
  if (showCancelConfirm) {
    return (
      <div
        className="fixed z-[9999] bg-[#1E293B] border border-[#475569] rounded-xl p-4 max-w-sm shadow-2xl"
        style={{
          left: tooltipPos.left,
          top: tooltipPos.top,
          pointerEvents: 'auto',
          maxWidth: '320px',
        }}
      >
        <h3 className="text-lg font-bold text-white mb-2">Stop this tour?</h3>
        <p className="text-sm text-[#94A3B8] mb-4">
          You can restart it anytime from the Help menu.
        </p>
        <div className="flex gap-2">
          <button
            onClick={() => setShowCancelConfirm(false)}
            className="flex-1 px-4 py-2 rounded-lg border border-[#475569] text-[#94A3B8] hover:text-white hover:border-white transition font-medium text-sm"
          >
            Continue
          </button>
          <button
            onClick={handleCancelTour}
            className="flex-1 px-4 py-2 rounded-lg bg-[#EF4444] hover:bg-[#DC2626] text-white transition font-medium text-sm"
          >
            Stop Tour
          </button>
        </div>
      </div>
    );
  }

  return (
    <div
      className="fixed z-[9999] bg-[#1E293B] border border-[#475569] rounded-xl p-4 max-w-sm shadow-2xl"
      style={{
        left: tooltipPos.left,
        top: tooltipPos.top,
        pointerEvents: 'auto',
        maxWidth: '320px',
      }}
    >
      {/* Title */}
      <h3 className="text-lg font-bold text-white mb-2">{title}</h3>

      {/* Description */}
      <p className="text-sm text-[#94A3B8] mb-3">{description}</p>

      {/* Action button or skip hint */}
      {action && !skipAction ? (
        <button
          onClick={action.onClick}
          className="w-full bg-[#3B82F6] hover:bg-[#2563EB] text-white rounded-lg px-4 py-2 flex items-center justify-center gap-2 transition font-medium"
        >
          {action.icon}
          {action.label}
        </button>
      ) : skipAction ? (
        <div className="bg-[#334155] rounded-lg px-4 py-3 text-center text-[#94A3B8] text-sm">
          👉 Try this yourself, then click "Next" when ready
        </div>
      ) : null}

      {/* Pro tip */}
      {tip && (
        <div className="mt-3 pt-3 border-t border-[#475569]">
          <p className="text-xs text-[#60A5FA] font-mono">
            💡 Pro Tip: {tip}
          </p>
        </div>
      )}

      {/* Navigation */}
      <div className="flex items-center justify-between mt-4 pt-3 border-t border-[#475569]">
        <button
          onClick={prevStep}
          className="text-[#94A3B8] hover:text-white text-sm font-medium transition"
          disabled={currentStepIndex === 1}
        >
          ← Back
        </button>

        <div className="flex items-center gap-3">
          <button
            onClick={() => setShowCancelConfirm(true)}
            className="text-[#94A3B8] hover:text-white text-xs transition"
          >
            Stop
          </button>

          {isLastStep ? (
            <button
              onClick={handleFinishTour}
              className="bg-[#10B981] hover:bg-[#059669] text-white px-4 py-1.5 rounded-lg text-sm font-medium transition"
            >
              ✓ Finish Tour
            </button>
          ) : (
            <button
              onClick={nextStep}
              className="text-white font-medium hover:text-[#3B82F6] transition"
            >
              Next →
            </button>
          )}
        </div>
      </div>
    </div>
  );
}