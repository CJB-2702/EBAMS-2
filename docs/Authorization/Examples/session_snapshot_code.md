---
type: "Authorization Guide"
title: "Session Snapshot — Reference Code"
description: "The literal session-population code referenced by [../architecture_summary.md](../architecture_summary.md)'s Session snapshot section."
tags: [authorization, authorization-guide, example]
context_tier: 3
---

# Session Snapshot — Reference Code

Supports [../architecture_summary.md](../architecture_summary.md). At login (or after any template/domain change), the session is updated with:

```python
session['user_domain_ids'] = set(
    UserDomain.objects.filter(
        user=user,
        is_active=True,
    ).values_list('domain_id', flat=True)
)

session['user_permission_codenames'] = set(
    Permission.objects.filter(
        group__user=user
    ).values_list('codename', flat=True)
)
```

Every data-filtered query checks `user_domain_ids` to scope rows. Every permission check uses Django's native `has_perm()` against `user.groups`. Per-request database lookups would be prohibitively slow; the session is updated only on assignment/revocation, not per request.
