---
name: nextjs-upgrade-and-api-response-parsing
description: Upgrade Next.js dependencies and fix API response parsing mismatches between backend objects and frontend array expectations
source: auto-skill
extracted_at: '2026-06-11T12:51:12.305Z'
---

# Next.js Upgrade and API Response Parsing

## Overview

When upgrading Next.js and fixing build errors, you may encounter various issues including module resolution errors, API response mismatches where the backend returns objects but the frontend expects arrays, and platform-specific compatibility problems (particularly with Turbopack on Windows). This guide covers the upgrade process, critical parsing fixes, and Windows-specific troubleshooting.

## Part 1: Next.js Upgrade Process

### Step 1: Clean Install

When encountering `next-flight-client-entry-loader` or module resolution errors:

```bash
# Kill all Node processes first
taskkill /F /IM node.exe

# Clean everything
cd frontend
rmdir /s /q node_modules
del /q package-lock.json
npm cache clean --force

# Reinstall with legacy peer deps (avoids some conflicts)
npm install --legacy-peer-deps
```

**Why:** Native binaries (SWC, LightningCSS) can get locked or corrupted. A full clean install resolves this.

### Step 2: Verify Versions

After install, check what actually installed:

```bash
npm ls next react react-dom --depth=0
```

Expected output:
```
jasper-trades-frontend@0.1.0
+-- next@15.5.19
+-- react-dom@19.2.7
`-- react@19.2.7
```

### Step 3: Update package.json

Match your `package.json` to what installed:

```json
{
  "dependencies": {
    "next": "^15.5.19",
    "react": "^19.2.7",
    "react-dom": "^19.2.7"
  },
  "devDependencies": {
    "eslint-config-next": "^15.5.19"
  }
}
```

### Step 4: Build Test

```bash
npm run build
```

Expected: `✓ Compiled successfully in XXs`

## Part 2: API Response Parsing Fixes

### The Problem

Backend endpoints return **objects with array properties**, but frontend expects **direct arrays**:

**Backend Response (Python/FastAPI):**
```python
return {
    "holdings": [
        {"symbol": "AAPL", "quantity": 10, "avg_price": 150.00, ...},
        {"symbol": "BTC", "quantity": 0.5, "avg_price": 45000.00, ...}
    ]
}
```

**Frontend Expectation (Broken):**
```typescript
// ❌ This will fail - hData is an object, not an array
const hData = await holdingsRes.json();
holdingsData = hData || [];  // hData is { holdings: [...] }
holdingsData.reduce(...)  // ERROR: holdingsData.reduce is not a function
```

### Root Cause

FastAPI naturally wraps list responses in objects for consistency:
```python
@router.get("/{portfolio_id}/holdings")
async def get_holdings(...) -> dict:  # Returns dict, not list
    return {"holdings": [...]}
```

TypeScript `any[]` type annotation doesn't enforce the structure.

### The Fix: Array Detection Pattern

Use `Array.isArray()` to handle both formats (defensive programming):

```typescript
// ✅ Correct - handles both object and array responses
const hData = await holdingsRes.json();
holdingsData = Array.isArray(hData) 
  ? hData 
  : (hData?.holdings || []);
```

**Why this works:**
- If backend returns `[...]` directly → use it
- If backend returns `{ holdings: [...] }` → extract holdings
- If backend returns `{}` or `null` → empty array fallback

### Field Mapping

Backend may use different field names. Map them on consumption:

```typescript
const holdingsArray = Array.isArray(holdingsResult.data) 
  ? holdingsResult.data 
  : (holdingsResult.data.holdings || []);

