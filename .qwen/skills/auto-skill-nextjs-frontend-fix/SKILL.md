---
name: nextjs-frontend-fix
description: Fix Next.js frontend installation, build, and start commands by downgrading to Next.js 15 and removing standalone output for Vercel compatibility
source: auto-skill
extracted_at: '2026-06-13T14:36:44.262Z'
---

# Next.js Frontend Fix for Vercel + Render Deployment

## Problem
Next.js 16.x has compatibility issues:
- `next start` does not work with `output: 'standalone'` configuration
- Requires running `node .next/standalone/server.js` directly instead
- Security vulnerabilities in Next.js 15.3.5
- Unnecessary complexity for Vercel deployment

## Solution

### 1. Downgrade to Next.js 15 (latest stable)

```bash
cd frontend
npm install next@15 eslint-config-next@15 --save --legacy-peer-deps
```

**Why:** Next.js 15 has better compatibility with standard `next start` command and Vercel deployment.

### 2. Update package.json scripts

Remove Turbopack and Tailwind v4 workarounds:

```json
{
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "eslint .",
    "clean": "next clean"
  }
}
```

**Why:** 
- Tailwind CSS v3.4.1 doesn't need `TAILWIND_CSS_LIGHTNINGCSS_DISABLED` flag
- `--webpack` flag is unnecessary for standard Next.js 15 usage
- Clean scripts work for both local dev and production

### 3. Remove standalone output from next.config.js

For Vercel deployment, use default output (not standalone):

```javascript
/** @type {import('next').NextConfig} */
const nextConfig = {
  // Disable image optimization for static export
  images: {
    unoptimized: true,
  },
};

module.exports = nextConfig;
```

**Why:** 
- `output: 'standalone'` is for Docker/self-hosted deployments
- Vercel handles Next.js apps natively without standalone
- Removes the `next start` incompatibility error

### 4. Clean and rebuild

```bash
cd frontend
rd /s /q node_modules .next
npm install --legacy-peer-deps
npm run build
npm run start
```

## Verification Checklist

All commands should work without errors:

| Command | Expected Output |
|---------|----------------|
| `npm run dev` | Starts dev server on http://localhost:3000 |
| `npm run build` | Completes successfully, no TypeScript errors |
| `npm run start` | Starts production server on http://localhost:3000 |
| `npx next dev` | Starts dev server |
| `npx next start` | Starts production server |

## Deployment Notes

### Vercel (Frontend)
- No `output: 'standalone'` needed
- Vercel auto-detects Next.js and handles build/start
- Set environment variables in Vercel dashboard:
  - `NEXT_PUBLIC_API_URL`: https://your-backend.onrender.com
  - `NEXT_PUBLIC_WS_URL`: wss://your-backend.onrender.com

### Render (Backend)
- Backend serves API only
- Configure CORS to accept Vercel frontend domain
- No changes needed to frontend config for Render

## Common Issues

### "Cannot find module 'react-is'"
Install the missing dependency:
```bash
npm install react-is@^18.0.0 --save
```

### ESLint warnings during build
ESLint warnings don't fail the build. To fix:
```bash
npm run lint -- --fix
```

### Build fails with "Invalid or damaged lockfile"
Delete lockfile and reinstall:
```bash
del package-lock.json
rd /s /q node_modules
npm install --legacy-peer-deps
```

## Key Takeaways

1. **Use Next.js 15** for Vercel + Render split deployment (not Next.js 16)
2. **Remove `output: 'standalone'`** for Vercel compatibility
3. **Simplify scripts** - no need for Turbopack or Tailwind v4 workarounds with v3.4.1
4. **Clean installs matter** - always delete `.next` when switching Next.js versions