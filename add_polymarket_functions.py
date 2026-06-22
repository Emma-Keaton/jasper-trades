# Add Polymarket functions to SettingsTab.tsx

with open('frontend/components/SettingsTab.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

# Find the insertion point (after loadTelegramPreferences, before savePayoutSettings)
insert_marker = '''  };

  const savePayoutSettings = async () => {'''

polymarket_functions = '''  };

  // ============ Polymarket Functions ============

  const checkPolymarketConnection = async () => {
    try {
      const deviceId = localStorage.getItem('device_id');
      const res = await fetch(`${API_URL}/api/v1/polymarket/connection/status`, {
        headers: { 'X-Device-ID': deviceId! },
      });
      const data = await res.json();

      if (data.connected) {
        setPolymarket(prev => ({
          ...prev,
          connected: true,
          wallet_address: data.wallet_address || '',
          balance: data.account_balance || 0,
          equity: data.account_equity || 0,
          ai_trading_enabled: data.ai_trading_enabled || false,
          copytrading_enabled: data.copytrading_enabled || false,
        }));
      } else {
        setPolymarket(prev => ({ ...prev, connected: false }));
      }
    } catch (error) {
      console.error('Failed to check Polymarket connection:', error);
    }
  };

  const connectPolymarket = async () => {
    if (!polymarket.api_key || !polymarket.api_secret) {
      setPolymarket(prev => ({ ...prev, message: 'Please enter both API key and secret', success: false }));
      return;
    }

    setPolymarket(prev => ({ ...prev, loading: true, message: '' }));

    try {
      const deviceId = localStorage.getItem('device_id');
      const res = await fetch(`${API_URL}/api/v1/polymarket/connection/configure`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Device-ID': deviceId!,
        },
        body: JSON.stringify({
          api_key: polymarket.api_key,
          api_secret: polymarket.api_secret,
        }),
      });

      const data = await res.json();

      if (res.ok && data.success) {
        setPolymarket(prev => ({
          ...prev,
          connected: true,
          wallet_address: data.wallet_address || '',
          loading: false,
          message: 'Polymarket account connected successfully!',
          success: true,
        }));
        refreshBalance();
      } else {
        setPolymarket(prev => ({
          ...prev,
          loading: false,
          message: data.detail || 'Failed to connect',
          success: false,
        }));
      }
    } catch (error) {
      setPolymarket(prev => ({
        ...prev,
        loading: false,
        message: 'Failed to connect Polymarket account',
        success: false,
      }));
    }
  };

  const disconnectPolymarket = async () => {
    if (!confirm('Are you sure you want to disconnect your Polymarket account?')) return;

    try {
      const deviceId = localStorage.getItem('device_id');
      const res = await fetch(`${API_URL}/api/v1/polymarket/connection`, {
        method: 'DELETE',
        headers: { 'X-Device-ID': deviceId! },
      });

      const data = await res.json();

      if (res.ok && data.success) {
        setPolymarket(prev => ({
          ...prev,
          connected: false,
          api_key: '',
          api_secret: '',
          wallet_address: '',
          balance: 0,
          equity: 0,
          message: 'Account disconnected',
          success: true,
          leaders: [],
        }));
        setShowLeaders(false);
      } else {
        setPolymarket(prev => ({
          ...prev,
          message: data.detail || 'Failed to disconnect',
          success: false,
        }));
      }
    } catch (error) {
      setPolymarket(prev => ({
        ...prev,
        message: 'Failed to disconnect',
        success: false,
      }));
    }
  };

  const refreshBalance = async () => {
    try {
      const deviceId = localStorage.getItem('device_id');
      const res = await fetch(`${API_URL}/api/v1/polymarket/account/balance`, {
        headers: { 'X-Device-ID': deviceId! },
      });

      if (res.ok) {
        const data = await res.json();
        setPolymarket(prev => ({
          ...prev,
          balance: data.balance || 0,
          equity: data.equity || 0,
        }));
      }
    } catch (error) {
      console.error('Failed to refresh balance:', error);
    }
  };

  const loadLeaders = async () => {
    try {
      const deviceId = localStorage.getItem('device_id');
      const res = await fetch(`${API_URL}/api/v1/polymarket/leaders?limit=10`, {
        headers: { 'X-Device-ID': deviceId! },
      });

      if (res.ok) {
        const data = await res.json();
        setPolymarket(prev => ({ ...prev, leaders: data.leaders || [] }));
        setShowLeaders(true);
      }
    } catch (error) {
      console.error('Failed to load leaders:', error);
    }
  };

  const followLeader = async (leaderId: string, leaderName: string) => {
    try {
      const deviceId = localStorage.getItem('device_id');
      const res = await fetch(`${API_URL}/api/v1/polymarket/leader/${leaderId}/follow`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Device-ID': deviceId!,
        },
        body: JSON.stringify({
          leader_name: leaderName,
          allocation_weight: 0.5,
          min_confidence: 0.7,
          max_copy_amount: 50.0,
        }),
      });

      const data = await res.json();

      if (res.ok && data.success) {
        setPolymarket(prev => ({
          ...prev,
          leaders: prev.leaders.map((l: any) =>
            l.leader_id === leaderId ? { ...l, is_following: true } : l
          ),
          message: `Now following ${leaderName}`,
          success: true,
        }));
      } else {
        setPolymarket(prev => ({
          ...prev,
          message: data.detail || 'Failed to follow leader',
          success: false,
        }));
      }
    } catch (error) {
      setPolymarket(prev => ({
        ...prev,
        message: 'Failed to follow leader',
        success: false,
      }));
    }
  };

  const savePayoutSettings = async () => {'''

# Replace
new_content = content.replace(insert_marker, polymarket_functions)

if new_content == content:
    print(f"❌ Insertion failed. Marker not found.")
    print(f"Looking for: {insert_marker[:100]}...")
else:
    with open('frontend/components/SettingsTab.tsx', 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("✅ Polymarket functions added successfully!")