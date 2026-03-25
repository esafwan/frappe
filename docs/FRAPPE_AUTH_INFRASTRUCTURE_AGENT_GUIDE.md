# Frappe Auth & Integration Infrastructure — Agent-Only Reference Guide

**Audience:** Coding/research agents building Frappe apps without direct repo access.  
**Goal:** Provide implementation-ready understanding of OAuth, credential storage, Connected App, and Google integration patterns in Frappe.

---

## 1) What Frappe Provides (Practical Capability Map)

Frappe has **two parallel auth/integration systems** you need to distinguish clearly:

1. **Frappe as OAuth Provider / OpenID Provider** (server-side provider endpoints)
   - Backed by `frappe/integrations/oauth2.py` + `frappe/oauth.py` + OAuth DocTypes.
   - Supports authorization flows for client apps authenticating against Frappe.

2. **Frappe as OAuth Client** (outbound integration to external providers)
   - Modern/generalized path: `Connected App` + `Token Cache`.
   - Legacy/specialized paths: `Social Login Key` + helpers in `frappe/utils/oauth.py`, and Google-specific modules.

If you’re building new external integrations (Slack/ClickUp/etc), default to **Connected App + Token Cache** unless forced otherwise.

---

## 2) Core Libraries & Runtime Dependencies

### OAuth/identity internals
- `oauthlib` OpenID server (`WebApplicationServer`) for provider endpoints.
- `OAuthWebRequestValidator` (Frappe custom validator) bridges OAuthlib ↔ DocTypes.
- `pydantic` for dynamic client registration metadata validation.

### OAuth client/outbound integration
- `requests_oauthlib.OAuth2Session` for web app and refresh token flows.
- `oauthlib.oauth2.BackendApplicationClient` for machine-to-machine token fetch.

### Security/storage
- `passlib` (`pbkdf2_sha256`, `argon2`) for login password hashing.
- `cryptography.fernet` for reversible encryption of API secrets/token-like password fields.

### Google integrations
- `google.oauth2.credentials` and `googleapiclient.discovery.build` for Google APIs.
- Raw `requests.post/get` for token exchange and token validation.

---

## 3) OAuth Provider Endpoints (Frappe as Authorization Server)

These are method endpoints under `/api/method/...`:

| Endpoint | Method | Auth | Handler | Purpose |
|---|---|---|---|---|
| `/api/method/frappe.integrations.oauth2.authorize` | GET | Guest allowed, login required for approval | `authorize(**kwargs)` | Validate auth request, optionally render consent or redirect directly |
| `/api/method/frappe.integrations.oauth2.approve` | GET | Logged-in | `approve(*args, **kwargs)` | Finalize consent and issue authorization response |
| `/api/method/frappe.integrations.oauth2.get_token` | POST/form | Guest allowed | `get_token(*args, **kwargs)` | Token endpoint (authorization code, refresh, password grant) |
| `/api/method/frappe.integrations.oauth2.revoke_token` | POST/form | Guest allowed | `revoke_token(*args, **kwargs)` | Revoke access or refresh token |
| `/api/method/frappe.integrations.oauth2.openid_profile` | GET/POST | Auth required | `openid_profile(*args, **kwargs)` | UserInfo endpoint |
| `/api/method/frappe.integrations.oauth2.introspect_token` | GET/POST | Guest allowed | `introspect_token(token, token_type_hint)` | Token metadata/introspection |
| `/api/method/frappe.integrations.oauth2.register_client` | POST JSON | Guest allowed, feature-flagged | `register_client()` | Dynamic OAuth client registration |

### Well-known metadata endpoints
Handled by `handle_wellknown(path)`:
- `/.well-known/openid-configuration`
- `/.well-known/oauth-authorization-server` (if enabled)
- `/.well-known/oauth-protected-resource` (if enabled)

---

## 4) Supported OAuth/OIDC Flows in Practice

## 4.1 Authorization Code
**Supported**. Primary secure flow.
- Auth request validated in `authorize()` and `OAuthWebRequestValidator.validate_*` methods.
- Code persisted in `OAuth Authorization Code` by `save_authorization_code()`.
- Exchanged at token endpoint (`get_token()` → OAuthlib → `save_bearer_token()`).

## 4.2 Authorization Code + PKCE
**Supported**.
- `code_challenge` and `code_challenge_method` stored in authorization code doc.
- `validate_code()` checks `code_verifier` (`plain` and `s256`).

## 4.3 Refresh Token
**Supported**.
- `validate_refresh_token()` validates active refresh token.
- Token refresh creates new bearer record via `save_bearer_token()`.

## 4.4 Resource Owner Password Credentials (password grant)
**Technically supported** via `validate_grant_type()` including `password`, and `validate_user()` using `LoginManager.authenticate`.
- Treat as legacy/high-risk; avoid for new third-party integrations.