setHoldings(holdingsArray.map((h: any) => ({
  symbol: h.symbol,
  name: h.name || h.symbol,
  type: h.type || 'Stock',
  shares: h.shares || h.quantity || 0,  // Backend uses 'quantity'
  avgPrice: h.avg_price || 0,
  currentPrice: h.current_price || h.avg_price || 0,
  pnlPercent: h.pnl_percent || h.unrealized_pnl_percent || 0  // Backend uses 'unrealized_pnl_percent'
})));
```

**Common Field Mismatches:**
| Frontend | Backend |
|----------|---------|
| `shares` | `quantity` |
| `pnlPercent` | `unrealized_pnl_percent` |
| `currentPrice` | `current_price` |
| `avgPrice` | `avg_price` |

## Part 3: Implementation Locations

### Location 1: PortfolioTab.tsx (Direct Fetch)

```typescript
// components/PortfolioTab.tsx
const fetchPortfolioData = async () => {
  const portfolioId = 1;
  const [holdingsRes, cashRes] = await Promise.all([
    fetch(`${API_URL}/api/v1/portfolio/${portfolioId}/holdings`),
    fetch(`${API_URL}/api/v1/portfolio/${portfolioId}/cash`),
  ]);

  let holdingsData: Holding[] = [];
  let cashData = cash;

  if (holdingsRes.ok) {
    const hData = await holdingsRes.json();
    // Backend returns { holdings: [...] } not direct array
    holdingsData = Array.isArray(hData) ? hData : (hData?.holdings || []);
    setHoldings(holdingsData);
  }

  if (cashRes.ok) {
    const cData = await cashRes.json();
    cashData = cData.amount || cash;
    setCash(cashData);
  }

  // Now safe to use .reduce()
  const hValue = holdingsData.reduce((sum, h) => sum + (h.shares * h.currentPrice), 0);
  // ... rest of calculations
};
```

### Location 2: page.tsx (Initial Load)

```typescript
// app/page.tsx
const fetchBackendData = useCallback(async () => {
  // ... other fetches

  // Fetch holdings
  const holdingsResult = await apiRequest<any>(`/api/v1/portfolio/${portfolioId}/holdings`);
  if (holdingsResult.data) {
    // Backend returns { holdings: [...] } not direct array
    const holdingsArray = Array.isArray(holdingsResult.data) 
      ? holdingsResult.data 
      : (holdingsResult.data.holdings || []);
    setHoldings(holdingsArray.map((h: any) => ({
      symbol: h.symbol,
      name: h.name || h.symbol,
      type: h.type || 'Stock',
      shares: h.shares || h.quantity || 0,
      avgPrice: h.avg_price || 0,
      currentPrice: h.current_price || h.avg_price || 0,
      pnlPercent: h.pnl_percent || h.unrealized_pnl_percent || 0
    })));
  }

  // ... rest of fetch
}, []);
```

### Location 3: page.tsx (Background Refresh)

```typescript
// app/page.tsx - Silent background refresh
const refreshBackendData = useCallback(async () => {
  try {
    // Update holdings prices silently
    const holdingsResult = await apiRequest<any>(`/api/v1/portfolio/${portfolioId}/holdings`);
    const holdingsResponse = holdingsResult.data;
    const holdingsData = Array.isArray(holdingsResponse) 
      ? holdingsResponse 
      : (holdingsResponse?.holdings || []);
    
    if (holdingsData.length > 0) {
      setHoldings(prev => {
        const newHoldings = holdingsData.map((h: any) => ({
          symbol: h.symbol,
          name: h.name || h.symbol,
          type: h.type || 'Stock',
          shares: h.shares || h.quantity || 0,
          avgPrice: h.avg_price || 0,
          currentPrice: h.current_price || h.avg_price || 0,
          pnlPercent: h.pnl_percent || h.unrealized_pnl_percent || 0
        }));
        const hasChanged = JSON.stringify(prev) !== JSON.stringify(newHoldings);
        return hasChanged ? newHoldings : prev;
      });
    }
  } catch (error) {
    // Silently ignore background refresh errors
    console.error('Background refresh failed:', error);
  }
}, []);
```

## Part 4: Error Symptoms and Diagnosis

### Symptom 1: Runtime TypeError
```
holdingsData.reduce is not a function
components\PortfolioTab.tsx (77:37)
```

**Diagnosis:** Trying to call array method on object.

**Fix:** Add `Array.isArray()` check before using array methods.

### Symptom 2: Empty UI Despite Backend Data
Chart shows "No Holdings Yet" but backend returns data.

**Diagnosis:** Frontend received `{ holdings: [...] }` but treated as truthy object, didn't extract array.

**Fix:** Extract `.holdings` property from response object.

### Symptom 3: TypeScript Compiles But Runtime Fails
No compile errors, but `reduce` or `map` fails at runtime.

**Diagnosis:** Type annotation `any[]` doesn't match actual response structure.

**Fix:** Change type to `any` and add runtime validation.

## Part 5: Prevention

### Backend: Add Response Type Hints

Make response shape explicit in FastAPI:

```python
class HoldingsResponse(BaseModel):
    holdings: list[PositionSchema]

@router.get("/{portfolio_id}/holdings", response_model=HoldingsResponse)
async def get_holdings(...) -> HoldingsResponse:
    return {"holdings": [...]}
```

### Frontend: Add Response Type Interfaces

```typescript
interface HoldingsApiResponse {
  holdings: Array<{
    symbol: string;
    quantity: number;
    avg_price: number;
    current_price: number;
    unrealized_pnl_percent: number;
  }>;
}

// Usage
const response = await fetch(url);
const data: HoldingsApiResponse = await response.json();
const holdingsArray = data.holdings; // Direct access
```

### API Client: Normalize Responses

Create a utility to normalize all array responses:

```typescript
// lib/api-client.ts
export function normalizeArrayResponse<T>(
  response: any,
  arrayKey?: string
): T[] {
  if (Array.isArray(response)) return response;
  if (response && typeof response === 'object') {
    const key = arrayKey || Object.keys(response)[0];
    return Array.isArray(response[key]) ? response[key] : [];
  }
  return [];
}

// Usage
const holdingsResult = await apiRequest('/portfolio/1/holdings');
const holdings = normalizeArrayResponse<Holding>(holdingsResult.data, 'holdings');
```

## Part 6: Platform-Specific Issues (Windows/Turbopack)

### Problem: Turbopack Incompatibility on Windows

When upgrading to Next.js 16+, you may encounter:
```
Error: Turbopack is not supported on this platform (win32/x64) because native bindings are not available.
Only WebAssembly (WASM) bindings were loaded, and Turbopack requires native bindings.

