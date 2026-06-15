---
name: backend-frontend-endpoint-integration
description: Systematic approach to connecting all backend FastAPI endpoints to frontend Next.js components via panel-based UI integration
source: auto-skill
extracted_at: '2026-06-15T19:35:57.713Z'
---

# Backend-Frontend Endpoint Integration

This skill provides a systematic approach to connecting all backend API endpoints to frontend components, achieving 83% endpoint coverage (180/217 endpoints).

## Overview

When faced with connecting numerous backend endpoints to a frontend application:

1. **Audit all backend endpoints** using grep search
2. **Extend the API client** with typed methods
3. **Create reusable panel components** for feature groups
4. **Integrate via collapsible sections** within existing tabs
5. **Verify with build tests and endpoint sampling**

## Step-by-Step Procedure

### 1. Audit Backend Endpoints

Search for all route decorators to get a complete inventory:

```bash
# In backend directory
grep -r "@router\.\(get\|post\|put\|delete\)" app/api/v1/
```

Count endpoints by router file and identify which are already connected in frontend.

### 2. Extend API Client

Add typed methods following existing patterns:

```typescript
// frontend/lib/api-client.ts

// ============ NEW FEATURE APIs ============
export const featureAPI = {
  getStatus: () => apiRequest<any>('/api/v1/feature/status'),
  doAction: (data: any) =>
    apiRequest('/api/v1/feature/action', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
};
```

Key patterns:
- Group methods by feature/router
- Use `apiRequest<T>()` helper for consistency
- Include TypeScript generics for type safety
- Handle query params with `encodeURIComponent()`

### 3. Create Panel Components

Build self-contained UI panels for each feature group:

```typescript
// frontend/components/panels/FeaturePanel.tsx
'use client';

import React, { useState } from 'react';
import { featureAPI } from '@/lib/api-client';
import { CollapsibleSection } from '@/components/ui/CollapsibleSection';

export function FeaturePanel() {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);

  const handleAction = async () => {
    setLoading(true);
    const response = await featureAPI.doAction({ /* params */ });
    if (response.data) setResult(response.data);
    setLoading(false);
  };

  return (
    <div className="space-y-4">
      <button onClick={handleAction} disabled={loading}>
        {loading ? 'Loading...' : 'Run Action'}
      </button>
      {result && <pre>{JSON.stringify(result, null, 2)}</pre>}
    </div>
  );
}
```

### 4. Create CollapsibleSection Component

Reusable UI wrapper for panels:

```typescript
// frontend/components/ui/CollapsibleSection.tsx
export function CollapsibleSection({
  title,
  subtitle,
  defaultOpen = false,
  storageKey,
  children,
}: Props) {
  const [isOpen, setIsOpen] = useState(() => {
    if (storageKey) {
      const stored = localStorage.getItem(storageKey);
      return stored ? stored === 'true' : defaultOpen;
    }
    return defaultOpen;
  });

  useEffect(() => {
    if (storageKey) {
      localStorage.setItem(storageKey, String(isOpen));
    }
  }, [isOpen, storageKey]);

  return (
    <div className="border border-[#475569] rounded-xl overflow-hidden mb-4">
      <button onClick={() => setIsOpen(!isOpen)}>
        <h3>{title}</h3>
        {subtitle && <p>{subtitle}</p>}
        <ChevronDown className={isOpen ? 'rotate-180' : ''} />
      </button>
      {isOpen && <div>{children}</div>}
    </div>
  );
}
```

### 5. Integrate Panels into Tabs

Import and render panels within existing tab components:

```typescript
// frontend/components/ExistingTab.tsx
import { CollapsibleSection } from '@/components/ui/CollapsibleSection';
import { FeaturePanel } from '@/components/panels/FeaturePanel';

// In render:
<CollapsibleSection
  title="Feature Name"
  subtitle="Description"
  storageKey="tab-feature-open"
>
  <FeaturePanel />
</CollapsibleSection>
```

### 6. Register Backend Routes

Ensure all new routers are registered with correct prefixes:

```python
# backend/app/main.py
app.include_router(feature.router, prefix="/api/v1", tags=["feature"])
```

### 7. Test and Verify

```bash
# TypeScript check
cd frontend && npx tsc --noEmit

# Production build
cd frontend && npm run build

# Test backend endpoints
curl http://localhost:8000/api/v1/feature/status
```

## Key Design Decisions

### Panel-Based Integration
- **Why:** Avoids creating new pages/screens, keeps UI clean
- **How:** Collapsible sections within existing tabs
- **Benefit:** Users can expand only what they need

### LocalStorage Persistence
- **Why:** Remember user preferences across sessions
- **How:** `storageKey` prop in CollapsibleSection
- **Benefit:** Panels stay open/closed as user prefers

### API Client Extension Pattern
- **Why:** Consistent error handling, type safety
- **How:** Group by feature, use `apiRequest<T>()`
- **Benefit:** Easy to maintain, reusable across components

## Endpoint Coverage Goals

**Target:** 80%+ of user-facing endpoints connected

**Typical Distribution:**
- ✅ Connected: 83% (180/217)
- ⚠️ Omitted: 17% (37/217) - Internal backend-only

**Omitted Categories:**
- Webhook receivers (external callbacks)
- Heartbeat/internal task schedulers
- Cache refresh operations
- Debug/diagnostic endpoints
- Deprecated legacy endpoints

## Common Pitfalls

### 1. Missing Router Prefix
**Problem:** Endpoint returns 404
**Solution:** Ensure `main.py` registers with correct prefix:
```python
app.include_router(router, prefix="/api/v1", tags=["tag"])
```

### 2. Unclosed JSX Tags
**Problem:** Build fails with "JSX element has no closing tag"
**Solution:** Check table wrappers, especially after mobile responsiveness edits

### 3. API Method Signature Mismatch
**Problem:** TypeScript errors or runtime failures
**Solution:** Match backend schemas exactly, use `any` for complex types initially

## Verification Checklist

- [ ] All new API methods added to `api-client.ts`
- [ ] Panel components created with loading/error states
- [ ] CollapsibleSection component working
- [ ] Panels integrated into tabs with correct imports
- [ ] Backend routers registered with correct prefixes
- [ ] TypeScript compilation passes (`tsc --noEmit`)
- [ ] Production build succeeds (`npm run build`)
- [ ] Sample endpoints tested via curl
- [ ] No console errors in browser dev tools

## Example: Complete Integration Flow

**Backend:** Created 56 new methods across 8 routers
**Frontend:** Created 9 panel components + 1 UI component
**Integration:** 4 tabs updated with collapsible panels
**Result:** 83% endpoint coverage (180/217)

**Files Modified:**
- `frontend/lib/api-client.ts` (+220 lines)
- `frontend/components/ui/CollapsibleSection.tsx` (new)
- `frontend/components/panels/*Panel.tsx` (9 new files)
- `frontend/components/*Tab.tsx` (4 files updated)
- `backend/app/main.py` (route registration)

## When to Use This Skill

Use when:
- You have many backend endpoints needing frontend UI
- You want to avoid creating new pages/screens
- You prefer collapsible/expandable feature sections
- You need consistent API client patterns
- You want persistent user preferences

Avoid when:
- Endpoints are internal/backend-only
- Single endpoint needs simple button (use inline handler)
- Feature requires dedicated page/layout