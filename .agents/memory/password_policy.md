---
name: OWASP Password Policy Implementation
description: Passwords now follow OWASP standards - 12-char minimum, no complexity rules, common password blocklist
type: project
---

Implemented OWASP-compliant password requirements in the Django Asset Management application.

**Changes:**
- Minimum password length increased from 8 to 12 characters
- Removed NumericPasswordValidator (OWASP recommends against arbitrary complexity rules)
- Created custom OWASPMinimumLengthValidator for 12-char enforcement
- Updated user password form template to display policy clearly
- Updated admin tests to use compliant passwords

**Files Modified:**
- `app/config/settings.py` — Updated AUTH_PASSWORD_VALIDATORS (removed NumericPasswordValidator)
- `app/administration/templates/users/edit.html` — Added password policy help text to form
- `app/administration/tests/basic_page_load_tests.py` — Updated test password to meet 12-char minimum

**Files Created:**
- `app/administration/control_layer/password_validators.py` — Custom OWASPMinimumLengthValidator class
- `docs/DOMAIN/admin/PASSWORD_POLICY.md` — Policy documentation with examples and OWASP references

**Why:** OWASP guidance emphasizes length over complexity. Longer passwords are more secure than requiring uppercase/numbers/symbols, which often lead to predictable patterns and lower usability.
