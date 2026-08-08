#!/usr/bin/env python
"""Security validation test"""
import sys
sys.path.insert(0, '.')

from app.config import settings

print('=== Current Security Configuration ===')
print('SECRET_KEY length: %d chars' % len(settings.SECRET_KEY))
print('SECRET_KEY is default: %s' % (settings.SECRET_KEY == "change-this-in-production"))
print('ENVIRONMENT: %s' % settings.ENVIRONMENT)
print('DEBUG: %s' % settings.DEBUG)
print('DATABASE: %s' % ("SQLite" if "sqlite" in settings.DATABASE_URL else "PostgreSQL"))
print('CORS origins: %s' % settings.CORS_ORIGINS)
print('CORS allow credentials: %s' % settings.CORS_ALLOW_CREDENTIALS)
print()
print('=== Security Validation Results ===')

errors = []
warnings = []

# Check SECRET_KEY
if settings.SECRET_KEY == 'change-this-in-production':
    errors.append('CRITICAL: SECRET_KEY is default - must be changed!')
    
if len(settings.SECRET_KEY) < 32:
    errors.append('CRITICAL: SECRET_KEY too short (%d < 32)' % len(settings.SECRET_KEY))
else:
    print('[OK] SECRET_KEY length is sufficient')

# Check CORS
cors_list = [o.strip() for o in settings.CORS_ORIGINS.split(',')]
if '*' in cors_list and settings.CORS_ALLOW_CREDENTIALS:
    errors.append('HIGH: Wildcard CORS + credentials enabled - security risk!')
else:
    print('[OK] CORS configuration is safe')

# Production checks
if settings.ENVIRONMENT == 'production':
    if settings.DEBUG:
        errors.append('CRITICAL: DEBUG=true in production')
    else:
        print('[OK] DEBUG disabled in production')
        
    if 'sqlite' in settings.DATABASE_URL:
        warnings.append('WARNING: Using SQLite in production (recommended: PostgreSQL)')

if errors:
    print()
    print('ERRORS FOUND:')
    for i, error in enumerate(errors, 1):
        print('[ERROR] %d. %s' % (i, error))
    sys.exit(1)
else:
    print('[OK] All critical security checks passed!')
    
if warnings:
    print()
    for warning in warnings:
        print('[WARNING] %s' % warning)

sys.exit(0)

