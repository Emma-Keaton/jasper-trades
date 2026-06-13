---
name: broker-integration-removal
description: Systematic approach to removing broker integrations from a multi-broker trading platform
source: auto-skill
extracted_at: '2026-06-11T01:55:00.000Z'
---

# Broker Integration Removal Strategy

When removing a broker integration (e.g., Exness/MT5) from a multi-broker trading platform, follow this systematic approach to ensure complete removal without breaking existing functionality.

## Phase 1: Identify All Integration Points

**Before deleting anything**, search comprehensively:

```bash
# Search codebase for broker references
grep -r "exness\|mt5\|MetaTrader" --include="*.{py,ts,tsx,js,jsx}"
grep -r "exness\|mt5\|MetaTrader" --include="*.md"
```

Map all locations:
- API routers/endpoints
- Service classes
- Frontend components
- Database models/columns
- Documentation
- Test files

## Phase 2: Delete Core Files First

Remove the primary integration files:
1. **API router** - `backend/app/api/v1/exness.py`
2. **Backend services** - `mt5_service.py`, `exness_service.py`
3. **Frontend components** - `ExnessSection.tsx`

## Phase 3: Clean Dependent Services

### Withdrawal Service
If the broker was a payout destination:
- Remove destination type from `process_withdrawal()` routing logic
- Delete broker-specific execution methods (e.g., `_execute_forex_reinvestment()`, `_mt5_internal_transfer()`)
- Remove broker-specific payout methods (e.g., `_payout_forex()`, `_payout_split()`)
- Update docstrings to reflect remaining payout destinations only

### Payout Scheduler
- Update class docstrings to remove broker references
- Remove settings parameter if it was only used for broker credentials
- Update payout destination logic to only support remaining options

## Phase 4: Update Database Models

### Remove Columns from DeviceSettings
Delete broker-specific columns:
```python
# Remove these from DeviceSettings model
exness_login_id = Column(String, nullable=True)
exness_server = Column(String, nullable=True)
exness_password = Column(String, nullable=True)
exness_investor_password = Column(String, nullable=True)
exness_enabled = Column(Boolean, default=False)
```

### Remove BrokerAccount Model
If there's a dedicated broker account model tied to this broker, remove it entirely.

### Update Column Comments
Update Auto-Payout Configuration JSON structure comments to remove broker-specific options:
```python
# Before:
# "payout_destination": "crypto_wallet" | "forex_account" | "split"

# After:
# "payout_destination": "crypto_wallet"
```

## Phase 5: Update Migrations

Remove broker columns from the migration system:
```python
# Remove from expected_columns in _migrate_device_settings()
'exness_login_id': 'TEXT',
'exness_server': 'TEXT',
'exness_password': 'TEXT',
'exness_investor_password': 'TEXT',
'exness_enabled': 'BOOLEAN',
```

## Phase 6: Remove API Router Registration

In `backend/app/main.py`:
```python
# Remove import
from app.api.v1 import exness, trading_caps
# Becomes:
from app.api.v1 import trading_caps

# Remove router include
app.include_router(exness.router, prefix="/api/v1", tags=["exness"])
```

## Phase 7: Clean Frontend

### Settings Component
- Remove component import: `import ExnessSection from './ExnessSection'`
- Remove state: `const [exness, setExness] = useState<ExnessSettings>(...)`
- Remove component rendering: `<ExnessSection exness={exness} ... />`

### Onboarding Tours
Remove tour steps referencing the broker from tour configuration files.

### Update Comments
Change comments like:
```typescript
// Get portfolio ID for trading caps and Exness
// Becomes:
// Get portfolio ID for trading caps
```

## Phase 8: Update Documentation

### README.md
- Remove broker from feature tables
- Remove from tech stack list
- Remove installation/configuration instructions
- Update multi-broker integration descriptions

### Other Docs
- `DATABASE_SETUP.md` - Remove from column lists and troubleshooting
- `RENDER_DEPLOYMENT.md` - Remove from broker lists
- `ONBOARDING_PLAN.md` - Mark as removed or delete phase
- `WIREFRAMES.md` - Add note that section was removed

## Phase 9: Verify Cleanup

Run final verification:
```bash
# Should only find acceptable comments (e.g., example broker names)
grep -r "exness\|mt5\|MetaTrader" --include="*.{py,ts,tsx,js,jsx}"
```

Expected: Only comments like `# e.g., 'FxPro', 'IronFX', 'Exness'` should remain.

## Key Principles

1. **Delete files before editing** - Removing files first makes import errors obvious
2. **Search before each edit** - Find all references before making changes
3. **Update docs last** - Code changes inform what documentation needs updating
4. **Preserve unrelated functionality** - Don't break crypto payouts when removing forex
5. **Keep one acceptable reference** - A comment showing example broker names is OK for context

## Post-Removal Testing

After removal, verify:
- [ ] Backend starts without import errors
- [ ] Payout scheduler runs without broker-related errors
- [ ] Settings page loads without missing component errors
- [ ] Withdrawal service only shows supported destinations
- [ ] Database migrations run without trying to add removed columns