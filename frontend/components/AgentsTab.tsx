'use client';

import React, { useState } from 'react';
import {
  Bot,
  Play,
  Square,
  Settings,
  Cpu,
  Check,
  RefreshCw
} from 'lucide-react';
import { AgentState, Toast } from '@/app/page';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

async function apiRequest<T>(endpoint: string, options?: RequestInit): Promise<{ data?: T; error?: string }> {
  try {
    const response = await fetch(`${API_URL}${endpoint}`, {
      ...options,
      headers: { 'Content-Type': 'application/json', ...options?.headers },
    });
    const data = await response.json();
    if (!response.ok) {
      return { error: data.detail || data.error || `HTTP ${response.status}` };
    }
    return { data };
  } catch (e) {
    return { error: e instanceof Error ? e.message : 'Network error' };
  }
}

interface AgentsTabProps {
  agents: AgentState[];
  setAgents: React.Dispatch<React.SetStateAction<AgentState[]>>;
  triggerToast: (type: Toast['type'], title: string, message: string) => void;
  loading?: boolean;
}

export default function AgentsTab({
  agents,
  setAgents,
  triggerToast,
  loading = false
}: AgentsTabProps) {
  const [selectedAgentId, setSelectedAgentId] = useState<string>('director');
  const [agentDetailsTab, setAgentDetailsTab] = useState<string>('configuration');

  if (loading) {
    return (
      <div className="flex flex-col gap-6">
        <div className="h-8 w-48 bg-gray-700 rounded animate-pulse mb-2" />
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="bg-[#1E293B] rounded-lg p-4 border border-[#475569] animate-pulse">
              <div className="h-6 w-6 bg-gray-700 rounded mb-2" />
              <div className="h-4 w-24 bg-gray-700 rounded mb-2" />
              <div className="h-3 w-16 bg-gray-700 rounded" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  const [selectedModel, setSelectedModel] = useState<string>('llama3');
  const [temperature, setTemperature] = useState<number>(0.7);
  const [maxTokens, setMaxTokens] = useState<number>(1024);
  const [timeout, setTimeoutVal] = useState<number>(5000);
  const [testingConnection, setTestingConnection] = useState<boolean>(false);

  const modelProfiles: { [key: string]: { name: string; speed: number; accuracy: number; cost: number; desc: string } } = {
    llama3: { name: "meta/llama-3.3-70b-instruct", speed: 4, accuracy: 4, cost: 3, desc: "Highly aligned robust task-completer with stellar standard logic." },
    deepseek: { name: "deepseek/deepseek-r1-distill-llama-70b", speed: 2, accuracy: 5, cost: 2, desc: "Chain-of-thought mathematical reasoning model. High latency but elite alpha signals accuracy." },
    nvidianim: { name: "nvidia/llama-3.1-nemotron-70b-instruct", speed: 5, accuracy: 4, cost: 4, desc: "NVIDIA-optimized low-latency inference suite customized for finance structures." },
    gpt4o: { name: "openai/gpt-4o-mini-micro", speed: 5, accuracy: 4, cost: 1, desc: "Extremely cost-efficient, ultra fast transactional payload specialist." }
  };

  const activeModel = modelProfiles[selectedModel] || modelProfiles.llama3;

  const toggleAgentStatus = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    const agent = agents.find(a => a.id === id);
    if (!agent) return;

    const action = agent.status === 'Running' ? 'stop' : 'start';

    try {
      const result = await apiRequest<any>(`/api/v1/agents/${id}/${action}`, { method: 'POST' });

      if (result.error) {
        triggerToast('error', 'Agent Control Failed', result.error);
        return;
      }

      setAgents(prev => prev.map(a => {
        if (a.id === id) {
          const nextStatus = agent.status === 'Running' ? 'Stopped' : 'Running';
          triggerToast(
            nextStatus === 'Running' ? 'success' : 'warning',
            `Agent ${a.name} ${nextStatus}`,
            `Agent ${a.name} ${nextStatus === 'Running' ? 'started' : 'stopped'} successfully.`
          );
          return { ...a, status: nextStatus };
        }
        return a;
      }));
    } catch (err) {
      triggerToast('error', 'Agent Control Failed', err instanceof Error ? err.message : 'Unknown error');
    }
  };

  const runConnectionTest = () => {
    setTestingConnection(true);
    setTimeout(() => {
      setTestingConnection(false);
      triggerToast('success', 'Model Handshake Succeeded', `Latency: 48ms | Secure endpoint authenticated with ${activeModel.name}.`);
    }, 1500);
  };

  const saveAgentConfig = () => {
    triggerToast('success', 'Configuration Committed', `Successfully deployed temperature, limits, & weights parameters to ${agents.find(a => a.id === selectedAgentId)?.name || 'Agent'} cluster.`);
  };

  const selectedAgent = agents.find(a => a.id === selectedAgentId) || agents[0];

  return (
    <div
      data-onboarding="agents-tour"
      className="flex flex-col gap-6 w-full"
    >

      {/* Tab Header */}
      <div>
        <h1 className="text-2xl font-black text-white tracking-tight font-sans">AI Workspace Agents</h1>
        <p className="text-sm text-[#94A3B8]">Deploy, inspect, and benchmark autonomous logic micro-engines.</p>
      </div>

      {/* AGENTS CARDS OVERVIEW */}
      <div
        data-onboarding="agent-director"
        className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4"
      >
        {agents.map((agent) => {
          const isRunning = agent.status === 'Running';
          const isSelected = selectedAgentId === agent.id;
          return (
            <div
              key={agent.id}
              onClick={() => setSelectedAgentId(agent.id)}
              className={`bg-[#1E293B] border p-4 rounded-xl flex flex-col justify-between gap-4 cursor-pointer hover:border-blue-400 focus:outline-none transition relative overflow-hidden h-36 ${
                isSelected ? 'border-[#3B82F6] ring-1 ring-[#3B82F6]/50' : 'border-[#475569]'
              }`}
            >
              <div className="flex items-start justify-between">
                <div className="flex flex-col">
                  <span className="font-bold text-sm text-[#F8FAFC]">{agent.name}</span>
                  <span className="text-[10px] font-mono text-[#94A3B8]">{agent.id === 'custom' ? 'Auxiliary Hub' : 'System Cluster'}</span>
                </div>
                <span className={`w-2.5 h-2.5 rounded-full ${
                  isRunning ? 'bg-[#10B981] animate-pulse' : 'bg-slate-500'
                }`} />
              </div>

              <div className="flex flex-col gap-1 text-[11px] font-mono text-[#94A3B8]">
                <div className="flex justify-between items-center">
                  <span>State:</span>
                  <span className={`font-semibold ${isRunning ? 'text-[#10B981]' : 'text-slate-400'}`}>
                    {agent.status}
                  </span>
                </div>
                <div className="flex justify-between items-center" data-onboarding="agent-latency">
                  <span>Avg Speed:</span>
                  <span className="text-[#F8FAFC]">{agent.latency}</span>
                </div>
              </div>

              <button
                role="button"
                aria-label={isRunning ? `Stop agent ${agent.name}` : `Start agent ${agent.name}`}
                onClick={(e) => toggleAgentStatus(agent.id, e)}
                data-onboarding="agent-status"
                className={`w-full py-1 rounded text-[10px] font-bold font-mono uppercase tracking-wider flex items-center justify-center gap-1.5 transition outline-none ${
                  isRunning
                    ? 'bg-red-500/10 text-red-400 border border-red-500/20 hover:bg-red-500/20'
                    : 'bg-[#10B981]/15 text-[#10B981] border border-[#10B981]/20 hover:bg-[#10B981]/25'
                }`}
              >
                {isRunning ? (
                  <>
                    <Square className="w-2.5 h-2.5 fill-current" />
                    STOP AGENT
                  </>
                ) : (
                  <>
                    <Play className="w-2.5 h-2.5 fill-current" />
                    DEPLOY AGENT
                  </>
                )}
              </button>
            </div>
          );
        })}
      </div>

      {/* TABBED AGENT DETAIL WORKSPACE */}
      <div className="bg-[#1E293B] border border-[#475569] rounded-xl overflow-hidden">
        <div className="bg-[#334155]/30 border-b border-[#475569] px-4 pt-3 flex items-center gap-1 overflow-x-auto">
          {[
            { id: 'configuration', label: 'Configuration' },
            { id: 'performance', label: 'Performance metrics' },
            { id: 'logs', label: 'Agent Logs' },
            { id: 'skills', label: 'Skills & Capabilities' }
          ].map(tab => (
            <button
              key={tab.id}
              onClick={() => setAgentDetailsTab(tab.id)}
              className={`text-xs font-bold px-4 py-2.5 -mb-px rounded-t-lg transition border-t-2 flex-shrink-0 outline-none ${
                agentDetailsTab === tab.id
                  ? 'bg-[#1E293B] border-[#3B82F6] text-[#3B82F6]'
                  : 'border-transparent text-[#94A3B8] hover:text-[#F8FAFC]'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <div className="p-6">
          <div className="flex flex-col gap-1 mb-6 border-b border-[#475569]/30 pb-4">
            <div className="flex items-center gap-2">
              <Bot className="w-5 h-5 text-[#3B82F6]" />
              <h2 className="text-lg font-black font-sans uppercase tracking-tight text-[#F8FAFC]">
                Currently Inspecting: {selectedAgent.name} Status Profile
              </h2>
            </div>
            <p className="text-xs text-[#94A3B8] font-mono">
              Cluster State: {selectedAgent.status === 'Running' ? 'Active Operational' : 'Inactive Offline'} | Response Benchmark: {selectedAgent.latency}
            </p>
          </div>

          {agentDetailsTab === 'configuration' && (
            <div className="grid grid-cols-1 md:grid-cols-12 gap-8">
              <div className="md:col-span-6 flex flex-col gap-6">
                <span className="font-mono text-[10px] uppercase font-bold tracking-wider text-[#94A3B8] border-b border-[#475569]/30 pb-1.5 flex items-center gap-1">
                  <Settings className="w-3.5 h-3.5" /> Engine Parameter Tuner
                </span>

                <div className="flex flex-col gap-2">
                  <div className="flex justify-between text-xs font-mono">
                    <span className="text-[#94A3B8]">Logical Generative Temperature</span>
                    <span className="font-bold text-[#3B82F6]">{temperature}</span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="1"
                    step="0.05"
                    value={temperature}
                    onChange={(e) => setTemperature(parseFloat(e.target.value))}
                    className="w-full h-1 bg-[#0F172A] rounded-lg appearance-none cursor-pointer accent-[#3B82F6]"
                  />
                  <span className="text-[10px] text-[#94A3B8]">Lower temp is precise & deterministic. Higher is imaginative & research-heavy.</span>
                </div>

                <div className="flex flex-col gap-2">
                  <div className="flex justify-between text-xs font-mono">
                    <span className="text-[#94A3B8]">Max Completion Limits</span>
                    <span className="font-bold text-[#3B82F6]">{maxTokens} tokens</span>
                  </div>
                  <input
                    type="range"
                    min="256"
                    max="4096"
                    step="128"
                    value={maxTokens}
                    onChange={(e) => setMaxTokens(parseInt(e.target.value))}
                    className="w-full h-1 bg-[#0F172A] rounded-lg appearance-none cursor-pointer accent-[#3B82F6]"
                  />
                  <span className="text-[10px] text-[#94A3B8]">Boundary limit on generated thoughts payload.</span>
                </div>

                <div className="flex flex-col gap-2">
                  <div className="flex justify-between text-xs font-mono">
                    <span className="text-[#94A3B8]">API Handshake Timeout Max</span>
                    <span className="font-bold text-[#3B82F6]">{timeout}ms</span>
                  </div>
                  <input
                    type="range"
                    min="1000"
                    max="15000"
                    step="5000"
                    value={timeout}
                    onChange={(e) => setTimeoutVal(parseInt(e.target.value))}
                    className="w-full h-1 bg-[#0F172A] rounded-lg appearance-none cursor-pointer accent-[#3B82F6]"
                  />
                  <span className="text-[10px] text-[#94A3B8]">Maximum milliseconds before terminating stale inference.</span>
                </div>

                <div className="flex items-center gap-3 pt-4">
                  <button
                    onClick={saveAgentConfig}
                    className="flex-1 bg-[#3B82F6] hover:bg-[#2563EB] text-white text-xs font-bold py-2.5 px-4 rounded-lg transition flex items-center justify-center gap-2 outline-none"
                  >
                    <Check className="w-4 h-4" /> COMMIT ACTIONS
                  </button>
                  <button
                    onClick={runConnectionTest}
                    disabled={testingConnection}
                    data-onboarding="test-connection"
                    className="border border-[#475569] hover:bg-[#334155] hover:text-[#F8FAFC] text-[#94A3B8] text-xs font-bold py-2.5 px-4 rounded-lg transition flex items-center justify-center gap-2 disabled:opacity-50 outline-none"
                  >
                    <RefreshCw className={`w-4 h-4 ${testingConnection ? 'animate-spin' : ''}`} />
                    {testingConnection ? 'TESTING...' : 'VALIDATE NODE'}
                  </button>
                </div>
              </div>

              <div
                data-onboarding="model-config"
                className="md:col-span-6 flex flex-col gap-6"
              >
                <span className="font-mono text-[10px] uppercase font-bold tracking-wider text-[#94A3B8] border-b border-[#475569]/30 pb-1.5 flex items-center gap-1">
                  <Cpu className="w-3.5 h-3.5" /> Backed Model Selection
                </span>

                <div className="flex flex-col gap-2">
                  <label className="text-xs text-[#94A3B8] font-mono leading-none">Inference Endpoint Engine</label>
                  <select
                    value={selectedModel}
                    onChange={(e) => {
                      setSelectedModel(e.target.value);
                      triggerToast('info', 'Model Selected', `Switched routing destination endpoint to ${modelProfiles[e.target.value].name}.`);
                    }}
                    className="w-full h-10 bg-[#0F172A] border border-[#475569] rounded-lg px-3 text-xs text-white font-mono focus:outline-none focus:border-[#3B82F6]"
                  >
                    <option value="llama3">Meta Llama 3.3 70B Instruct (General Strategy)</option>
                    <option value="deepseek">DeepSeek R1 Distill Llama 70B (Math & Analytics)</option>
                    <option value="nvidianim">NVIDIA Llama Nemotron 70B (Low Latency Finance)</option>
                    <option value="gpt4o">OpenAI GPT-4o Mini Micro (Cheap Execution)</option>
                  </select>
                </div>

                <div className="bg-[#0F172A] border border-[#475569] p-4 rounded-xl flex flex-col gap-4 font-mono text-xs text-[#94A3B8]">
                  <span className="font-bold text-white text-xs">{activeModel.name}</span>
                  <p className="text-[11px] leading-relaxed select-text">{activeModel.desc}</p>

                  <div className="flex flex-col gap-2 pt-2 border-t border-[#475569]/30">
                    <div className="flex justify-between items-center">
                      <span>Inference Speed Benchmark:</span>
                      <div className="flex items-center gap-1 font-bold" data-onboarding="agent-latency">
                        {Array.from({ length: 5 }).map((_, i) => (
                          <span key={i} className={`w-2.5 h-2.5 rounded-full ${i < activeModel.speed ? 'bg-[#3B82F6]' : 'bg-[#334155]'}`} />
                        ))}
                      </div>
                    </div>

                    <div className="flex justify-between items-center">
                      <span>Reasoning Quality:</span>
                      <div className="flex items-center gap-1 font-bold">
                        {Array.from({ length: 5 }).map((_, i) => (
                          <span key={i} className={`w-2.5 h-2.5 rounded-full ${i < activeModel.accuracy ? 'bg-[#10B981]' : 'bg-[#334155]'}`} />
                        ))}
                      </div>
                    </div>

                    <div className="flex justify-between items-center">
                      <span>Inference Overhead Rating:</span>
                      <div className="flex items-center gap-1 font-bold">
                        {Array.from({ length: 5 }).map((_, i) => (
                          <span key={i} className={`w-2.5 h-2.5 rounded-full ${i < activeModel.cost ? 'bg-[#F59E0B]' : 'bg-[#334155]'}`} />
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {agentDetailsTab === 'performance' && (
            <div
              data-onboarding="agent-status"
              className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 font-mono text-xs"
            >
              <div className="bg-[#0F172A] p-4 rounded-lg border border-[#475569]/30 flex flex-col gap-1.5 justify-center">
                <span className="text-[#94A3B8]">TOTAL SYNERGY DECISIONS</span>
                <span className="text-xl font-bold font-mono text-white">1,247 commands</span>
                <span className="text-[10px] text-[#10B981]">99.8% precision index</span>
              </div>
              <div className="bg-[#0F172A] p-4 rounded-lg border border-[#475569]/30 flex flex-col gap-1.5 justify-center">
                <span className="text-[#94A3B8]">AVERAGE LATENCY RESPONSE</span>
                <span className="text-xl font-bold font-mono text-white">{selectedAgent.latency}</span>
                <span className="text-[10px] text-[#3B82F6]">Secure roundtrip routing</span>
              </div>
              <div className="bg-[#0F172A] p-4 rounded-lg border border-[#475569]/30 flex flex-col gap-1.5 justify-center">
                <span className="text-[#94A3B8]">SYSTEM SUCCESS RATE</span>
                <span className="text-xl font-bold font-mono text-white">{selectedAgent.successRate}</span>
                <span className="text-[10px] text-[#10B981]">0 operational packet slips</span>
              </div>
              <div className="bg-[#0F172A] p-4 rounded-lg border border-[#475569]/30 flex flex-col gap-1.5 justify-center">
                <span className="text-[#94A3B8]">DEPLOYMENT UPTIME</span>
                <span className="text-xl font-bold font-mono text-[#F59E0B]">{selectedAgent.uptime}</span>
                <span className="text-[10px] text-slate-400">Continuous cloud thread</span>
              </div>
            </div>
          )}

          {agentDetailsTab === 'logs' && (
            <div className="bg-[#0F172A] border border-[#475569] rounded-lg p-4 font-mono text-xs text-[#94A3B8] h-48 overflow-y-auto flex flex-col gap-2">
              <p className="text-[#3B82F6]">[BOOTSTRAP CLIENT] Secured workspace environment handshakes initiated.</p>
              <p className="text-white">[INFO] Commenced thread scanning loop targeting sector index rates.</p>
              <p className="text-[#10B981]">[OK] Thread successfully established local connection loop. Client port mapped.</p>
              <p className="text-white">[TELEMETRY] Listening to Webhooks endpoints. Live price feeds running.</p>
              <p className="text-pink-400">[TRACE] Thread synchronized with central {selectedAgent.name} control registers.</p>
              <p className="text-[#94A3B8] animate-pulse">{'> '}Waiting for next automated payload transaction event...</p>
            </div>
          )}

          {agentDetailsTab === 'skills' && (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 font-mono text-xs">
              <div className="bg-[#0F172A] border border-[#475569]/30 p-4 rounded-lg flex flex-col gap-2">
                <span className="font-bold text-[#3B82F6] uppercase">Index Scan Analytics</span>
                <p className="text-[11px] text-[#94A3B8]">Scans index rates and applies sentiment analysis models.</p>
              </div>
              <div className="bg-[#0F172A] border border-[#475569]/30 p-4 rounded-lg flex flex-col gap-2">
                <span className="font-bold text-[#10B981] uppercase">Risk Hedging Limits</span>
                <p className="text-[11px] text-[#94A3B8]">Validates current limits margins and cancels order if exceeded.</p>
              </div>
              <div className="bg-[#0F172A] border border-[#475569]/30 p-4 rounded-lg flex flex-col gap-2">
                <span className="font-bold text-[#6366F1] uppercase">Order Split Execution</span>
                <p className="text-[11px] text-[#94A3B8]">Divides transactions to mitigate slippages across illiquid assets.</p>
              </div>
            </div>
          )}

        </div>
      </div>

    </div>
  );
}