## 4.5 Implicit Flow
- `OAuth Client` DocType still has `grant_type=Implicit` / `response_type=Token`.
- Test coverage includes implicit token redirect behavior.
- But metadata endpoint intentionally only advertises `response_types_supported=["code"]` for secure posture.

## 4.6 Client Credentials
- **Provider side:** not broadly exposed as first-class advertised grant in metadata.
- **Connected App side (outbound client):** supported via `get_backend_app_token()` using `BackendApplicationClient`.

---

## 5) OAuth Validator Contract (Key Methods Agents Must Understand)

`OAuthWebRequestValidator` is the core extension point:

- Client/redirect/scope checks:
  - `validate_client_id(client_id, request, ...)`
  - `validate_redirect_uri(client_id, redirect_uri, request, ...)`
  - `validate_scopes(client_id, scopes, client, request, ...)`
  - `validate_response_type(client_id, response_type, client, request, ...)`

- Code/token persistence:
  - `save_authorization_code(client_id, code, request, ...)`
  - `save_bearer_token(token, request, ...)`
  - `invalidate_authorization_code(client_id, code, request, ...)`

- Token operations:
  - `validate_bearer_token(token, scopes, request)`
  - `validate_refresh_token(refresh_token, client, request, ...)`
  - `revoke_token(token, token_type_hint, request, ...)`

- OIDC claims/token:
  - `finalize_id_token(...)`
  - `get_jwt_bearer_token(...)`
  - `get_userinfo_claims(request)`

- Password grant auth:
  - `validate_user(username, password, client, request, ...)`

If you customize provider behavior, this class is your highest-leverage hook.

---

## 6) Credential Storage Model (Critical Security Knowledge)

## 6.1 `__Auth` table behavior
Frappe stores sensitive values in `__Auth` with two modes:

1. **Hashed (`encrypted = 0`)**
   - For login passwords.
   - Verified by `passlibctx.verify()`.
   - Written by `update_password()`.

2. **Encrypted (`encrypted = 1`)**
   - For reversible secrets (API keys, OAuth client secrets, refresh tokens in Password fields).
   - Written by `set_encrypted_password()`.
   - Read via `get_decrypted_password()`.
   - Cipher: Fernet key from `site_config.encryption_key`.

## 6.2 What this means for integration builders
- Use `Password` fields for secrets you need to read back (tokens/client secrets).
- Never store OAuth secrets in plain `Data` fields.
- Encryption key lifecycle is operationally critical (restores/migrations must preserve key).

---

## 7) OAuth and Integration DocTypes — What Exists and How It’s Used

## 7.1 `OAuth Client`
Purpose: Registers third-party client apps that authenticate against Frappe.

Key fields:
- `client_id` (set to document name)
- `client_secret`
- `redirect_uris`, `default_redirect_uri`
- `grant_type` (`Authorization Code` / `Implicit`)
- `response_type` (`Code` / `Token`)
- `scopes`
- `token_endpoint_auth_method` (`Client Secret Basic` / `Client Secret Post` / `None`)
- `allowed_roles` (role gate)

Important methods:
- `validate()` (assign client_id, default secret, enforce grant/response compatibility)
- `user_has_allowed_role()` (session role authorization)
- `is_public_client()`

## 7.2 `OAuth Bearer Token`
Purpose: Stores provider-side issued access/refresh token records.

Key fields:
- `access_token` (autoname)
- `refresh_token`
- `client`, `user`, `scopes`
- `expires_in`, `expiration_time`, `status`

Method:
- `clear_old_logs(days=30)` cleanup helper.

## 7.3 `OAuth Authorization Code`
Purpose: Temporary authorization code storage.

Key fields:
- `authorization_code` (autoname)
- `client`, `user`, `scopes`
- `redirect_uri_bound_to_authorization_code`
- `nonce`, `code_challenge`, `code_challenge_method`
- `validity`

## 7.4 `OAuth Settings`
Purpose: feature toggles and metadata publishing.

Key fields include:
- `show_auth_server_metadata`
- `show_protected_resource_metadata`
- `enable_dynamic_client_registration`
- `skip_authorization`
- `allowed_public_client_origins`
- resource metadata descriptors (`resource_name`, docs/policy/tos)

## 7.5 `OAuth Provider Settings` (legacy bridge)
- `skip_authorization` (`Force`/`Auto`).
- Used by compatibility function `get_oauth_settings()`.

## 7.6 `Connected App`
Purpose: Generic outbound OAuth 2.0 client config.

Key fields:
- Provider identity: `provider_name`
- Discovery: `openid_configuration`
- Client creds: `client_id`, `client_secret`, computed `redirect_uri`
- Endpoints: `authorization_uri`, `token_uri`, `userinfo_uri`, `introspection_uri`, `revocation_uri`
- Scopes table
- Query parameter table (for provider-specific extras)

