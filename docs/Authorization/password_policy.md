---
type: "Authorization Guide"
title: "Password Policy (OWASP-Compliant)"
description: "This application enforces password requirements based on the [OWASP Authentication Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html)."
tags: [authorization, authorization-guide]
context_tier: 2
---

# Password Policy (OWASP-Compliant)

This application enforces password requirements based on the [OWASP Authentication Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html).

## Requirements

Passwords must meet the following criteria:

1. **Minimum length: 12 characters** — long passwords are more secure than artificial complexity requirements.
2. **Cannot match username or email** — prevents obvious password choices.
3. **Cannot be a commonly used password** — checked against a blocklist of 20,000+ compromised passwords.
4. **Spaces and special characters encouraged** — passphrase-like passwords (e.g. `correcthorsebatterystaple`) are very secure.

## What OWASP does *not* recommend

This application **intentionally does not enforce**:

- **Uppercase/lowercase/number/symbol mixtures** — complex rules don't meaningfully improve security and reduce usability.
- **Periodic password expiration** — forced changes reduce security by encouraging reuse and weak passwords.
- **Password history / uniqueness** — the user should choose strong new passwords naturally; forcing uniqueness is not needed.

## Implementation

### Validators (`settings.py`)

```python
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "app.administration.control_layer.password_validators.OWASPMinimumLengthValidator",
        "OPTIONS": {
            "min_length": 12,
        },
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
]
```

The standard `NumericPasswordValidator` is intentionally **removed** — it rejected purely numeric passphrases (e.g. `123456789012`) that OWASP guidance explicitly recommends allowing.

### Custom validator

`app/administration/control_layer/password_validators.py` provides:

- **`OWASPMinimumLengthValidator`** — configurable minimum length (default: 12 characters) with OWASP-compliant messaging.

## For users

When setting a password, the UI displays:

- Minimum 12 characters.
- Cannot match username or email.
- Cannot be a commonly used password.
- Spaces and special characters are allowed and encouraged.

## Examples

✓ **Strong passwords** (all meet requirements):
- `Correct Horse Battery Staple` (passphrase)
- `MyDog's name is Max, born 2020!`
- `correcthorsebatterystaple`
- `MyPassword123!@#` (traditional complex password)

✗ **Weak passwords** (fail requirements):
- `short` (too short)
- `password` (commonly used)
- `jdoe` or `john.doe@company.com` (matches username/email)

## References

- [OWASP Authentication Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html)
- [OWASP Password Storage Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html)
- [NIST 800-63B Digital Identity Guidelines](https://pages.nist.gov/800-63-3/sp800-63b.html)
