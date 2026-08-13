'use client';

import React, { useState, useRef, useEffect } from 'react';
import { MessageCircle, X, Send, Minimize2, Maximize2 } from 'lucide-react';
import { getOrCreateDeviceId } from '@/lib/deviceFingerprint';

interface ChatMessage {
  id: number;
  message: string;
  direction: 'incoming' | 'outgoing';
  timestamp: string;
}

export default function ChatWidget() {
  const [isOpen, setIsOpen] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputText, setInputText] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

  const scrollToBottom = () => messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });

useEffect(() => {
    if (isOpen && messages.length === 0) fetchHistory();
    if (isOpen) scrollToBottom();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen, messages]);

  const fetchHistory = async () => {
    try {
      const deviceId = getOrCreateDeviceId();
      const res = await fetch(`${API_URL}/api/v1/chat/history?device_id=${deviceId}&limit=20`);
      if (res.ok) { const data = await res.json(); setMessages(data.messages || []); }
    } catch { /* ignore */ }
  };

  const sendMessage = async () => {
    if (!inputText.trim()) return;
    const id = Date.now();
    setMessages(prev => [...prev, { id, message: inputText, direction: 'outgoing', timestamp: new Date().toISOString() }]);
    setInputText('');
    setIsTyping(true);
    try {
      const deviceId = getOrCreateDeviceId();
      const res = await fetch(`${API_URL}/api/v1/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Device-ID': deviceId },
        body: JSON.stringify({ message: inputText }),
      });
      if (res.ok) {
        const data = await res.json();
        if (data.response) setMessages(prev => [...prev, { id: id + 1, message: data.response, direction: 'incoming', timestamp: new Date().toISOString() }]);
      }
    } catch { /* ignore */ }
    finally { setIsTyping(false); }
  };

  const handleKeyPress = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  };

  const formatTime = (ts: string) => new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  const formatMessage = (text: string) => text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>').replace(/\*(.*?)\*/g, '<em>$1</em>');

  if (!isOpen) {
    return (
      <button
        onClick={() => setIsOpen(true)}
        aria-label="Open chat"
        className="fixed bottom-20 right-4 z-50 flex h-14 w-14 items-center justify-center rounded-full bg-brand-600 text-white shadow-pop transition hover:bg-brand-700 active:scale-95 md:bottom-6 md:right-6"
      >
        <MessageCircle className="h-6 w-6" />
      </button>
    );
  }

  return (
    <div className="fixed bottom-24 right-4 z-50 flex w-[calc(100vw-2rem)] max-w-sm flex-col overflow-hidden rounded-card border border-slate-200 bg-white shadow-pop dark:border-slate-700 dark:bg-slate-900 md:bottom-24 md:right-6" style={{ height: isExpanded ? 'min(80dvh, 620px)' : 'min(60dvh, 460px)' }}>
      <div className="flex items-center justify-between border-b border-slate-100 bg-brand-600 px-4 py-3 text-white dark:border-slate-800">
        <div className="flex items-center gap-2">
          <span className="flex h-8 w-8 items-center justify-center rounded-full bg-white/20"><MessageCircle className="h-4 w-4" /></span>
          <div>
            <p className="text-sm font-semibold">Ask Jasper</p>
            <p className="text-[11px] opacity-80">AI is online</p>
          </div>
        </div>
        <div className="flex items-center gap-1">
          <button onClick={() => setIsExpanded(e => !e)} className="rounded-full p-1.5 hover:bg-white/15">{isExpanded ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}</button>
          <button onClick={() => setIsOpen(false)} className="rounded-full p-1.5 hover:bg-white/15"><X className="h-4 w-4" /></button>
        </div>
      </div>

      <div className="flex-1 space-y-3 overflow-y-auto p-4">
        {messages.length === 0 ? (
          <div className="py-8 text-center text-sm text-slate-400 dark:text-slate-500">
            <MessageCircle className="mx-auto mb-2 h-8 w-8 opacity-40" />
            <p>Ask me anything</p>
            <p className="mt-1 text-xs">About your trades, holdings, or markets</p>
          </div>
        ) : (
          messages.map(m => (
            <div key={m.id} className={`flex ${m.direction === 'outgoing' ? 'justify-end' : 'justify-start'}`}>
              <div className={`max-w-[80%] rounded-2xl px-3 py-2 text-sm ${
                m.direction === 'outgoing'
                  ? 'rounded-br-sm bg-brand-600 text-white'
                  : 'rounded-bl-sm bg-slate-100 text-slate-800 dark:bg-slate-800 dark:text-slate-100'
              }`}>
                <div className="text-xs" dangerouslySetInnerHTML={{ __html: formatMessage(m.message) }} />
                <div className="mt-1 text-[10px] opacity-70">{formatTime(m.timestamp)}</div>
              </div>
            </div>
          ))
        )}
        {isTyping && (
          <div className="flex justify-start">
            <div className="flex gap-1 rounded-2xl rounded-bl-sm bg-slate-100 px-4 py-2 dark:bg-slate-800">
              <span className="h-2 w-2 animate-bounce rounded-full bg-slate-400" style={{ animationDelay: '0ms' }} />
              <span className="h-2 w-2 animate-bounce rounded-full bg-slate-400" style={{ animationDelay: '150ms' }} />
              <span className="h-2 w-2 animate-bounce rounded-full bg-slate-400" style={{ animationDelay: '300ms' }} />
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className="border-t border-slate-100 p-3 dark:border-slate-800">
        <div className="flex items-end gap-2">
          <textarea
            value={inputText}
            onChange={e => setInputText(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="Ask about your portfolio..."
            rows={1}
            className="min-h-[40px] flex-1 resize-none rounded-control border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-brand-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100 dark:placeholder:text-slate-500"
          />
          <button onClick={sendMessage} disabled={!inputText.trim() || isTyping} className="rounded-control bg-brand-600 p-2.5 text-white transition hover:bg-brand-700 disabled:opacity-50">
            <Send className="h-5 w-5" />
          </button>
        </div>
      </div>
    </div>
  );
}
