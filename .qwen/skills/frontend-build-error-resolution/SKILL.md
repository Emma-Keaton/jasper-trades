---
name: frontend-build-error-resolution
description: Resolve Next.js build errors including duplicate variables, missing modules, and gitignore conflicts
source: auto-skill
extracted_at: '2026-06-09T16:30:00.000Z'
---

# Frontend Build Error Resolution

When building the Next.js frontend for production deployment, several common errors may occur. This guide covers systematic resolution steps.

## Common Build Errors and Fixes

### 1. Duplicate Variable Declarations

**Error:** `Module parse failed: Identifier 'X' has already been declared`

**Cause:** Same variable name used for both a useState hook and a function in the same scope.

**Example:**
```typescript
// ❌ WRONG - duplicate name
const [testMessage, setTestMessage] = useState('');
const testMessage = async () => { ... };

// ✅ CORRECT - rename the state variable
const [testMessageText, setTestMessageText] = useState('');
const testMessage = async () => { ... };
```

**Resolution:**
1. Identify the duplicate variable in the error message
2. Rename the useState variable (e.g., `testMessage` → `testMessageText`)
3. Update all references in JSX (value, onChange, body)
4. Rebuild to verify

**Files to check:**
- `components/settings/DiscordBotSection.tsx`
- `components/settings/EmailServiceSection.tsx`
- Any component with similarly named state and functions

### 2. Interface Property Typos

**Error:** `Object literal may only specify known properties, and 'X' does not exist in type 'Y'`

**Example:**
```typescript
// ❌ WRONG - typo in interface
interface ApiSettings {
  albaca_paper: boolean;  // typo
}

// ✅ CORRECT
interface ApiSettings {
  alpaca_paper: boolean;
}
```

**Resolution:**
1. Find the interface definition
2. Correct the typo to match the actual property name used throughout
3. Verify all components use the corrected name

### 3. Nullable Props in Components

**Error:** `Type 'number | null' is not assignable to type 'number'`

**Cause:** State initialized as nullable (`number | null`) but component expects non-nullable type.

**Resolution:**
```typescript
// ✅ Make the prop nullable in the interface
interface TradingCapsSectionProps {
  portfolioId: number | null;  // Allow null
  triggerToast: (type: Toast['type'], title: string, message: string) => void;
}

// ✅ Use fallback when consuming
export default function TradingCapsSection({ portfolioId, triggerToast }: TradingCapsSectionProps) {
  const [caps, setCaps] = useState<TradingCaps>({
    configured: false,
    portfolio_id: portfolioId || 1,  // Fallback to 1
    // ...
  });
  
  const fetchCaps = async () => {
    const res = await fetch(`${API_URL}/api/v1/trading-caps?portfolio_id=${portfolioId || 1}`);
    // ...
  };
}
```

### 4. Module Not Found - gitignore Conflict

**Error:** `Module not found: Can't resolve '../lib/websocket'`

**Cause:** The `lib/` folder is ignored by root `.gitignore` (common for Python projects) but needed for frontend.

**Resolution:**

**Option A: Force add the folder**
```bash
git add -f frontend/lib/
git commit -m "Add frontend lib folder"
```

**Option B: Update .gitignore**
```gitignore
# Keep Python lib ignored
lib/

# But track frontend lib
!frontend/lib/
!frontend/lib/*
```

**Verification:**
```bash
# Check if files are tracked
git ls-files frontend/lib/

# Should show:
# frontend/lib/websocket.ts
# frontend/lib/api-client.ts
# ...
```

### 5. Missing Exports

**Error:** `Module '"./api-client"' declares 'apiRequest' locally, but it is not exported`

**Resolution:**
```typescript
// ❌ WRONG - not exported
async function apiRequest<T>(...) { ... }

// ✅ CORRECT - exported
export async function apiRequest<T>(...) { ... }
```

## Build Verification Workflow

1. **Clean build cache:**
   ```bash
   rm -rf frontend/.next
   cd frontend && npm run build
   ```

2. **Check for type errors:**
   - Read the error message carefully
   - Note the file path and line number
   - Identify the specific type mismatch

3. **Fix and rebuild:**
   - Make the minimal change to fix the type
   - Run `npm run build` again
   - Repeat until no errors

4. **Verify all files are tracked:**
   ```bash
   git status
   git ls-files frontend/lib/
   ```

5. **Test local serving:**
   ```bash
   npm run build && npm run start
   # Visit http://localhost:3000
   ```

## Render Deployment Commands

For monorepo deployment (backend + frontend):

**Build Command:**
```bash
pip install -r backend/requirements.txt && cd frontend && npm ci && npm run build && cd .. && mkdir -p backend/static && cp -r frontend/.next/static backend/static/ 2>/dev/null || true && cp -r frontend/public backend/static/ 2>/dev/null || true
```

**Start Command:**
```bash
cd backend && python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

**Health Check Path:** `/api/v1/health`

## Key Lessons

1. **Always run a clean build** before deploying to catch errors early
2. **Check gitignore rules** - Python conventions may ignore frontend source folders
3. **Use force add (`-f`)** when gitignore blocks legitimate frontend files
4. **Name state variables descriptively** to avoid conflicts with function names
5. **Make props nullable** when initial state depends on async data fetching
6. **Export helper functions** that are used across multiple modules