Attempted to load @next/swc-win32-x64-msvc, but an error occurred: 
\\?\E:\Projects\jasper-trades\frontend\node_modules\@next\swc-win32-x64-msvc\next-swc.win32-x64-msvc.node 
is not a valid Win32 application.
```

### Root Cause

Next.js 16 introduces Turbopack as the default bundler, which requires native platform-specific bindings. On Windows, these bindings may fail to load or be incompatible, causing the build to fall back to WASM bindings which don't support all Turbopack features.

### Solution 1: Use Webpack Bundler (Recommended for Windows)

Modify your Next.js configuration and scripts to use Webpack instead of Turbopack:

**next.config.js:**
```javascript
/** @type {import('next').NextConfig} */
const nextConfig = {
  // Static export for serving from FastAPI
  output: 'export',
  // Disable image optimization for static export
  images: {
    unoptimized: true,
  },
  // Fix Turbopack root issue (if present)
  turbopack: {
    root: __dirname,
  },
};

module.exports = nextConfig;
```

**package.json:**
```json
{
  "scripts": {
    "dev": "next dev --webpack",
    "build": "next build",
    "start": "next start",
    "lint": "eslint .",
    "clean": "next clean"
  }
}
```

### Solution 2: Fix Native Bindings (Alternative)

If you prefer to use Turbopack, try fixing the native bindings:

1. Remove problematic node modules:
   ```bash
   rmdir /s /q node_modules\@next\swc-win32-x64-msvc
   rmdir /s /q node_modules\@tailwindcss\oxide-win32-x64-msvc
   rmdir /s /q node_modules\lightningcss-win32-x64-msvc
   ```

2. Clear npm cache and reinstall:
   ```bash
   npm cache clean --force
   npm install
   ```

### Problem: Deprecated ESLint Configuration

Next.js 16 removes support for the `eslint` property in `next.config.js`.

### Error Message:
```
⚠️  ESLint configuration in next.config.js is no longer supported. 
See more info here: https://nextjs.org/docs/app/api-reference/cli/next#next-lint-options
⚠️  Invalid next.config.js options detected:
Unrecognized key(s) in object: 'eslint'
```

### Solution: Remove Deprecated Configuration

Remove the `eslint` property from `next.config.js`:

**Before:**
```javascript
const nextConfig = {
  eslint: {
    ignoreDuringBuilds: true,
  },
  // ... other config
};
```

**After:**
```javascript
const nextConfig = {
  // ... other config (eslint property removed)
};
```

To ignore ESLint during builds, use environment variables or modify your lint scripts instead.

### Problem: Workspace Root Detection Issues

### Error Message:
```
Next.js inferred your workspace root, but it may not be correct.
We couldn't find the Next.js package (next/package.json) from the project directory: 
E:\Projects\jasper-trades\frontend\app
To fix this, set turbopack.root in your Next.js config, or ensure the Next.js package 
is resolvable from this directory.
```

### Solution: Set Turbopack Root

Add the `turbopack.root` configuration to `next.config.js`:

```javascript
/** @type {import('next').NextConfig} */
const nextConfig = {
  // ... other config
  // Fix Turbopack root issue
  turbopack: {
    root: __dirname,
  },
};

module.exports = nextConfig;
```

## Checklist for Next.js Upgrades

- [ ] Kill all Node processes before reinstall
- [ ] Remove node_modules and package-lock.json
- [ ] Clean npm cache
- [ ] Install with `--legacy-peer-deps` if needed
- [ ] Verify installed versions with `npm ls`
- [ ] Update package.json to match installed versions
- [ ] Run clean build: `npm run build`
- [ ] Check for API response mismatches (objects vs arrays)
- [ ] Add `Array.isArray()` guards for all array responses
- [ ] Map backend field names to frontend conventions
- [ ] Test in both initial load and background refresh
- [ ] **Windows-specific:** Test with `--webpack` flag if Turbopack fails
- [ ] **Windows-specific:** Remove deprecated `eslint` config from next.config.js
- [ ] **Windows-specific:** Add `turbopack: { root: __dirname }` if needed

## Related Skills

- **[Recharts Resize Error Fix](./recharts-resize-error-fix.md)** - Fix chart dimension errors
- **[Portfolio Component Initialization State](./portfolio-component-initialization-state.md)** - Pass initialization flags to components
- **[Frontend Build Error Resolution](./frontend-build-error-resolution.md)** - General build troubleshooting
- **[Silent Refresh Architecture](./silent-refresh-architecture.md)** - Background data updates

## Files Modified

- `components/PortfolioTab.tsx` - Holdings parsing fix
- `app/page.tsx` - Holdings parsing in initial load and background refresh
- `package.json` - Next.js 16.2.9, React 19.2.7 versions, dev script with `--webpack`
- `next.config.js` - Removed eslint config, added turbopack.root