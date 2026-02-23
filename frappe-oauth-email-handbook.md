# Frappe OAuth Email Handbook

A comprehensive guide to configuring and understanding OAuth-based email in Frappe Framework.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Key Concepts](#key-concepts)
3. [How OAuth Email Works in Frappe](#how-oauth-email-works-in-frappe)
4. [Step-by-Step: Gmail with OAuth](#step-by-step-gmail-with-oauth)
5. [Step-by-Step: Microsoft 365 / Outlook with OAuth](#step-by-step-microsoft-365--outlook-with-oauth)
6. [Service Principal (Backend App) Flow](#service-principal-backend-app-flow)
7. [Token Lifecycle and Refresh](#token-lifecycle-and-refresh)
8. [SMTP Port Blocking (DigitalOcean) and OAuth](#smtp-port-blocking-digitalocean-and-oauth)
9. [Alternatives for Port-Blocked Environments](#alternatives-for-port-blocked-environments)
10. [Troubleshooting](#troubleshooting)
11. [Code Reference Map](#code-reference-map)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Frappe Email System                       │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Email Account                                              │
│  ├── auth_method: "Basic" | "OAuth"                         │
│  ├── connected_app → Connected App (OAuth config)           │
│  ├── connected_user → User (whose token to use)             │
│  └── backend_app_flow → Service Principal (checkbox)        │
│                                                             │
│  Connected App                                              │
│  ├── client_id, client_secret                               │
│  ├── authorization_uri, token_uri                           │
│  ├── scopes[]                                               │
│  └── redirect_uri (auto-generated)                          │
│                                                             │
│  Token Cache                                                │
│  ├── Named: "{connected_app}-{user}"                        │
│  ├── access_token (encrypted)                               │
│  ├── refresh_token (encrypted)                              │
│  └── expires_in                                             │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  SENDING (Outgoing)           RECEIVING (Incoming)          │
│  ┌──────────────────┐         ┌──────────────────┐          │
│  │  Email Queue      │         │  Email Server     │         │
│  │       │           │         │  (receive.py)     │         │
│  │       ▼           │         │       │           │         │
│  │  SMTPServer       │         │  IMAP4 / POP3     │         │
│  │  (smtp.py)        │         │       │           │         │
│  │       │           │         │       ▼           │         │
│  │       ▼           │         │  XOAUTH2 SASL     │         │
│  │  XOAUTH2 SASL    │         │  Authentication    │         │
│  │  Authentication   │         │                    │         │
│  │       │           │         └──────────────────┘          │
│  │       ▼           │                                      │
│  │  smtp.gmail.com   │                                      │
│  │  :587 (TLS)       │                                      │
│  └──────────────────┘                                       │
│                                                             │
│  Exception: "Frappe Mail" service uses HTTP API,            │
│  not SMTP. All other services use SMTP.                     │
└─────────────────────────────────────────────────────────────┘
```

### The Critical Fact

**Frappe uses SMTP/IMAP/POP3 for all email operations, even with OAuth.** OAuth only changes the *authentication mechanism* — instead of sending a password, Frappe sends an OAuth2 access token using the XOAUTH2 SASL mechanism. The underlying transport protocol remains SMTP (for sending) and IMAP/POP3 (for receiving).

The only exception is the "Frappe Mail" service, which uses HTTP API calls instead of SMTP.

---

## Key Concepts

### XOAUTH2 SASL Mechanism

When OAuth is enabled, Frappe authenticates to the mail server using the XOAUTH2 SASL mechanism instead of a username/password. The authentication string is formatted as:

```
user={email}\x01auth=Bearer {access_token}\x01\x01
```

This is sent to:
- **SMTP**: via `SMTP.auth("XOAUTH2", ...)`
- **IMAP**: via `IMAP4.authenticate("XOAUTH2", ...)`
- **POP3**: via `AUTH XOAUTH2 {base64-encoded-string}`

Source: `frappe/email/oauth.py`

### Two OAuth Grant Types

Frappe supports two OAuth2 grant types for email:

| Feature | User-Delegated (Authorization Code) | Service Principal (Client Credentials) |
|---------|--------------------------------------|----------------------------------------|
| Checkbox | `backend_app_flow` unchecked | `backend_app_flow` checked |
| Grant Type | Authorization Code | Client Credentials |
| User Interaction | Required (consent screen) | None |
| Token Cache Key | `{app_name}-{user}` | `{app_name}-` (empty user) |
| Who the token represents | A specific user's mailbox | The application itself |
| Refresh Token | Yes | No (re-fetches on expiry) |
| Gmail Support | Yes | No (Gmail doesn't support Client Credentials for SMTP) |
| Microsoft 365 Support | Yes | Yes (with admin consent) |

### Connected App vs Google Settings

Frappe has **two separate OAuth systems** for Google:

1. **Connected App** (Generic OAuth2) — used by Email Account's OAuth method. This is the one we configure here.
2. **Google Settings** (Legacy) — uses `frappe/integrations/google_oauth.py`, a separate Google-specific integration. Not used by the Email Account OAuth flow.

The Email Account OAuth flow exclusively uses the **Connected App** doctype.

---

## How OAuth Email Works in Frappe

### Complete Flow Diagram

```
Phase 1: Setup
═══════════════
Admin creates Connected App
  → client_id, client_secret, authorization_uri, token_uri, scopes
  → redirect_uri auto-generated: /api/method/frappe.integrations.doctype.connected_app.connected_app.callback/{name}

Admin creates Email Account
  → auth_method = "OAuth"
  → connected_app = <the Connected App>
  → connected_user = <frappe user>
  → SMTP server, port, etc. still required


Phase 2: Authorization (User-Delegated Flow)
═════════════════════════════════════════════
User clicks "Authorize API Access" button on Email Account form
  │
  ▼
email_account.js: oauth_access(frm)
  → Calls connected_app.initiate_web_application_flow()
  │
  ▼
Browser redirects to OAuth provider (e.g. Google consent screen)
  → User grants access
  │
  ▼
OAuth provider redirects to Frappe callback URL with ?code=...&state=...
  │
  ▼
connected_app.callback()
  → Validates state matches Token Cache
  → Exchanges code for tokens via token_uri
  → Stores access_token + refresh_token in Token Cache
  → Redirects user back to Email Account form


Phase 3: Email Sending
═══════════════════════
Email Queue processes outgoing email
  │
  ▼
email_account.sendmail_config()
  → use_oauth = True
  → access_token = connected_app.get_active_token().access_token
  │    └── If expired: auto-refreshes via refresh_token
  │
  ▼
SMTPServer.__init__(use_oauth=True, access_token="...")
  │
  ▼
SMTPServer.session (property)
  → smtplib.SMTP("smtp.gmail.com", 587)
  → STARTTLS
  → Oauth(_session, email_account, login, access_token).connect()
  │    └── _connect_smtp() → SMTP.auth("XOAUTH2", auth_string_callback)
  │
  ▼
Email sent via smtp.gmail.com:587 using XOAUTH2


Phase 4: Email Receiving
════════════════════════
EmailServer.connect()
  │
  ▼
connect_imap()
  → IMAP4_SSL("imap.gmail.com", 993)
  → Oauth(imap, email_account, username, access_token).connect()
  │    └── _connect_imap() → IMAP4.authenticate("XOAUTH2", auth_string_callback)
  │
  ▼
Emails pulled via imap.gmail.com:993 using XOAUTH2
```

---

## Step-by-Step: Gmail with OAuth

### Prerequisites

- A Google Cloud Platform (GCP) project
- Access to the Google Cloud Console
- A Gmail account (or Google Workspace account)
- Your Frappe site must be accessible via HTTPS (required for OAuth redirect)

### Step 1: Create a Google Cloud OAuth Application

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Navigate to **APIs & Services > OAuth consent screen**
   - Choose **External** (or **Internal** for Google Workspace)
   - Fill in App name, User support email, Developer contact
   - Click **Save and Continue**
4. On the **Scopes** screen:
   - Click **Add or Remove Scopes**
   - Add the scope: `https://mail.google.com/`
   - This grants full IMAP/SMTP access
   - Click **Save and Continue**
5. On the **Test users** screen (for External apps in testing):
   - Add the Gmail address you want to connect
   - Click **Save and Continue**

> **Note**: For External apps, until you submit for verification, only test users can authorize. For production, you need to verify your app with Google (or use Internal if on Google Workspace).

6. Navigate to **APIs & Services > Credentials**
   - Click **Create Credentials > OAuth Client ID**
   - Application type: **Web application**
   - Name: e.g., `Frappe Email OAuth`
   - Authorized redirect URIs: Add your Frappe callback URL:
     ```
     https://your-frappe-site.com/api/method/frappe.integrations.doctype.connected_app.connected_app.callback/Gmail-OAuth
     ```
     (Replace `Gmail-OAuth` with whatever you'll name your Connected App)
   - Click **Create**
   - Note down the **Client ID** and **Client Secret**

### Step 2: Create a Connected App in Frappe

Navigate to **Connected App > New** in your Frappe site.

| Field | Example Value |
|-------|---------------|
| **Provider Name** | `Google Gmail` |
| **Client ID** | `123456789-abcdef.apps.googleusercontent.com` |
| **Client Secret** | `GOCSPX-xxxxxxxxxxxxxxxx` |
| **Authorization URI** | `https://accounts.google.com/o/oauth2/v2/auth` |
| **Token URI** | `https://oauth2.googleapis.com/token` |
| **Revocation URI** | `https://oauth2.googleapis.com/revoke` |
| **Redirect URI** | *(Auto-generated, read-only)* |

**Scopes** (child table — add one row):

| Scope |
|-------|
| `https://mail.google.com/` |

**Query Parameters** (child table — add one row):

| Key | Value |
|-----|-------|
| `access_type` | `offline` |
| `prompt` | `consent` |

> **Important**: The `access_type=offline` parameter is critical — it tells Google to return a refresh token. Without it, the access token will expire after ~1 hour with no way to renew it. The `prompt=consent` ensures the consent screen is shown every time, which guarantees a new refresh token is issued.

After saving, note the auto-generated **Redirect URI**. Go back to your Google Cloud Console and verify this URI is listed in your OAuth Client's Authorized redirect URIs. The format will be:
```
https://your-frappe-site.com/api/method/frappe.integrations.doctype.connected_app.connected_app.callback/<connected-app-name>
```

### Step 3: Create an Email Account in Frappe

Navigate to **Email Account > New**.

| Field | Value |
|-------|-------|
| **Email ID** | `yourname@gmail.com` |
| **Email Account Name** | `Gmail OAuth` |
| **Service** | `GMail` |
| **Enable Incoming** | ✓ |
| **Enable Outgoing** | ✓ |

**Authentication Section:**

| Field | Value |
|-------|-------|
| **Method** | `OAuth` |
| **Connected App** | `Google Gmail` (the Connected App you created) |
| **Connected User** | `yourname@gmail.com` (or the Frappe user that maps to this Gmail) |
| **Authenticate as Service Principal** | ☐ (unchecked) |

**Incoming (auto-filled by selecting GMail service):**

| Field | Value |
|-------|-------|
| **Use IMAP** | ✓ |
| **Use SSL** | ✓ |
| **Email Server** | `imap.gmail.com` |
| **Incoming Port** | `993` |

**Outgoing (auto-filled by selecting GMail service):**

| Field | Value |
|-------|-------|
| **Use TLS** | ✓ |
| **SMTP Server** | `smtp.gmail.com` |
| **SMTP Port** | `587` |

Save the Email Account (without validating connections yet).

### Step 4: Authorize API Access

1. On the saved Email Account form, you'll see a yellow banner: *"OAuth has been enabled but not authorised."*
2. Click the **Authorize API Access** button
3. You'll be redirected to Google's consent screen
4. Sign in with the Gmail account and grant access
5. Google redirects back to your Frappe site
6. A Token Cache record is automatically created storing your access and refresh tokens
7. The Email Account is now ready to send and receive emails

### Step 5: Verify

- Click **Pull Emails** to test incoming email
- Send a test email from the site to verify outgoing works

---

## Step-by-Step: Microsoft 365 / Outlook with OAuth

### User-Delegated Flow

#### Step 1: Register an App in Azure AD

1. Go to [Azure Portal](https://portal.azure.com/) > **Azure Active Directory** > **App registrations**
2. Click **New registration**
   - Name: `Frappe Email`
   - Supported account types: Choose as appropriate
   - Redirect URI: **Web** → `https://your-frappe-site.com/api/method/frappe.integrations.doctype.connected_app.connected_app.callback/<connected-app-name>`
3. After registration, note:
   - **Application (client) ID**
   - **Directory (tenant) ID**
4. Go to **Certificates & secrets** > **New client secret**
   - Note the **Value** (this is your client secret)
5. Go to **API permissions** > **Add a permission**
   - Select **Microsoft Graph**
   - **Delegated permissions**:
     - `IMAP.AccessAsUser.All` (for receiving)
     - `SMTP.Send` (for sending)
     - `offline_access` (for refresh tokens)
   - Click **Grant admin consent** if you're a tenant admin

#### Step 2: Create Connected App in Frappe

| Field | Example Value |
|-------|---------------|
| **Provider Name** | `Microsoft 365` |
| **Client ID** | `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` |
| **Client Secret** | `xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx` |
| **Authorization URI** | `https://login.microsoftonline.com/{tenant-id}/oauth2/v2.0/authorize` |
| **Token URI** | `https://login.microsoftonline.com/{tenant-id}/oauth2/v2.0/token` |

Replace `{tenant-id}` with your Azure AD Tenant ID (or use `common` for multi-tenant).

**Scopes** (child table):

| Scope |
|-------|
| `https://outlook.office365.com/IMAP.AccessAsUser.All` |
| `https://outlook.office365.com/SMTP.Send` |
| `offline_access` |

> **Note**: For IMAP/SMTP XOAUTH2, Microsoft requires scopes prefixed with `https://outlook.office365.com/` rather than `https://graph.microsoft.com/`.

#### Step 3: Create Email Account

| Field | Value |
|-------|-------|
| **Email ID** | `user@yourorg.onmicrosoft.com` |
| **Service** | `Outlook.com` |
| **Method** | `OAuth` |
| **Connected App** | `Microsoft 365` |
| **Connected User** | *(your Frappe user)* |
| **SMTP Server** | `smtp.office365.com` |
| **SMTP Port** | `587` |
| **Use TLS** | ✓ |
| **Email Server** | `outlook.office365.com` |
| **Incoming Port** | `993` |
| **Use SSL** | ✓ |
| **Use IMAP** | ✓ |

Then authorize and test as described in the Gmail section.

---

## Service Principal (Backend App) Flow

The "Authenticate as Service Principal" checkbox enables the **OAuth2 Client Credentials grant**. This is useful when:

- You want the application itself to send/receive emails without a user logging in
- You're using a shared mailbox
- You need a fully automated, headless setup

### How It Differs

| Aspect | User-Delegated | Service Principal |
|--------|----------------|-------------------|
| Grant Type | Authorization Code | Client Credentials |
| Token Cache Key | `{app}-{user}` | `{app}-` (empty user) |
| Code Path | `connected_app.get_active_token(user)` | `connected_app.get_backend_app_token()` |
| OAuth Session | Uses `OAuth2Session` with stored token | Uses `BackendApplicationClient` |
| Requires User Click | Yes ("Authorize API Access") | No |
| Refresh Token | Yes | No (re-fetches when expired) |
| `connected_user` field | Required | Hidden (not needed) |

Source: `frappe/integrations/doctype/connected_app/connected_app.py:158-183`

### Gmail and Service Principal

**Gmail does NOT support the Client Credentials grant for SMTP/IMAP.** Google only allows delegated access (Authorization Code flow) for Gmail SMTP/IMAP. If you need headless access to Gmail, you must use a Google Workspace domain with domain-wide delegation, which is a different mechanism not natively supported by Frappe's Connected App flow.

### Microsoft 365 and Service Principal

Microsoft 365 **does support** Client Credentials for IMAP/SMTP, but requires:

1. Azure AD app registration with **Application permissions** (not Delegated):
   - `https://outlook.office365.com/IMAP.AccessAsApp`
   - `https://outlook.office365.com/SMTP.SendAsApp`
2. Admin consent granted
3. A service principal created and registered to the mailbox via Exchange Online PowerShell:
   ```powershell
   New-ServicePrincipal -AppId <app-id> -ServiceId <object-id>
   Add-MailboxPermission -Identity "shared@org.com" -User <object-id> -AccessRights FullAccess
   ```

In the Frappe Email Account, check **Authenticate as Service Principal** and leave **Connected User** empty.

---

## Token Lifecycle and Refresh

### Token Storage

Tokens are stored in the **Token Cache** doctype:
- Name format: `{connected_app_name}-{user}` (or `{connected_app_name}-` for service principal)
- Both `access_token` and `refresh_token` are stored as encrypted Password fields
- `expires_in` stores the token TTL in seconds
- Expiry is calculated from the `modified` timestamp + `expires_in`

Source: `frappe/integrations/doctype/token_cache/token_cache.py`

### Refresh Logic

```
email_account.get_oauth_token()
    │
    ├── backend_app_flow=True
    │   └── connected_app.get_backend_app_token()
    │       └── If token expired → fetch new token via Client Credentials
    │
    └── backend_app_flow=False
        └── connected_app.get_active_token(connected_user)
            └── If token expired → refresh via refresh_token
                └── If refresh fails → returns None, logs error
```

### When Refresh Fails

If token refresh fails (e.g., refresh token revoked, app consent removed):
- An error is logged ("Token Refresh Error")
- `get_active_token()` returns `None`
- The email send/receive will fail
- User must re-authorize via the "Authorize API Access" button

### Token Expiry Details

- Google access tokens expire after **3600 seconds (1 hour)**
- Microsoft access tokens expire after **3600 seconds (1 hour)** typically
- Google refresh tokens do not expire unless revoked or unused for 6 months (for apps in "testing" mode, refresh tokens expire after 7 days)
- Microsoft refresh tokens expire after 90 days of inactivity

Source: `frappe/integrations/doctype/token_cache/token_cache.py:74-82`

---

## SMTP Port Blocking (DigitalOcean) and OAuth

### The Problem

DigitalOcean (and some other cloud providers) block outbound SMTP ports:
- **Port 25** — blocked by default
- **Port 465** — may be blocked
- **Port 587** — may be blocked

This prevents sending emails via SMTP regardless of the authentication method.

### Does OAuth Help?

**No.** OAuth changes only the authentication mechanism (from password to access token). The transport protocol is still SMTP, which requires port 587 (TLS) or 465 (SSL).

```
With Basic Auth:  Your Server ──SMTP:587──► smtp.gmail.com  (BLOCKED)
With OAuth:       Your Server ──SMTP:587──► smtp.gmail.com  (STILL BLOCKED)
```

OAuth is about **authentication**, not **transport**. The SMTP connection to `smtp.gmail.com:587` must still be established regardless of whether you authenticate with a password or an OAuth token.

### Code Evidence

From `frappe/email/smtp.py:74-86`:
```python
SMTP = smtplib.SMTP_SSL if self.use_ssl else smtplib.SMTP
_session = SMTP(self.server, self.port, timeout=self.timeout)  # TCP connection to SMTP port
self.secure_session(_session)  # TLS handshake

if self.use_oauth:
    Oauth(_session, self.email_account, self.login, self.access_token).connect()
elif self.password:
    _session.login(str(self.login or ""), str(self.password or ""))
```

The SMTP TCP connection is established *before* any authentication happens. If the port is blocked, the connection never completes.

---

## Alternatives for Port-Blocked Environments

If SMTP ports are blocked on your hosting provider, here are your options:

### Option 1: Frappe Mail (Recommended for Frappe users)

Frappe Mail is the only built-in service that uses **HTTP API** (port 443) instead of SMTP. It completely bypasses SMTP port restrictions.

- Service: `Frappe Mail`
- Transport: HTTP POST to `/api/method/mail.api.outbound.send_raw`
- Port: 443 (HTTPS) — never blocked
- Auth: API key/secret or OAuth
- Source: `frappe/email/frappemail.py`

### Option 2: Third-Party Email API Services

Use services that provide HTTP API for sending email (these require custom integration or apps):

| Service | API Endpoint | Native Frappe Support |
|---------|-------------|----------------------|
| **SendGrid** | HTTPS API | SMTP only (built-in), HTTP API via custom app |
| **Mailgun** | HTTPS API | Not built-in, available via custom app |
| **Amazon SES** | HTTPS API | Not built-in, available via custom app |
| **Postmark** | HTTPS API | Not built-in |

> Note: SendGrid and SparkPost are listed as Frappe services but they still use SMTP in the built-in implementation.

### Option 3: Request Port Unblock from DigitalOcean

DigitalOcean allows you to request SMTP port unblocking:
1. Open a support ticket
2. Explain your use case (transactional email from your application)
3. They may unblock ports 25/587 for your droplet

### Option 4: SMTP Relay via Alternative Port

Some SMTP services offer connections on port 2525 (non-standard) which may not be blocked:
- Set `smtp_port` to `2525` in the Email Account
- Services like SendGrid and Mailgun support port 2525

### Option 5: Gmail API (Not Built-in)

The Gmail API sends emails via HTTPS (port 443) using `POST https://gmail.googleapis.com/gmail/v1/users/me/messages/send`. This would bypass port blocking entirely, but **Frappe does not have built-in support for Gmail API email sending**. This would require a custom app.

---

## Troubleshooting

### "OAuth has been enabled but not authorised"

- The Token Cache doesn't exist or has no access token
- Click **Authorize API Access** to initiate the OAuth flow

### "Please Authorize OAuth for Email Account"

- The access token is missing or expired and couldn't be refreshed
- Re-authorize via the button on the Email Account form

### Token Refresh Errors

- Check Error Log for "Token Refresh Error"
- For Google: Ensure `access_type=offline` was in the query parameters when authorizing
- For Google apps in "testing" mode: Refresh tokens expire after 7 days — publish the app or re-authorize
- For Microsoft: Refresh tokens expire after 90 days of inactivity

### Redirect URI Mismatch

- The redirect URI in Google Cloud Console / Azure AD must **exactly match** the auto-generated one in the Connected App
- Check for trailing slashes, http vs https, domain mismatches
- The Frappe redirect URI format: `https://your-site.com/api/method/frappe.integrations.doctype.connected_app.connected_app.callback/{connected-app-name}`

### SMTP Authentication Failed

- Verify the scope includes the correct SMTP permission:
  - Gmail: `https://mail.google.com/`
  - Microsoft: `https://outlook.office365.com/SMTP.Send`
- Check if the token has expired and refresh failed
- Verify the `login` or `email_id` matches the account the OAuth token was generated for

### "Use different Email ID" Option

- When `backend_app_flow` is unchecked, the `login_id_is_different` checkbox appears
- Use this when the Frappe user's email differs from the SMTP login email
- Example: Frappe user is `admin@company.com` but SMTP login is `noreply@company.com`

---

## Code Reference Map

### Doctypes

| Doctype | Location | Purpose |
|---------|----------|---------|
| Email Account | `frappe/email/doctype/email_account/` | Main email configuration |
| Email Domain | `frappe/email/doctype/email_domain/` | Domain-level defaults |
| Connected App | `frappe/integrations/doctype/connected_app/` | OAuth2 provider configuration |
| Token Cache | `frappe/integrations/doctype/token_cache/` | Stores OAuth tokens |

### Key Source Files

| File | Purpose |
|------|---------|
| `frappe/email/oauth.py` | XOAUTH2 SASL implementation for SMTP/IMAP/POP3 |
| `frappe/email/smtp.py` | SMTP connection and authentication |
| `frappe/email/receive.py` | IMAP/POP3 connection and email pulling |
| `frappe/email/doctype/email_account/email_account.py` | Email Account logic, `get_oauth_token()`, `sendmail_config()` |
| `frappe/email/doctype/email_account/email_account.js` | Frontend: OAuth button, service defaults |
| `frappe/integrations/doctype/connected_app/connected_app.py` | OAuth flows, token management, callback handler |
| `frappe/integrations/doctype/token_cache/token_cache.py` | Token storage, expiry checking, refresh |
| `frappe/email/frappemail.py` | HTTP-based email sending (Frappe Mail only) |
| `frappe/email/doctype/email_queue/email_queue.py` | Email queue processing, decides SMTP vs Frappe Mail |

### Key Functions

| Function | File:Line | Purpose |
|----------|-----------|---------|
| `get_oauth_token()` | `email_account.py:812` | Gets token from Connected App |
| `get_access_token()` | `email_account.py:522` | Extracts access token string |
| `sendmail_config()` | `email_account.py:526` | Builds SMTP config with OAuth flag |
| `get_active_token()` | `connected_app.py:139` | Gets token, auto-refreshes if expired |
| `get_backend_app_token()` | `connected_app.py:158` | Client Credentials grant for service principal |
| `initiate_web_application_flow()` | `connected_app.py:91` | Starts Authorization Code flow |
| `callback()` | `connected_app.py:186` | Handles OAuth callback, exchanges code for token |
| `Oauth.connect()` | `oauth.py:37` | Authenticates SMTP/IMAP/POP3 with XOAUTH2 |
| `Oauth._auth_string` | `oauth.py:34` | Generates XOAUTH2 auth string |
| `TokenCache.is_expired()` | `token_cache.py:81` | Checks if token has expired |
| `TokenCache.update_data()` | `token_cache.py:40` | Stores token data from OAuth response |

---

## Summary

| Question | Answer |
|----------|--------|
| Does OAuth bypass SMTP? | **No.** OAuth is authentication only. SMTP transport is still used. |
| Can Gmail work with OAuth in Frappe? | **Yes.** User-delegated flow with Authorization Code grant. |
| Can Microsoft 365 work with OAuth? | **Yes.** Both user-delegated and service principal flows. |
| Does OAuth fix DigitalOcean port blocking? | **No.** SMTP ports (587/465) are still needed. |
| What fixes port blocking? | Frappe Mail (HTTP API), or requesting port unblock from provider. |
| Can Gmail API send email without SMTP? | Not natively in Frappe. Would need a custom app. |
| What authentication mechanism is used? | XOAUTH2 SASL for all protocols (SMTP, IMAP, POP3). |
| Where are tokens stored? | Token Cache doctype, encrypted fields. |
| Do tokens auto-refresh? | Yes, on access if expired (user-delegated) or re-fetched (service principal). |
