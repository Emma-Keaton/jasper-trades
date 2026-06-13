---
name: nextjs-15-frontend-fix
description: Fix Next.js frontend installation, build, and start commands by downgrading to Next.js 15 and removing standalone output for Vercel compatibility
source: auto-skill
extracted_at: '2026-06-13T14:48:08.166Z'
---

# Next.js 15 Frontend Fix

## Problem
Next.js 16.x has compatibility issues:
- `next start` doesn't work with `output: 'standalone'` configuration (requires `node .next/standalone/server.js` directly)
- Security vulnerabilities in early v16 versions
- Unnecessary complexity for Vercel deployment

## Solution
Downgrade to Next.js 15 (latest stable) and remove standalone output configuration.

## Steps

### 1. Update package.json
```json
{
  "dependencies": {
    "next": "15.5.19",
    "react": "^19.2.7",
    "react-dom": "^19.2.7"
  },
  "devDependencies": {
    "eslint-config-next": "15.5.19"
  },
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "eslint .",
    "clean": "next clean"
  }
}
```

**Key changes:**
- Remove `^` prefix for exact version matching
- Simplify scripts (no `TAILWIND_CSS_LIGHTNINGCSS_DISABLED` or `--webpack` flags needed for Tailwind v3)

### 2. Update next.config.js
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

**Remove:**
- `output: 'standalone'` (not needed for Vercel)
- `turbopack` config (uses webpack by default)

### 3. Clean install
```bash
cd frontend
rmdir /s /q node_modules .next
npm install --legacy-peer-deps
```

### 4. Verify all commands work
```bash
npm run dev      # Should start on localhost:3000
npm run build    # Should complete without errors
npm run start    # Should work with `next start`
npx next dev     # Should work
npx next start   # Should work
```

## Why Next.js 15 for Vercel?
- Vercel handles Next.js apps natively (no standalone needed)
- `next start` works out of the box
- Latest stable v15 has security patches
- Better compatibility with existing tooling

## Verification
- ✅ `npm run dev` - Development server starts without errors
- ✅ `npm run build` - Production build completes (ESLint warning is cosmetic)
- ✅ `npm run start` - Production server starts without standalone errors
- ✅ Vercel deployment - Works with zero config

## Notes
- ESLint warning during build (`Failed to patch ESLint`) is cosmetic and doesn't block builds
- Tailwind CSS v3.4.1 works correctly (no lightningcss issues on Windows)
- React 19 is compatible with Next.js 15