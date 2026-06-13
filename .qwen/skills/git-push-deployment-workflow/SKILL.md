---
name: git-push-deployment-workflow
description: Proper Git workflow for deploying to Vercel and Render via GitHub
source: auto-skill
extracted_at: '2026-06-11T00:00:13.832Z'
---

# Git Push Deployment Workflow for Vercel + Render

## Overview

When deploying updates to a split architecture (frontend on Vercel, backend on Render), both services auto-deploy from the same GitHub repository. Use this workflow to ensure changes are properly synced and deployed.

## The Correct Workflow

### Step 1: Stage and Commit Local Changes

```bash
git add .
git commit -m "feat: description of changes"
```

**Why:** Ensures all your local changes are committed before syncing with remote.

### Step 2: Pull Latest from Remote

```bash
git pull origin main
```

**Why:** 
- Syncs your local branch with what's currently deployed
- Prevents conflicts if Vercel/Render made any automated commits
- Ensures you're building on the latest code base

**Common Issue:** If you skip this step and someone/something else pushed to main, your push will be rejected or overwrite their changes.

### Step 3: Push to GitHub

```bash
git push origin main
```

**Why:** Triggers auto-deployment on both Vercel and Render.

### Step 4: Monitor Auto-Deployment

Both services detect the push and deploy automatically:

| Service | Build Time | What Happens |
|---------|------------|--------------|
| **Vercel** | 2-5 minutes | Detects push → builds Next.js → deploys to CDN |
| **Render** | 5-8 minutes | Detects push → builds Docker image → deploys container |

## Deployment Architecture

```
Local Code → GitHub (git push) → Vercel (frontend) + Render (backend)
                                      ↓                      ↓
                              https://your-app.vercel.app  https://your-app.onrender.com
```

## Troubleshooting

### Git Lock Issues (Windows)

If you see errors like:
```
Unlink of file '.git/objects/pack/...' failed. Should I try again?
```

**Fix:**
```bash
git config core.filemode false
git push origin main
```

**Why:** Windows file permissions can conflict with Git's file tracking.

### Build Failures

If Vercel/Render build fails:

1. **Check build logs** in their respective dashboards
2. **Verify package versions** match between local and CI
3. **Test build locally** first:
   ```bash
   npm run build
   ```

### Deployment Not Reflecting Changes

If the live site doesn't show your changes after 10+ minutes:

1. **Verify push succeeded:**
   ```bash
   git log -1
   # Check the commit hash matches what's in Vercel/Render dashboards
   ```

2. **Force redeploy:**
   - Vercel: Go to Deployments → click "Redeploy" on latest commit
   - Render: Go to Dashboard → click "Manual Deploy" → "Deploy latest commit"

3. **Clear browser cache** - Sometimes the old frontend is cached

## Best Practices

1. **Always pull before push** - Prevents overwriting others' work
2. **Test locally first** - Run `npm run build` before committing
3. **Use descriptive commit messages** - Helps debug deployment issues
4. **Monitor both dashboards** - Vercel deploys faster, check both complete
5. **Keep main branch deployable** - Don't push half-finished features

## Example Session

```bash
# Make your changes, then:
cd E:\Projects\jasper-trades

# Stage all changes
git add .

# Commit with clear message
git commit -m "feat: remove hardcoded PnL defaults, use backend equity data only"

# Sync with remote (critical!)
git pull origin main

# Push to trigger deployment
git push origin main

# Wait 5-8 minutes, then check:
# - https://jasper-trades.vercel.app
# - https://jasper-trades.onrender.com
```

## Key Takeaway

**Pull → Push → Wait → Verify**

Never push without pulling first. The 30 seconds it takes to `git pull` can prevent hours of debugging overwritten changes.