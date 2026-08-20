'use client';

import { useState } from 'react';
import { Mail, Check, Send } from 'lucide-react';
import { Toast } from '@/app/types';
import InfoModal, { SetupStep, ApiLink, BenefitItem } from './InfoModal';
import { getOrCreateDeviceId } from '@/lib/deviceFingerprint';
import { apiFetch } from '@/lib/api-client';

interface SendGridSettings {
  api_key: string;
  from_email: string;
  enabled: boolean;
}

interface EmailServiceSectionProps {
  email: SendGridSettings;
  setEmail: (settings: SendGridSettings) => void;
  triggerToast: (type: Toast['type'], title: string, message: string) => void;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export default function EmailServiceSection({ email, setEmail, triggerToast }: EmailServiceSectionProps) {
  const [showModal, setShowModal] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testEmailAddress, setTestEmailAddress] = useState('');

  const saveSendGridSettings = async () => {
    try {
      const deviceId = getOrCreateDeviceId();
      const res = await apiFetch(`${API_URL}/api/v1/settings/email/sendgrid`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Device-ID': deviceId,
        },
        body: JSON.stringify(email),
      });

      if (res.ok) {
        triggerToast('success', 'Email Settings Saved', 'SendGrid configuration saved');
      } else {
        triggerToast('error', 'Save Failed', 'Could not save email settings');
      }
    } catch {
      triggerToast('error', 'Save Failed', 'Could not save email settings');
    }
  };

  const testEmail = async () => {
    if (!testEmailAddress || !email.enabled) {
      triggerToast('warning', 'Not Configured', 'Enable SendGrid and enter a test email');
      return;
    }

    setTesting(true);
    try {
      const deviceId = getOrCreateDeviceId();
      const res = await apiFetch(`${API_URL}/api/v1/notify/test-email`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Device-ID': deviceId,
        },
        body: JSON.stringify({ to: testEmailAddress, channel: 'email' }),
      });

      if (res.ok) {
        triggerToast('success', 'Test Email Sent', `Check ${testEmailAddress} for the test message`);
      } else {
        triggerToast('error', 'Test Failed', 'Could not send test email');
      }
    } catch {
      triggerToast('error', 'Test Failed', 'Could not send test email');
    } finally {
      setTesting(false);
    }
  };

  return (
    <section className="bg-[#1E293B] rounded-lg p-4 border border-[#475569]">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Mail className="w-5 h-5 text-[#0EA5E9]" />
          <h2 className="text-lg font-semibold text-white">Email Notifications (SendGrid)</h2>
        </div>
        {email.enabled && (
          <span className="text-xs px-2 py-1 rounded bg-green-500/20 text-green-400">
            Enabled
          </span>
        )}
        <button onClick={() => setShowModal(true)} className="p-1 hover:bg-[#334155] rounded text-[#94A3B8]">
          <Mail className="w-4 h-4" />
        </button>
      </div>

      <p className="text-xs text-gray-400 mb-4">
        Send professional email notifications for trades, alerts, and daily summaries.
        FREE: 100 emails/day forever.
      </p>

      <div className="space-y-3">
        {/* API Key */}
        <div>
          <label htmlFor="sendgridApiKey" className="block text-sm text-gray-300 mb-2">SendGrid API Key</label>
          <input
            id="sendgridApiKey"
            type="password"
            value={email.api_key}
            onChange={(e) => setEmail({...email, api_key: e.target.value})}
            placeholder="SG.xxxxxxxxxx..."
            className="w-full bg-[#0F172A] border border-[#475569] rounded-md px-3 py-2 text-white text-sm"
          />
        </div>

        {/* From Email */}
        <div>
          <label htmlFor="fromEmail" className="block text-sm text-gray-300 mb-2">From Email</label>
          <input
            id="fromEmail"
            type="email"
            value={email.from_email}
            onChange={(e) => setEmail({...email, from_email: e.target.value})}
            placeholder="your@email.com"
            className="w-full bg-[#0F172A] border border-[#475569] rounded-md px-3 py-2 text-white text-sm"
          />
          <p className="text-xs text-gray-500 mt-1">
            This email will appear as the sender
          </p>
        </div>

        {/* Enable Toggle */}
        <div className="flex items-center gap-2">
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={email.enabled}
              onChange={(e) => setEmail({...email, enabled: e.target.checked})}
              className="w-4 h-4"
            />
            <span className="text-sm text-gray-300">Enable email notifications</span>
          </label>
        </div>

        {/* Test Email */}
        {email.enabled && email.api_key && email.from_email && (
          <div className="border-t border-[#475569] pt-4 mt-4">
            <label htmlFor="testEmailAddress" className="block text-sm text-gray-300 mb-2">Test Email Address</label>
            <div className="flex gap-2">
              <input
                id="testEmailAddress"
                type="email"
                value={testEmailAddress}
                onChange={(e) => setTestEmailAddress(e.target.value)}
                placeholder="test@example.com"
                className="flex-1 bg-[#0F172A] border border-[#475569] rounded-md px-3 py-2 text-white text-sm"
              />
              <button
                onClick={testEmail}
                disabled={testing || !testEmailAddress}
                className="px-4 py-2 bg-[#0EA5E9] hover:bg-[#0284C7] disabled:opacity-50 text-white rounded-md text-sm flex items-center gap-2"
              >
                {testing ? 'Sending...' : (
                  <>
                    <Send className="w-4 h-4" />
                    Send Test
                  </>
                )}
              </button>
            </div>
          </div>
        )}

        {/* Save Button */}
        <button
          onClick={saveSendGridSettings}
          className="w-full py-2.5 bg-[#0EA5E9] hover:bg-[#0284C7] text-white font-medium rounded-lg transition-colors flex items-center justify-center gap-2"
        >
          <Check className="w-4 h-4" />
          Save Email Settings
        </button>

        {/* Info Box */}
        <div className="mt-3 p-3 bg-[#0EA5E9]/10 border border-[#0EA5E9]/30 rounded-lg">
          <p className="text-xs text-[#0EA5E9]">
            📧 <strong>Email Templates Included:</strong> Trade confirmations, price alerts, 
            daily P&L summaries, and weekly reports.
          </p>
        </div>
      </div>

      {/* Setup Guide Modal */}
      <InfoModal title="SendGrid Email - Setup Guide" open={showModal} onClose={() => setShowModal(false)}>
        <div className="space-y-4">
          <div>
            <h4 className="font-semibold text-white mb-2">What is SendGrid?</h4>
            <p className="text-gray-300">
              SendGrid is a professional email delivery service used by thousands of companies.
              Free tier includes 100 emails/day forever - perfect for trading notifications.
            </p>
          </div>

          <div>
            <h4 className="font-semibold text-white mb-2">FREE Tier</h4>
            <ul className="text-gray-300 space-y-1">
              <BenefitItem>100 emails/day forever (3,000/month)</BenefitItem>
              <BenefitItem>No credit card required</BenefitItem>
              <BenefitItem>Professional HTML templates included</BenefitItem>
              <BenefitItem>99%+ deliverability rate</BenefitItem>
            </ul>
          </div>

          <div>
            <h4 className="font-semibold text-white mb-2">How to Get Your API Key</h4>
            <div className="space-y-3">
              <SetupStep number={1}>
                Go to{' '}
                <ApiLink href="https://signup.sendgrid.com/">SendGrid Sign Up</ApiLink>
              </SetupStep>
              <SetupStep number={2}>
                Create free account (email + password, no credit card)
              </SetupStep>
              <SetupStep number={3}>
                Verify your email address (check inbox)
              </SetupStep>
              <SetupStep number={4}>
                Go to Settings → API Keys → Create API Key
              </SetupStep>
              <SetupStep number={5}>
                Name it &quot;Jasper Trades&quot;, give &quot;Full Access&quot; permission
              </SetupStep>
              <SetupStep number={6}>
                Copy the API key (starts with &quot;SG.&quot;) - you can only see it once!
              </SetupStep>
              <SetupStep number={7}>
                Paste the key above and enter your &quot;From Email&quot;
              </SetupStep>
            </div>
          </div>

          <div className="bg-blue-500/10 border border-blue-500/30 rounded-lg p-3">
            <h4 className="font-semibold text-blue-400 mb-2">What Emails You&apos;ll Get:</h4>
            <ul className="text-gray-300 space-y-1 text-xs">
              <li>• 📈 Trade Execution Confirmations</li>
              <li>• 🔔 Price Alert Notifications</li>
              <li>• 📊 Daily P&L Summary (every morning)</li>
              <li>• 📈 Weekly Performance Report</li>
              <li>• ⚠️ System Alerts (maintenance, issues)</li>
            </ul>
          </div>

          <div className="bg-amber-500/10 border border-amber-500/30 rounded-lg p-3">
            <h4 className="font-semibold text-amber-400 mb-2">Important:</h4>
            <p className="text-gray-300 text-xs">
              SendGrid requires email verification. After creating your account, verify your 
              &quot;From Email&quot; address in SendGrid&apos;s Sender Authentication settings, or emails 
              may not be delivered.
            </p>
          </div>
        </div>
      </InfoModal>
    </section>
  );
}
