'use client';

import { useState } from 'react';
import { MessageSquare, Check, Send, Hash } from 'lucide-react';
import { Toast } from '@/app/types';
import InfoModal, { SetupStep, ApiLink, BenefitItem } from './InfoModal';
import { getOrCreateDeviceId } from '@/lib/deviceFingerprint';
import { apiFetch } from '@/lib/api-client';

interface DiscordBotSettings {
  bot_token: string;
  guild_id: string;
  channel_id: string;
  enabled: boolean;
  chat_enabled: boolean;
}

interface DiscordBotSectionProps {
  discord: DiscordBotSettings;
  setDiscord: (settings: DiscordBotSettings) => void;
  triggerToast: (type: Toast['type'], title: string, message: string) => void;
}

import { API_URL } from '@/lib/constants';

export default function DiscordBotSection({ discord, setDiscord, triggerToast }: DiscordBotSectionProps) {
  const [showModal, setShowModal] = useState(false);
  const [showingToken, setShowingToken] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testMessageText, setTestMessageText] = useState('');

  const saveDiscordSettings = async () => {
    try {
      const deviceId = getOrCreateDeviceId();
      const res = await apiFetch(`${API_URL}/api/v1/settings/discord-bot`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Device-ID': deviceId,
        },
        body: JSON.stringify(discord),
      });

      if (res.ok) {
        triggerToast('success', 'Discord Bot Saved', 'Discord bot configuration saved');
      } else {
        triggerToast('error', 'Save Failed', 'Could not save Discord bot settings');
      }
    } catch {
      triggerToast('error', 'Save Failed', 'Could not save Discord bot settings');
    }
  };

  const startBot = async () => {
    if (!discord.bot_token) {
      triggerToast('warning', 'Missing Token', 'Enter your Discord bot token');
      return;
    }

    setTesting(true);
    try {
      const deviceId = getOrCreateDeviceId();
      const res = await apiFetch(`${API_URL}/api/v1/discord/start`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Device-ID': deviceId,
        },
      });

      if (res.ok) {
        triggerToast('success', 'Bot Started', 'Discord bot is now running');
        setDiscord({...discord, enabled: true});
      } else {
        triggerToast('error', 'Start Failed', 'Could not start Discord bot');
      }
    } catch {
      triggerToast('error', 'Start Failed', 'Could not start Discord bot');
    } finally {
      setTesting(false);
    }
  };

  const testMessage = async () => {
    if (!discord.enabled) {
      triggerToast('warning', 'Bot Not Running', 'Start the bot first');
      return;
    }

    setTesting(true);
    try {
      const deviceId = getOrCreateDeviceId();
      const res = await apiFetch(`${API_URL}/api/v1/discord/test`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Device-ID': deviceId,
        },
        body: JSON.stringify({ message: testMessageText || 'Test message from Jasper Trades' }),
      });

      if (res.ok) {
        triggerToast('success', 'Message Sent', 'Check your Discord channel');
      } else {
        triggerToast('error', 'Send Failed', 'Could not send message');
      }
    } catch {
      triggerToast('error', 'Send Failed', 'Could not send message');
    } finally {
      setTesting(false);
    }
  };

  return (
    <section className="bg-[#1E293B] rounded-lg p-4 border border-[#475569]">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <MessageSquare className="w-5 h-5 text-[#5865F2]" />
          <h2 className="text-lg font-semibold text-white">Discord Bot (Two-Way Chat)</h2>
        </div>
        {discord.enabled && (
          <span className="text-xs px-2 py-1 rounded bg-green-500/20 text-green-400">
            Running
          </span>
        )}
        <button onClick={() => setShowModal(true)} className="p-1 hover:bg-[#334155] rounded text-[#94A3B8]">
          <MessageSquare className="w-4 h-4" />
        </button>
      </div>

      <p className="text-xs text-gray-400 mb-4">
        Two-way Discord bot for trading commands and notifications.
        Unlike webhooks, the bot can receive commands and respond.
      </p>

      {discord.enabled && (
        <div className="mb-4 p-3 bg-green-500/10 border border-green-500/30 rounded-lg">
          <div className="flex items-center gap-2 mb-2">
            <Check className="w-4 h-4 text-green-500" />
            <span className="text-sm text-green-400 font-medium">Bot Connected</span>
          </div>
          <div className="grid grid-cols-2 gap-4 text-xs">
            <div>
              <span className="text-gray-400">Server:</span>
              <span className="text-white font-mono ml-2">{discord.guild_id}</span>
            </div>
            <div>
              <span className="text-gray-400">Channel:</span>
              <span className="text-white font-mono ml-2">{discord.channel_id}</span>
            </div>
          </div>
        </div>
      )}

      <div className="space-y-3">
        {/* Bot Token */}
        <div>
          <label className="block text-sm text-gray-300 mb-2 flex items-center gap-2">
            Bot Token
            <button
              type="button"
              onClick={() => setShowingToken(!showingToken)}
              className="text-xs text-[#5865F2] hover:underline"
            >
              {showingToken ? 'Hide' : 'Show'}
            </button>
          </label>
          <input
            type={showingToken ? 'text' : 'password'}
            value={discord.bot_token}
            onChange={(e) => setDiscord({...discord, bot_token: e.target.value})}
            placeholder="MTxxxxxxxxxxx..."
            className="w-full bg-[#0F172A] border border-[#475569] rounded-md px-3 py-2 text-white text-sm font-mono"
          />
          <p className="text-xs text-gray-500 mt-1">
            From Discord Developer Portal → Bot → Reset Token
          </p>
        </div>

        {/* Guild ID (Server ID) */}
        <div>
          <label htmlFor="discordGuildId" className="block text-sm text-gray-300 mb-2 flex items-center gap-2">
            Server ID (Guild ID)
          </label>
          <input
            id="discordGuildId"
            type="text"
            value={discord.guild_id}
            onChange={(e) => setDiscord({...discord, guild_id: e.target.value})}
            placeholder="123456789012345678"
            className="w-full bg-[#0F172A] border border-[#475569] rounded-md px-3 py-2 text-white text-sm font-mono"
          />
          <p className="text-xs text-gray-500 mt-1">
            Enable Developer Mode in Discord → Right-click server → Copy ID
          </p>
        </div>

        {/* Channel ID */}
        <div>
          <label htmlFor="discordChannelId" className="block text-sm text-gray-300 mb-2 flex items-center gap-2">
            <Hash className="w-3 h-3" />
            Channel ID
          </label>
          <input
            id="discordChannelId"
            type="text"
            value={discord.channel_id}
            onChange={(e) => setDiscord({...discord, channel_id: e.target.value})}
            placeholder="123456789012345678"
            className="w-full bg-[#0F172A] border border-[#475569] rounded-md px-3 py-2 text-white text-sm font-mono"
          />
          <p className="text-xs text-gray-500 mt-1">
            Right-click channel → Copy ID (Developer Mode required)
          </p>
        </div>

        {/* Enable Options */}
        <div className="space-y-2">
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={discord.enabled}
              onChange={(e) => setDiscord({...discord, enabled: e.target.checked})}
              className="w-4 h-4"
            />
            <span className="text-sm text-gray-300">Enable Discord bot</span>
          </label>
          <label className="flex items-center gap-2 cursor-pointer ml-6">
            <input
              type="checkbox"
              checked={discord.chat_enabled}
              onChange={(e) => setDiscord({...discord, chat_enabled: e.target.checked})}
              className="w-4 h-4"
              disabled={!discord.enabled}
            />
            <span className="text-sm text-gray-300">Enable two-way chat (AI responses)</span>
          </label>
        </div>

        {/* Test Message */}
        {discord.enabled && (
          <div className="border-t border-[#475569] pt-4 mt-4">
            <label htmlFor="discordTestMessage" className="block text-sm text-gray-300 mb-2">Send Test Message</label>
            <div className="flex gap-2">
              <input
                id="discordTestMessage"
                type="text"
                value={testMessageText}
                onChange={(e) => setTestMessageText(e.target.value)}
                placeholder="Hello from Jasper!"
                className="flex-1 bg-[#0F172A] border border-[#475569] rounded-md px-3 py-2 text-white text-sm"
              />
              <button
                onClick={testMessage}
                disabled={testing}
                className="px-4 py-2 bg-[#5865F2] hover:bg-[#4752C4] disabled:opacity-50 text-white rounded-md text-sm flex items-center gap-2"
              >
                {testing ? 'Sending...' : (
                  <>
                    <Send className="w-4 h-4" />
                    Send
                  </>
                )}
              </button>
            </div>
          </div>
        )}

        {/* Action Buttons */}
        <div className="flex gap-2">
          <button
            onClick={startBot}
            disabled={!discord.bot_token || testing}
            className="flex-1 py-2.5 bg-[#5865F2] hover:bg-[#4752C4] disabled:opacity-50 text-white font-medium rounded-lg transition-colors flex items-center justify-center gap-2"
          >
            {testing ? 'Starting...' : (
              <>
                <Check className="w-4 h-4" />
                {discord.enabled ? 'Restart Bot' : 'Start Bot'}
              </>
            )}
          </button>
          <button
            onClick={saveDiscordSettings}
            className="flex-1 py-2.5 bg-[#1E293B] border border-[#475569] hover:bg-[#334155] text-white font-medium rounded-lg transition-colors flex items-center justify-center gap-2"
          >
            <Check className="w-4 h-4" />
            Save Settings
          </button>
        </div>

        {/* Available Commands */}
        {discord.enabled && (
          <div className="mt-4 p-3 bg-[#5865F2]/10 border border-[#5865F2]/30 rounded-lg">
            <h4 className="text-sm font-semibold text-[#5865F2] mb-2 flex items-center gap-2">
              <Hash className="w-4 h-4" />
              Available Commands
            </h4>
            <div className="grid grid-cols-2 gap-2 text-xs text-gray-300">
              <div className="font-mono bg-[#0F172A] px-2 py-1 rounded">!portfolio</div>
              <div>- View portfolio summary</div>
              <div className="font-mono bg-[#0F172A] px-2 py-1 rounded">!trades</div>
              <div>- Recent trades</div>
              <div className="font-mono bg-[#0F172A] px-2 py-1 rounded">!help</div>
              <div>- Show commands</div>
              <div className="font-mono bg-[#0F172A] px-2 py-1 rounded">!status</div>
              <div>- Bot status</div>
            </div>
          </div>
        )}
      </div>

      {/* Setup Guide Modal */}
      <InfoModal title="Discord Bot - Complete Setup Guide" open={showModal} onClose={() => setShowModal(false)}>
        <div className="space-y-4">
          <div>
            <h4 className="font-semibold text-white mb-2">What is the Discord Bot?</h4>
            <p className="text-gray-300">
              Unlike webhooks (send-only), the Discord bot enables two-way communication.
              Users can type commands like `!portfolio` and get instant responses.
              The bot can also answer trading questions using Jasper&apos;s AI.
            </p>
          </div>

          <div>
            <h4 className="font-semibold text-white mb-2">FREE Forever</h4>
            <ul className="text-gray-300 space-y-1">
              <BenefitItem>Unlimited messages</BenefitItem>
              <BenefitItem>No rate limits</BenefitItem>
              <BenefitItem>Rich embed formatting</BenefitItem>
              <BenefitItem>Slash commands support</BenefitItem>
              <BenefitItem>Works in any Discord server</BenefitItem>
            </ul>
          </div>

          <div>
            <h4 className="font-semibold text-white mb-2">Step 1: Create Discord Application</h4>
            <div className="space-y-3">
              <SetupStep number={1}>
                Go to{' '}
                <ApiLink href="https://discord.com/developers/applications">Discord Developer Portal</ApiLink>
              </SetupStep>
              <SetupStep number={2}>
                Click &quot;New Application&quot; → Name it &quot;Jasper Trades&quot; → Create
              </SetupStep>
              <SetupStep number={3}>
                Go to &quot;Bot&quot; in left sidebar → Click &quot;Add Bot&quot; → &quot;Yes, do it!&quot;
              </SetupStep>
            </div>
          </div>

          <div>
            <h4 className="font-semibold text-white mb-2">Step 2: Get Bot Token</h4>
            <div className="space-y-3">
              <SetupStep number={1}>
                In Bot settings, find &quot;Token&quot; section
              </SetupStep>
              <SetupStep number={2}>
                Click &quot;Reset Bot Token&quot; (or &quot;Copy Token&quot; if already exists)
              </SetupStep>
              <SetupStep number={3}>
                <strong>IMPORTANT:</strong> You&apos;ll only see the token ONCE! Copy it immediately.
              </SetupStep>
              <SetupStep number={4}>
                Paste the token in the &quot;Bot Token&quot; field above
              </SetupStep>
            </div>
          </div>

          <div>
            <h4 className="font-semibold text-white mb-2">Step 3: Add Bot to Your Server</h4>
            <div className="space-y-3">
              <SetupStep number={1}>
                Go to &quot;OAuth2&quot; → &quot;URL Generator&quot;
              </SetupStep>
              <SetupStep number={2}>
                Select scopes: <code className="bg-[#0F172A] px-2 py-0.5 rounded text-xs">bot</code> and <code className="bg-[#0F172A] px-2 py-0.5 rounded text-xs">applications.commands</code>
              </SetupStep>
              <SetupStep number={3}>
                Under &quot;Bot Permissions&quot;, select:
                <ul className="mt-2 space-y-1 text-xs">
                  <li>• Send Messages</li>
                  <li>• Read Message History</li>
                  <li>• Embed Links</li>
                  <li>• Attach Files</li>
                </ul>
              </SetupStep>
              <SetupStep number={4}>
                Copy the generated URL at bottom of page
              </SetupStep>
              <SetupStep number={5}>
                Paste URL in browser → Select your server → Authorize
              </SetupStep>
            </div>
          </div>

          <div>
            <h4 className="font-semibold text-white mb-2">Step 4: Get Server & Channel IDs</h4>
            <div className="space-y-3">
              <SetupStep number={1}>
                In Discord: User Settings → Advanced → Enable &quot;Developer Mode&quot;
              </SetupStep>
              <SetupStep number={2}>
                <strong>Server ID:</strong> Right-click your server icon → &quot;Copy ID&quot;
              </SetupStep>
              <SetupStep number={3}>
                <strong>Channel ID:</strong> Right-click the channel → &quot;Copy ID&quot;
              </SetupStep>
              <SetupStep number={4}>
                Paste both IDs in the fields above
              </SetupStep>
            </div>
          </div>

          <div>
            <h4 className="font-semibold text-white mb-2">Step 5: Start the Bot</h4>
            <div className="space-y-3">
              <SetupStep number={1}>
                Make sure &quot;Enable Discord bot&quot; is checked
              </SetupStep>
              <SetupStep number={2}>
                Click &quot;Start Bot&quot; button
              </SetupStep>
              <SetupStep number={3}>
                Watch for &quot;Bot Connected&quot; status (green)
              </SetupStep>
              <SetupStep number={4}>
                Type <code className="bg-[#0F172A] px-2 py-0.5 rounded text-xs">!help</code> in your Discord channel to test
              </SetupStep>
            </div>
          </div>

          <div className="bg-[#5865F2]/10 border border-[#5865F2]/30 rounded-lg p-3">
            <h4 className="font-semibold text-[#5865F2] mb-2">Bot Commands:</h4>
            <div className="space-y-2 text-xs text-gray-300">
              <div><code className="bg-[#0F172A] px-2 py-0.5 rounded">!portfolio</code> - View portfolio summary</div>
              <div><code className="bg-[#0F172A] px-2 py-0.5 rounded">!trades</code> - Recent trades today</div>
              <div><code className="bg-[#0F172A] px-2 py-0.5 rounded">!help</code> - List all commands</div>
              <div><code className="bg-[#0F172A] px-2 py-0.5 rounded">!status</code> - Bot connection status</div>
              <div className="mt-2 text-gray-400">Plus AI chat: Ask questions like &quot;Should I buy AAPL?&quot;</div>
            </div>
          </div>

          <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-3">
            <h4 className="font-semibold text-red-400 mb-2">⚠️ Security Warning:</h4>
            <p className="text-gray-300 text-xs">
              Never share your bot token! It&apos;s like a password. If accidentally exposed, 
              immediately reset it in Discord Developer Portal.
            </p>
          </div>
        </div>
      </InfoModal>
    </section>
  );
}
