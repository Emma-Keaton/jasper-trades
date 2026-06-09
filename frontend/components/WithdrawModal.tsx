'use client';

import { useState } from 'react';
import { X, ArrowUpRight, Wallet, AlertCircle } from 'lucide-react';
import { Toast } from '@/app/page';

interface WithdrawModalProps {
  portfolioId: number;
  availableBalance: number;
  onClose: () => void;
  triggerToast: (type: Toast['type'], title: string, message: string) => void;
}

interface WithdrawalStats {
  total_withdrawn: number;
  pending_count: number;
  auto_payout_total: number;
}

export default function WithdrawModal({ 
  portfolioId, 
  availableBalance, 
  onClose,
  triggerToast 
}: WithdrawModalProps) {
  const [amount, setAmount] = useState<string>('');
  const [destinationType, setDestinationType] = useState<'crypto_wallet' | 'broker'>('crypto_wallet');
  const [walletAddress, setWalletAddress] = useState('');
  const [loading, setLoading] = useState(false);
  const [showStats, setShowStats] = useState(false);
  const [stats, setStats] = useState<WithdrawalStats | null>(null);

  const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
  const deviceId = typeof window !== 'undefined' ? localStorage.getItem('device_id') : null;

  const calculateFee = (amt: number) => {
    return amt * 0.001; // 0.1% fee
  };

  const calculateNet = (amt: number) => {
    return amt - calculateFee(amt);
  };

  const fetchStats = async () => {
    try {
      const res = await fetch(`${API_URL}/api/v1/withdrawal/stats?portfolio_id=${portfolioId}`, {
        headers: deviceId ? { 'X-Device-ID': deviceId } : {},
      });
      if (res.ok) {
        const data = await res.json();
        setStats(data.stats);
        setShowStats(true);
      }
    } catch (error) {
      console.error('Failed to fetch stats:', error);
    }
  };

  const handleWithdraw = async () => {
    const withdrawAmount = parseFloat(amount);
    
    if (isNaN(withdrawAmount) || withdrawAmount <= 0) {
      triggerToast('error', 'Invalid Amount', 'Please enter a valid amount greater than 0');
      return;
    }

    if (withdrawAmount > availableBalance) {
      triggerToast('error', 'Insufficient Balance', `Available: $${availableBalance.toFixed(2)}`);
      return;
    }

    if (destinationType === 'crypto_wallet' && !walletAddress) {
      triggerToast('error', 'Wallet Required', 'Please enter your crypto wallet address');
      return;
    }

    setLoading(true);

    try {
      // Validate wallet address if crypto
      if (destinationType === 'crypto_wallet' && walletAddress) {
        const validateRes = await fetch(`${API_URL}/api/v1/withdrawal/payout/validate-wallet`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ address: walletAddress, network: 'ethereum' }),
        });
        
        if (validateRes.ok) {
          const validateData = await validateRes.json();
          if (!validateData.valid) {
            triggerToast('error', 'Invalid Wallet', validateData.message);
            setLoading(false);
            return;
          }
        }
      }

      // Create withdrawal request
      const res = await fetch(`${API_URL}/api/v1/withdrawal/request`, {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          ...(deviceId ? { 'X-Device-ID': deviceId } : {}),
        },
        body: JSON.stringify({
          portfolio_id: portfolioId,
          amount: withdrawAmount,
          destination_type: destinationType,
          destination_address: destinationType === 'crypto_wallet' ? walletAddress : null,
        }),
      });

      if (!res.ok) {
        const error = await res.json();
        throw new Error(error.detail || 'Withdrawal failed');
      }

      const data = await res.json();
      
      triggerToast(
        'success',
        'Withdrawal Requested',
        `Amount: $${withdrawAmount.toFixed(2)} | Fee: $${calculateFee(withdrawAmount).toFixed(2)} | Net: $${calculateNet(withdrawAmount).toFixed(2)}`
      );

      onClose();
      
    } catch (error: any) {
      triggerToast('error', 'Withdrawal Failed', error.message);
    } finally {
      setLoading(false);
    }
  };

  const inputAmount = parseFloat(amount) || 0;
  const fee = calculateFee(inputAmount);
  const netAmount = calculateNet(inputAmount);

  return (
    <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="bg-[#1E293B] rounded-xl border border-[#475569] max-w-md w-full max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-[#475569]">
          <div className="flex items-center gap-2">
            <ArrowUpRight className="w-5 h-5 text-[#10B981]" />
            <h2 className="text-lg font-semibold text-white">Withdraw Funds</h2>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-white transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-4 space-y-4">
          {/* Available Balance */}
          <div className="bg-[#0F172A] rounded-lg p-3 border border-[#475569]">
            <p className="text-xs text-gray-400 mb-1">Available Balance</p>
            <p className="text-2xl font-bold text-white">${availableBalance.toFixed(2)}</p>
          </div>

          {/* Amount Input */}
          <div>
            <label className="block text-sm text-gray-300 mb-2">Withdrawal Amount</label>
            <div className="relative">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400">$</span>
              <input
                type="number"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                placeholder="0.00"
                min="0"
                max={availableBalance}
                step="0.01"
                className="w-full bg-[#0F172A] border border-[#475569] rounded-lg pl-8 pr-3 py-3 text-white text-lg focus:outline-none focus:border-[#10B981] transition-colors"
              />
              {inputAmount > 0 && (
                <button
                  onClick={() => setAmount(availableBalance.toString())}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-[#10B981] hover:text-[#059669] px-2 py-1 bg-[#10B981]/10 rounded"
                >
                  MAX
                </button>
              )}
            </div>
          </div>

          {/* Fee Breakdown */}
          {inputAmount > 0 && (
            <div className="bg-[#0F172A] rounded-lg p-3 border border-[#475569] space-y-2 text-sm">
              <div className="flex justify-between text-gray-400">
                <span>Amount:</span>
                <span className="text-white">${inputAmount.toFixed(2)}</span>
              </div>
              <div className="flex justify-between text-gray-400">
                <span>Fee (0.1%):</span>
                <span className="text-white">-${fee.toFixed(2)}</span>
              </div>
              <div className="flex justify-between font-semibold text-[#10B981] pt-2 border-t border-[#475569]">
                <span>You'll Receive:</span>
                <span>${netAmount.toFixed(2)}</span>
              </div>
            </div>
          )}

          {/* Destination Selection */}
          <div>
            <label className="block text-sm text-gray-300 mb-2">Destination</label>
            <select
              value={destinationType}
              onChange={(e) => setDestinationType(e.target.value as 'crypto_wallet' | 'broker')}
              className="w-full bg-[#0F172A] border border-[#475569] rounded-lg px-3 py-2.5 text-white focus:outline-none focus:border-[#10B981] transition-colors"
            >
              <option value="crypto_wallet">Crypto Wallet (USDC/USDT)</option>
              <option value="broker">Broker Account (Alpaca/Binance)</option>
            </select>
          </div>

          {/* Wallet Address Input */}
          {destinationType === 'crypto_wallet' && (
            <div>
              <label className="block text-sm text-gray-300 mb-2">Wallet Address</label>
              <input
                type="text"
                value={walletAddress}
                onChange={(e) => setWalletAddress(e.target.value)}
                placeholder="0x... (Ethereum) or Solana address"
                className="w-full bg-[#0F172A] border border-[#475569] rounded-lg px-3 py-2.5 text-white font-mono text-sm focus:outline-none focus:border-[#10B981] transition-colors"
              />
              <p className="text-xs text-gray-500 mt-1.5 flex items-center gap-1">
                <AlertCircle className="w-3 h-3" />
                Supports Ethereum (ERC-20) and Solana (SPL) addresses
              </p>
            </div>
          )}

          {/* Info Box */}
          <div className="bg-[#10B981]/10 border border-[#10B981]/30 rounded-lg p-3">
            <p className="text-xs text-[#10B981]">
              💡 <strong>Tip:</strong> Withdrawals are processed within 24 hours. 
              Crypto withdrawals are sent to your wallet address. Broker withdrawals 
              return to your original funding source.
            </p>
          </div>

          {/* View History Button */}
          <button
            onClick={fetchStats}
            className="w-full py-2 bg-[#1E293B] border border-[#475569] hover:bg-[#334155] text-white rounded-lg text-sm transition-colors"
          >
            {showStats ? 'Refresh Withdrawal History' : 'View Withdrawal History'}
          </button>

          {/* Stats Modal */}
          {showStats && stats && (
            <div className="bg-[#0F172A] rounded-lg p-4 border border-[#475569] space-y-3">
              <h3 className="text-sm font-semibold text-white mb-2">Withdrawal Statistics</h3>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-400">Total Withdrawn:</span>
                  <span className="text-white font-medium">${stats.total_withdrawn.toFixed(2)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">Auto-Payout Total:</span>
                  <span className="text-[#10B981] font-medium">${stats.auto_payout_total.toFixed(2)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">Pending:</span>
                  <span className="text-[#F59E0B] font-medium">{stats.pending_count}</span>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Footer Actions */}
        <div className="p-4 border-t border-[#475569] flex gap-3">
          <button
            onClick={onClose}
            className="flex-1 py-2.5 bg-[#1E293B] border border-[#475569] hover:bg-[#334155] text-white rounded-lg transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleWithdraw}
            disabled={loading || inputAmount <= 0 || inputAmount > availableBalance}
            className="flex-1 py-2.5 bg-[#10B981] hover:bg-[#059669] disabled:bg-[#10B981]/50 disabled:cursor-not-allowed text-white font-medium rounded-lg transition-colors"
          >
            {loading ? 'Processing...' : 'Withdraw'}
          </button>
        </div>
      </div>
    </div>
  );
}