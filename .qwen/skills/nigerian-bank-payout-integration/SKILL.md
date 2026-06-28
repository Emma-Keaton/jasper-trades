---
name: nigerian-bank-payout-integration
description: Dynamic Nigerian bank list fetching and CBN NIP account validation for NGN payouts with auto-gateway detection
source: auto-skill
extracted_at: '2026-06-28T13:21:13.742Z'
---

# Nigerian Bank Payout Integration

## Overview

Implement production-ready Nigerian bank payouts with dynamic bank list fetching, mandatory CBN NIP account validation, and auto-gateway detection for flexible deployment configurations.

## Key Principles

**NEVER hardcode bank lists** - Nigerian banks are frequently renamed, licensed, or liquidated. Always fetch from payment gateway APIs at runtime.

**Always validate accounts** - CBN mandates NIP account resolution before any transfer to prevent wrong-account payouts.

**Flexibility for deployment** - API keys can be provided via environment variables (Render) or user settings (local dev/flexible deployment).

## Backend Implementation

### 1. Bank List API (`GET /api/v1/banks/nigeria`)

```python
# Fetches from Paystack/Flutterwave, falls back to cached list
@router.get("/nigeria")
async def get_nigerian_banks(gateway="paystack", device_id: str = Header(...)):
    api_key = load_gateway_key_from_settings(device_id)
    
    if not api_key:
        return get_cached_nigerian_banks()  # 38 banks
    
    banks = await fetch_paystack_banks(api_key)  # or flutterwave
    return {"banks": banks, "source": gateway}
```

**Cached banks include:**
- 18 Tier 1 traditional banks (GTBank, Access, Zenith, UBA, etc.)
- 11 digital banks/MFBs (OPay, PalmPay, Kuda, Moniepoint, etc.)
- 3 PSBs (MoMo, SmartCash, 9PSB)

Each bank has:
- `code`: Gateway/CBN code (e.g., `058` for GTBank)
- `nip_code`: NIBSS code for direct clearing (e.g., `000013`)
- `slug`: URL-friendly identifier

### 2. Account Validation API (`GET /api/v1/banks/nigeria/validate`)

```python
@router.get("/nigeria/validate")
async def validate_nigerian_account(
    account_number: str,  # 10-digit NUBAN
    bank_code: str,
    gateway="paystack",
    device_id: str = Header(...)
):
    # Validate format first
    if len(account_number) != 10 or not account_number.isdigit():
        return {"success": False, "message": "Invalid account number"}
    
    api_key = load_gateway_key_from_settings(device_id)
    if not api_key:
        return {"success": False, "message": "Configure Paystack key in Settings"}
    
    # Call Paystack/Flutterwave resolve API
    result = await validate_account_paystack(account_number, bank_code, api_key)
    return result
```

**Paystack Validation:**
```python
async def validate_account_paystack(account_number, bank_code, api_key):
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://api.paystack.co/bank/resolve",
            params={"account_number": account_number, "bank_code": bank_code},
            headers={"Authorization": f"Bearer {api_key}"}
        )
        data = response.json()
        if data["status"] is True:
            return {
                "success": True,
                "account_name": data["data"]["account_name"],
                "account_number": account_number
            }
```

## Frontend Implementation

### 1. Dynamic Bank Dropdown

```tsx
const [banks, setBanks] = useState<Bank[]>([]);

useEffect(() => {
  fetchBanks();
}, []);

const fetchBanks = async () => {
  const res = await fetch(`${API_URL}/api/v1/banks/nigeria`);
  const data = await res.json();
  setBanks(data.banks || []);
};

<select value={bankCode} onChange={handleChange}>
  <option value="">Select Bank</option>
  {banks.map(bank => (
    <option key={bank.code} value={bank.code}>
      {bank.name}
    </option>
  ))}
</select>
```

### 2. Account Validation Flow

```tsx
const [validatedAccountName, setValidatedAccountName] = useState<string | null>(null);

const validateAccount = async () => {
  if (accountNumber.length !== 10) {
    triggerToast('error', 'Invalid Format', 'Must be 10 digits');
    return;
  }
  
  setValidatingAccount(true);
  const res = await fetch(
    `${API_URL}/api/v1/banks/nigeria/validate?account_number=${accountNumber}&bank_code=${bankCode}`
  );
  const data = await res.json();
  
  if (data.success) {
    setValidatedAccountName(data.account_name);
    triggerToast('success', `Verified: ${data.account_name}`);
    setAccountName(data.account_name); // Auto-fill
  } else {
    triggerToast('error', data.message);
  }
};
```

### 3. UI States

```tsx
<button 
  onClick={validateAccount}
  disabled={validating || !accountNumber || !bankCode}
>
  {validating ? (
    <><Loader2 className="animate-spin" /> Verifying with CBN NIP...</>
  ) : (
    <><Check /> Verify Account Number</>
  )}
</button>

{validatedAccountName && (
  <div className="bg-green-500/10 border border-green-500/30 rounded p-3">
    <p className="text-green-500">
      ✓ Account Verified: {validatedAccountName}
    </p>
    <p className="text-xs text-gray-400">
      Confirm before saving
    </p>
  </div>
)}
```

