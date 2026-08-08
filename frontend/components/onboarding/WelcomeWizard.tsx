'use client';

import React, { useState } from 'react';
import { Bot, Rocket, Radio, ListChecks } from 'lucide-react';
import { useOnboarding } from './OnboardingProvider';
import { Button } from '@/components/ui';

const STEPS = [
  { icon: <Bot className="h-6 w-6" />, title: 'Welcome! I am Jasper', body: 'Your AI trader. I watch markets 24\/7 and trade for you, explaining everything in plain English.' },
  { icon: <Rocket className="h-6 w-6" />, title: 'Tap Start', body: 'On Home, press Start and I will begin trading with practice money. Nothing real unless you say so.' },
  { icon: <Radio className="h-6 w-6" />, title: 'Connect sources', body: 'In Signals, connect Telegram, feeds or Reddit so I have more places to look for good ideas.' },
  { icon: <ListChecks className="h-6 w-6" />, title: 'Watch your Trades', body: 'Every move I make shows up on the Trades screen, with reasons you can actually understand.' },
] as const;

export default function WelcomeWizard() {
  const { showWelcome, setShowWelcome, completeOnboarding } = useOnboarding();
  const [step, setStep] = useState(0);

  const close = () => {
    try { localStorage.setItem('jasper_welcome_done', 'true'); } catch { /* ignore */ }
    setShowWelcome(false);
  };

  const finish = () => {
    close();
    completeOnboarding();
  };

  const isLast = step === STEPS.length - 1;
  const active = STEPS[step];

  if (!showWelcome) return null;

  return (
    <div className="fixed inset-0 z-[95] flex items-end justify-center bg-slate-950/50 backdrop-blur-sm md:items-center md:p-6">
      <div className="relative flex max-h-[92dvh] w-full max-w-md flex-col overflow-hidden rounded-t-card bg-white shadow-pop dark:bg-slate-900 md:rounded-card">
        <div className="relative overflow-hidden p-7">
          <div className="pointer-events-none absolute -right-10 -top-10 h-40 w-40 rounded-full bg-brand-100/70 blur-2xl dark:bg-brand-500/10" />
          <div className="relative">
            <span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-brand-600 text-white shadow-card">{active.icon}</span>
            <h2 className="mt-5 font-display text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-50">{active.title}</h2>
            <p className="mt-2 text-[15px] leading-relaxed text-slate-600 dark:text-slate-300">{active.body}</p>
          </div>
        </div>

        <div className="mt-auto space-y-4 p-7 pt-2">
          <div className="flex items-center justify-center gap-1.5">
            {STEPS.map((_, i) => (
              <span key={i} className={`h-1.5 rounded-full transition-all ${i === step ? 'w-6 bg-brand-600' : 'w-1.5 bg-slate-200 dark:bg-slate-700'}`} />
            ))}
          </div>

          <div className="flex items-center justify-between gap-2">
            <button onClick={close} className="rounded-full px-4 py-2 text-sm font-medium text-slate-400 transition hover:text-slate-700 dark:hover:text-slate-200">Skip</button>
            <div className="flex items-center gap-2">
              {!isLast && (
                <Button variant="secondary" onClick={() => setStep(s => s + 1)}>Next</Button>
              )}
              {isLast && <Button onClick={finish}>Let us go</Button>}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
