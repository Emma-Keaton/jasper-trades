---
name: complete-ibkr-removal
description: Complete removal of IBKR broker integration from codebase and documentation
source: auto-skill
extracted_at: '2026-06-12T19:30:40.073Z'
---

# Complete IBKR Broker Removal Procedure

When removing a broker integration (like IBKR) from the Jasper Trades codebase, follow this comprehensive checklist to ensure all references are removed from both code and documentation.

## Files to Modify

### Core Backend Code

1. **Delete broker service file**
   - `backend/app/brokers/ibkr_service.py` - Remove entire file

2. **Update configuration** (`backend/app/config.py`)
   - Remove broker-specific environment variable settings (HOST, PORT, CLIENT_ID, etc.)

3. **Update database models** (`backend/app/models.py`)
   - Remove broker columns from DeviceSettings model
   - Update broker type comments in Trade model

4. **Update migrations** (`backend/app/migrations.py`)
   - Remove broker column additions from migration scripts

5. **Update broker module** (`backend/app/brokers/__init__.py`)
   - Remove lazy-load functions
   - Remove from `__all__` exports

6. **Update broker registry** (`backend/app/brokers/registry.py`)
   - Remove lazy-load helper functions
   - Remove broker initialization from `initialize_brokers()`
   - Update module docstring

7. **Update broker router** (`backend/app/brokers/router.py`)
   - Remove from BROKER_CAPABILITIES dictionary

8. **Update execution agent** (`backend/app/agents/execution.py`)
   - Update docstrings mentioning broker names

### Backend Additional Files

9. **Update model extensions** (`backend/app/models_ext/broker_connections.py`)
   - Remove from broker type comments and lists

10. **Update migration files** (`backend/app/migrations/*.py`)
    - Remove from migration docstrings and SQL comments

11. **Remove environment files**
    - `backend/.env.example` - Remove broker env vars
    - `backend/.env.render` - Remove broker env vars for deployment

12. **Clean up backup files**
    - Delete any `.pyc` cache files
    - Delete any `.new` backup files

### Documentation Files

13. **Update README** (`README.md`)
    - Remove from broker routing table
    - Remove from features list
    - Remove from tech stack table

14. **Update deployment guide** (`DEPLOYMENT.md`)
    - Remove from broker routing table
    - Remove entire broker setup section

15. **Update project plan** (`plan.md`)
    - Remove from architecture diagram
    - Remove from tech stack table
    - Remove from implementation phases
    - Remove from project structure tree

16. **Update backend docs** (`backend/BACKEND_COMPLETE.md`)
    - Remove from files created list
    - Remove from configuration examples

17. **Update implementation plan** (`backend/IMPLEMENTATION_PLAN.md`)
    - Remove entire broker integration section
    - Remove from project structure tree

18. **Update settings documentation** (`SETTINGS_API_KEYS.md`)
    - Remove from API keys list

19. **Update wireframes** (`wireframes/WIREFRAMES.md`)
    - Remove from settings UI mockups

## Verification

After removal, verify completeness:

```bash
# Search for any remaining references (should return 0 matches)
grep -r "ibkr|IBKR|Ibkr" --include="*.py" --include="*.md" --include="*.env*" .
```

## Key Principles

- **Be thorough**: Check both code AND documentation
- **Update comments**: Even casual mentions in comments should be removed
- **Check environment files**: Both example and deployment-specific files
- **Clean up backups**: Remove `.new`, `.pyc`, and other backup files
- **Verify with grep**: Always run a final search to catch missed references