Key methods:
- `get_openid_configuration()`
- `get_oauth2_session(user=None, init=False)`
- `initiate_web_application_flow(user=None, success_uri=None)`
- `get_user_token(...)`
- `get_active_token(user=None)` (refresh handling)
- `get_backend_app_token(include_client_id=None)` (machine-to-machine)

## 7.7 `Token Cache`
Purpose: Outbound token persistence per `(connected_app, user)`.

Naming pattern:
- `autoname = format:{connected_app}-{user}`

Key fields:
- `access_token` (Password)
- `refresh_token` (Password)
- `expires_in`, `token_type`
- `state`, `success_uri`
- `scopes` child table

Key methods:
- `update_data(data)`
- `is_expired()`
- `get_json()`
- `get_auth_header()`

---

## 8) Connected App End-to-End Flow (Exact Operational Sequence)

1. Admin creates `Connected App`.
2. `validate()` auto-sets callback URL to:
   - `/api/method/frappe.integrations.doctype.connected_app.connected_app.callback/<app_name>`
3. User clicks **Connect to {provider}** in form UI.
4. `initiate_web_application_flow()`:
   - builds OAuth2 session (init mode)
   - calls `authorization_url(...)` on provider auth endpoint
   - stores `state` + optional `success_uri` in `Token Cache`
5. Browser redirected to provider authorization UI.
6. Provider returns to callback endpoint with `code` + `state`.
7. `callback()` validates state, exchanges code for token via `fetch_token(...)`.
8. `token_cache.update_data(token)` stores encrypted token fields.
9. User redirected to `success_uri` or app form URL.
10. Business code obtains reusable session via `get_oauth2_session(user)`; token refresh can happen automatically.

---

## 9) Whitelisted Methods Reference (Agent Quick Catalog)

## 9.1 Provider/OIDC
- `frappe.integrations.oauth2.authorize(**kwargs)`
- `frappe.integrations.oauth2.approve(*args, **kwargs)`
- `frappe.integrations.oauth2.get_token(*args, **kwargs)`
- `frappe.integrations.oauth2.revoke_token(*args, **kwargs)`
- `frappe.integrations.oauth2.openid_profile(*args, **kwargs)`
- `frappe.integrations.oauth2.introspect_token(token, token_type_hint=None)`
- `frappe.integrations.oauth2.register_client()` (POST JSON)

## 9.2 Connected App
- `ConnectedApp.get_openid_configuration(self)`
- `ConnectedApp.initiate_web_application_flow(self, user=None, success_uri=None)`
- `frappe.integrations.doctype.connected_app.connected_app.callback(code=None, state=None)`
- `frappe.integrations.doctype.connected_app.connected_app.has_token(connected_app, connected_user=None)`

## 9.3 Google-specific
- `frappe.integrations.doctype.google_settings.google_settings.get_file_picker_settings()`
- `frappe.integrations.doctype.google_calendar.google_calendar.authorize_access(g_calendar, reauthorize=False)`
- `frappe.integrations.doctype.google_calendar.google_calendar.google_callback(code=None)`
- `frappe.integrations.doctype.google_calendar.google_calendar.sync(g_calendar=None)`
- `frappe.integrations.google_oauth.callback(state, code=None, error=None)`

## 9.4 Generic auth helper
- `frappe.auth.get_logged_user()`

---

## 10) Patterns to Reuse vs Avoid

## 10.1 Reuse
- `Connected App` + `Token Cache` for external OAuth provider integration.
- `OAuth2Session` with `auto_refresh_url` + `token_updater`.
- `Password` fieldtype storage for reversible secrets.
- OIDC discovery via `get_openid_configuration()` when provider supports it.

## 10.2 Extend
- Add tenant/workspace identifiers to token caching strategy (if one user connects multiple accounts per provider).
- Add robust refresh failure retries/backoff and observability logs.
- Add explicit token revocation call flow when disconnecting apps.

## 10.3 Avoid (legacy/specialized)
- Hardcoding provider URLs/scopes directly in app logic (Google Calendar legacy style).
- Storing long-lived tokens outside `Password`/encrypted pattern.
- Building net-new bespoke OAuth flow before checking Connected App fit.

---

## 11) Google Integration Case Study (Why It’s an Anti-Pattern for New Work)

Google modules (`Google Settings`, `Google Calendar`, `google_oauth.py`) predate/parallel Connected App and include provider-specific coupling:

- Hardcoded Google URLs/scopes.
- Custom callback routing with domain dispatch map.
- Separate token fields in Google-specific DocTypes.
- Mixed direct `requests` and Google SDK use.

For new non-Google integrations, do **not** copy this pattern. Treat it as legacy compatibility layer.

