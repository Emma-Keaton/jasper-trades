---
name: tailwind-css-v3-configuration-fix
description: Resolves Tailwind CSS v3.x compatibility issues by correcting PostCSS configuration and dependencies
source: auto-skill
extracted_at: '2026-06-11T14:31:51.034Z'
---

# Tailwind CSS v3 Configuration Fix

## Problem
The project had `@tailwindcss/postcss` (a Tailwind v4 plugin) installed as a devDependency while using Tailwind CSS v3.4.1. This caused incompatibility because:
- `@tailwindcss/postcss` belongs exclusively to Tailwind v4 and has no 3.x version
- Tailwind v3 uses the main `tailwindcss` package as the PostCSS plugin directly
- The mismatch led to build errors and Lightning CSS warnings

## Solution
1. **Remove incompatible dependency**: Uninstall `@tailwindcss/postcss`
2. **Correct dependency placement**: Ensure `postcss` and `autoprefixer` are devDependencies (not regular dependencies)
3. **Add proper PostCSS configuration**: Create `postcss.config.js` with Tailwind v3 plugin setup

## Step-by-Step Procedure

### 1. Update package.json
Remove `@tailwindcss/postcss` from devDependencies and move `postcss` and `autoprefixer` to devDependencies:

```json
{
  "devDependencies": {
    "@tailwindcss/typography": "^0.5.19",
    "@types/node": "^20",
    "@types/react": "^19",
    "@types/react-dom": "^19",
    "autoprefixer": "^10.4.21",
    "eslint": "9.39.1",
    "eslint-config-next": "^16.2.9",
    "firebase-tools": "^15.0.0",
    "postcss": "^8.5.6",
    "tailwindcss": "3.4.1",
    "tw-animate-css": "^1.4.0",
    "typescript": "5.9.3"
  }
}
```

Note: Also remove `postcss` and `autoprefixer` from regular dependencies if present.

### 2. Create postcss.config.js
In the frontend root directory, create `postcss.config.js`:

```javascript
// postcss.config.js
module.exports = {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  }
}
```

### 3. Reinstall dependencies
Run `npm install` in the frontend directory to apply the changes.

## Verification
After applying this fix:
- The Tailwind CSS v3.4.1 engine will work correctly with PostCSS
- Lightning CSS warnings should disappear
- Next.js build and dev commands should execute without CSS-related errors
- The `@tailwind` directives in your CSS files will be processed properly

## Notes
- This fix assumes you're using Tailwind CSS v3.x (specifically 3.4.1 in this project)
- If you need to upgrade to Tailwind v4 in the future, you would reverse this process:
  - Remove `tailwindcss`, `postcss`, `autoprefixer` as direct plugins
  - Add `@tailwindcss/postcss` and `@tailwindcss/oxide`
  - Change CSS imports from `@tailwind` to `@import "tailwindcss"`