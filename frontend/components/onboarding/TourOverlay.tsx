'use client';

import React, { useId } from 'react';
import { useOnboarding } from './OnboardingProvider';

interface TourOverlayProps {
  children: React.ReactNode;
}

export default function TourOverlay({ children }: TourOverlayProps) {
  const { targetElement, isTourActive } = useOnboarding();
  const maskId = useId();

  if (!isTourActive || !targetElement?.rect) {
    return <>{children}</>;
  }

  const rect = targetElement.rect;
  const padding = 8;
  const spotlightWidth = rect.width + padding * 2;
  const spotlightHeight = rect.height + padding * 2;

  return (
    <div className="relative">
      {/* Children rendered normally */}
      {children}

      {/* Overlay layer */}
      <div
        className="fixed inset-0 z-[9998]"
        style={{ pointerEvents: 'none' }}
      >
        {/* Dark mask with spotlight cutout */}
        <svg className="absolute inset-0 w-full h-full">
          <defs>
            <mask id={maskId}>
              <rect width="100%" height="100%" fill="white" />
              <rect
                x={rect.left - padding}
                y={rect.top - padding}
                width={spotlightWidth}
                height={spotlightHeight}
                rx="8"
                ry="8"
                fill="black"
              />
            </mask>
          </defs>
          <rect
            width="100%"
            height="100%"
            fill="rgba(0, 0, 0, 0.7)"
            mask={`url(#${maskId})`}
          />
        </svg>

        {/* Highlight border around element */}
        <div
          className="absolute border-2 border-[#3B82F6] rounded-lg shadow-[0_0_20px_rgba(59,130,246,0.5)] pointer-events-auto"
          style={{
            top: rect.top - padding,
            left: rect.left - padding,
            width: rect.width + padding * 2,
            height: rect.height + padding * 2,
          }}
        />
      </div>
    </div>
  );
}