---

## 12) Practical Build Playbooks for Agents

## 12.1 New OAuth provider integration (recommended)

1. Create Connected App record with endpoints, client credentials, scopes.
2. Trigger `initiate_web_application_flow()` from UI action.
3. On success, use `get_active_token()` or `get_oauth2_session()` in server logic.
4. Use `token_cache.get_auth_header()` or OAuth2 session request methods.

### Example (server-side API call with auto-refresh session)

```python
app = frappe.get_doc("Connected App", "My Provider")
session = app.get_oauth2_session(user=frappe.session.user)
response = session.get("https://api.example.com/v1/me")
response.raise_for_status()
data = response.json()
```

## 12.2 Machine-to-machine integration (no user)

```python
app = frappe.get_doc("Connected App", "Service Principal App")
token_cache = app.get_backend_app_token(include_client_id=True)
headers = token_cache.get_auth_header()
result = frappe.integrations.utils.make_get_request("https://api.example.com/system", headers=headers)
```

## 12.3 Disconnect/reconnect pattern

- For reconnect: rerun `initiate_web_application_flow()`.
- For disconnect: clear/rotate token cache + call provider revocation endpoint if available.

---

## 13) Known Design Constraints and Caveats

- Provider metadata endpoint advertises only code flow despite historical implicit support.
- Password grant exists but should be treated as legacy.
- `Connected App` token cache key is app+user; multi-account-per-user needs custom extension.
- State and success URI are stored in Token Cache, so callback depends on pre-created state record.
- Encryption key mismatch breaks decryption of stored Password-field secrets.

---

## 14) Integration Decision Matrix (for HUF-like multi-service agents)

| Service pattern | Recommended path in Frappe |
|---|---|
| Standard OAuth2 auth code + refresh | Connected App directly |
| OAuth2 auth code + PKCE | Connected App (if provider supports your selected params) + verify query params/code verifier handling |
| Client credentials only | Connected App `get_backend_app_token()` |
| API key / static bearer only | Custom DocType with Password fields + integration utils request wrappers |
| Non-OAuth auth (e.g., XML-RPC creds) | Custom auth adapter; do not force into Connected App |

---

## 15) Minimal Method Signatures (for prompt-engineered agents)

```python
# frappe/integrations/oauth2.py
approve(*args, **kwargs)
authorize(**kwargs)
get_token(*args, **kwargs)
revoke_token(*args, **kwargs)
openid_profile(*args, **kwargs)
introspect_token(token: str, token_type_hint: str | None = None)
register_client()  # POST JSON

# frappe/integrations/doctype/connected_app/connected_app.py
ConnectedApp.get_openid_configuration(self)
ConnectedApp.get_oauth2_session(self, user=None, init=False)
ConnectedApp.initiate_web_application_flow(self, user: str | None = None, success_uri: str | None = None)
ConnectedApp.get_user_token(self, user=None, success_uri=None)
ConnectedApp.get_active_token(self, user=None)
ConnectedApp.get_backend_app_token(self, include_client_id=None)
callback(code: str | None = None, state: str | None = None)
has_token(connected_app: str, connected_user: str | None = None)

# frappe/integrations/doctype/token_cache/token_cache.py
TokenCache.get_auth_header(self)
TokenCache.update_data(self, data)
TokenCache.get_expires_in(self)
TokenCache.is_expired(self)
TokenCache.get_json(self)

# frappe/utils/password.py
get_decrypted_password(doctype, name, fieldname="password", raise_exception=True)
set_encrypted_password(doctype, name, pwd, fieldname="password")
update_password(user, pwd, doctype="User", fieldname="password", logout_all_sessions=False)
check_password(user, pwd, doctype="User", fieldname="password", delete_tracker_cache=True)
```

---

## 16) Agent Prompt Snippets You Can Reuse

### A) “Implement a new provider with Connected App”
> Use `Connected App` and `Token Cache` only. Do not use Google-specific modules. Add a server method that calls `initiate_web_application_flow`, validate callback state, persist token in `Token Cache`, and expose a helper that returns an auto-refreshing `OAuth2Session`.

### B) “Store credentials securely”
> Secrets must live in `Password` fields / `__Auth` encrypted mode via Frappe password utils. Never store tokens or client secrets in plain `Data` fields.

### C) “Add observability”
> Log outbound API failures with integration request logs and include provider/app/user identifiers (without printing secrets).

---

## 17) Final Guidance for Agents

If you only remember five rules:
1. Default to **Connected App + Token Cache** for outbound OAuth.
2. Treat Google modules as **legacy/specialized**, not architecture templates.
3. Use `Password` fields for all reversible credentials.
4. Prefer auth code + refresh (+ PKCE where required).
5. Keep token lifecycle explicit: issue, cache, refresh, revoke, rotate.