## Settings Configuration

Users must add Paystack/Flutterwave API keys in Settings:

```
Settings → Payment Gateways → Paystack Secret Key
- Test key: sk_test_xxx
- Live key: sk_live_xxx
```

**Storage:** Encrypted JSON in `DeviceSettings.naira_bank_details`:
```json
{
  "paystack_api_key": "encrypted_sk_xxx",
  "naira_bank_enabled": true,
  "bank_account_number": "0123456789",
  "bank_code": "058",
  "account_name": "John Doe",
  "bank_name": "GTBank"
}
```

## Bank Code Reference

### Traditional Banks
| Bank | Gateway Code | NIP Code |
|------|-------------|----------|
| GTBank | `058` | `000013` |
| Access | `044` | `000014` |
| Zenith | `057` | `000015` |
| UBA | `033` | `000004` |
| First Bank | `011` | `000016` |

### Digital Banks
| Bank | Gateway Code | NIP Code |
|------|-------------|----------|
| OPay | `999992` | `100004` |
| PalmPay | `999991` | `100033` |
| Kuda | `50211` | `090267` |
| Moniepoint | `50515` | `090405` |

### PSBs
| Bank | Code |
|------|------|
| MoMo (MTN) | `120003` |
| SmartCash (Airtel) | `120004` |
| 9PSB (9mobile) | `120001` |

## Error Handling

### Common Errors

1. **"Invalid account number. Must be 10 digits."**
   - User entered wrong format
   - Validate before API call

2. **"Payment gateway API key not configured"**
   - User hasn't added Paystack/Flutterwave key
   - Show link to Settings

3. **"Could not resolve account"**
   - Bank downtime (temporary)
   - Invalid account number
   - Wrong bank code

4. **"Connection error"**
   - Network issue
   - Gateway API down
   - Retry after 30 seconds

### Graceful Degradation

```python
if not api_key:
    logger.warning("No API key, returning cached list")
    return get_cached_nigerian_banks()

if gateway_fetch_fails:
    logger.warning("Gateway failed, using cached")
    return get_cached_nigerian_banks()
```

## Testing

### Test Accounts (Paystack Sandbox)

```python
# Valid test account
account_number = "0123456789"
bank_code = "058"  # GTBank
# Returns: {"account_name": "John Doe"}

# Invalid account
account_number = "9999999999"
# Returns: {"status": false, "message": "Invalid account"}
```

### Frontend Test Flow

1. Go to Settings → Payout
2. Select "Nigerian Bank (NGN)"
3. Select bank from dropdown (should show 38+ banks)
4. Enter `0123456789` as account number
5. Click "Verify Account Number"
6. Should show "Account Verified: John Doe"

## Integration with Payout Flow

### Complete Payout Sequence

```
1. User selects "Nigerian Bank" destination
2. Enters 10-digit account number
3. Selects bank from dynamic dropdown
4. Clicks "Verify Account Number"
5. Backend validates via Paystack NIP
6. Frontend shows account holder name
7. User confirms name is correct
8. User enters/confirm account name
9. Saves payout configuration
10. On payout day: Auto-payout converts USD→NGN, transfers to bank
```

### Payout Execution (Future)

```python
async def _payout_naira_bank(portfolio_id, amount, bank_details):
    # 1. Convert USD to NGN at current forex rate
    ng_amount = await convert_usd_to_ngn(amount)
    
    # 2. Initiate transfer via Paystack/Flutterwave
    result = await paystack_transfer(
        recipient=bank_details["account_number"],
        bank_code=bank_details["bank_code"],
        amount=ng_amount,
        reason="Auto-payout from Jasper Trades"
    )
    
    # 3. Record transaction
    withdrawal.transaction_hash = result["transfer_code"]
    withdrawal.status = "completed"
```

## Compliance Notes

1. **CBN Mandate:** All Nigerian bank transfers must use NIP account resolution
2. **Fraud Prevention:** Always show verified name before confirming payout
3. **Audit Trail:** Store account validation timestamp and response
4. **Data Privacy:** Encrypt bank details, never log account numbers in plaintext

## Files Modified/Created

**Backend:**
- `app/api/v1/banks.py` - New file (bank list + validation)
- `app/services/withdrawal_service.py` - Added `_payout_naira_bank()` method
- `app/api/v1/banks.py` - Registered in `main.py`

**Frontend:**
- `frontend/components/PayoutSection.tsx` - Dynamic bank dropdown + validation UI
- Added `Bank` interface with code/nip_code fields

**Models:**
- `app/models.py` - `DeviceSettings.naira_bank_details` (encrypted JSON)

## Related Skills

- `trove-api-integration` - Trove API for USD/NGN conversion
- `auto-payout-withdrawal-system` - Base payout infrastructure
- `multi-broker-asset-routing` - Broker routing logic