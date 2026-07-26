---
type: Architecture Example
title: CSRF middleware and PUT/PATCH request bodies
description: Middleware and request-parsing detail supporting [../patterns/htmx_patterns.md](../patterns/htmx_patterns.md) §5.
tags: [architecture, htmx, csrf, example]
context_tier: 3
---

# CSRF middleware and PUT/PATCH request bodies

Supports [../patterns/htmx_patterns.md](../patterns/htmx_patterns.md) §5 (CSRF, Django middleware, and HTTP methods).

**Django middleware:** ensure `django.middleware.csrf.CsrfViewMiddleware` is in `MIDDLEWARE` (default). Unsafe methods (POST, PUT, PATCH, DELETE) require a valid CSRF token; GET and HEAD do not. The middleware accepts the token from the `X-CSRFToken` header on AJAX requests, including HTMX.

**Request bodies and `request.POST`:** for PUT and PATCH, Django does not populate `request.POST` from typical form bodies the way it does for POST. Views should read the payload as the API defines (`request.body` with JSON, or `QueryDict` parsing). This is independent of CSRF.
