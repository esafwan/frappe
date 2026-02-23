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
10. [Bypassing SMTP: Mailgun HTTP API via Frappe Hook](#bypassing-smtp-mailgun-http-api-via-frappe-hook)
11. [Building the Mailgun Frappe App: Detailed Plan](#building-the-mailgun-frappe-app-detailed-plan)
12. [Troubleshooting](#troubleshooting)
13. [Code Reference Map](#code-reference-map)

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

## Bypassing SMTP: Mailgun HTTP API via Frappe Hook

This is the solution for environments where SMTP ports are blocked (DigitalOcean, etc.). Instead of fighting port restrictions, we intercept all outgoing emails at the Frappe level and route them through Mailgun's HTTP API (port 443, which is never blocked).

### The Key: `override_email_send` Hook

Frappe provides a hook called `override_email_send` that intercepts **every** outgoing email before it reaches SMTP. This is the exact integration point we need.

From `frappe/email/doctype/email_queue/email_queue.py:187-203`:

```python
message = ctx.build_message(recipient.recipient)
if method := get_hook_method("override_email_send"):
    method(self, self.sender, recipient.recipient, message)
elif not frappe.in_test or frappe.flags.testing_email:
    if ctx.email_account_doc.service == "Frappe Mail":
        ctx.frappe_mail_client.send_raw(...)
    else:
        ctx.smtp_server.session.sendmail(...)
```

**How it works:**
1. Frappe builds the complete MIME message (headers, body, attachments — everything)
2. Before sending via SMTP, it checks for an `override_email_send` hook
3. If the hook exists, it calls the hook function **instead of** SMTP
4. The hook receives the fully-built MIME message and can send it any way it wants
5. If the hook function completes without raising an exception, the email is marked as "Sent"

**Hook function signature:**
```python
def send_via_mailgun(email_queue_doc, sender, recipient, message):
    """
    Args:
        email_queue_doc: EmailQueue document (has .name, .sender, .recipients, .reference_doctype, etc.)
        sender: str - The sender email address (e.g., "John <john@example.com>")
        recipient: str - Single recipient email address
        message: bytes - Complete RFC-compliant MIME message (ready to send as-is)
    """
```

**Critical detail:** The `message` parameter is the **complete MIME message** as bytes — headers, body, attachments, everything. This maps perfectly to Mailgun's `POST /v3/{domain}/messages.mime` endpoint, which accepts pre-built MIME messages.

### How Mailgun's MIME Endpoint Works

Mailgun offers two sending methods:
1. **Component-based** (`POST /v3/{domain}/messages`) — you pass from, to, subject, text, html separately
2. **MIME-based** (`POST /v3/{domain}/messages.mime`) — you pass a pre-built RFC-compliant MIME string

Since Frappe already builds the complete MIME, we use **method 2** — just forward the MIME as-is. This preserves all formatting, headers, attachments, inline images, tracking pixels, etc.

```bash
# Mailgun MIME sending endpoint
curl -s --user 'api:YOUR_API_KEY' \
    https://api.mailgun.net/v3/YOUR_DOMAIN/messages.mime \
    -F to=recipient@example.com \
    -F message=@/path/to/mime_message.eml
```

In Python with `requests`:
```python
import requests

response = requests.post(
    f"https://api.mailgun.net/v3/{domain}/messages.mime",
    auth=("api", api_key),
    data={"to": recipient},
    files={"message": ("message.mime", mime_bytes)},
)
```

### Architecture with the Hook

```
┌─────────────────────────────────────────────────────────────┐
│                  With override_email_send Hook               │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Email Queue                                                │
│       │                                                     │
│       ▼                                                     │
│  build_message()  ──► Complete MIME (bytes)                  │
│       │                                                     │
│       ▼                                                     │
│  get_hook_method("override_email_send")                     │
│       │                                                     │
│       ▼  (hook exists!)                                     │
│  mailgun_app.send_via_mailgun(                              │
│      email_queue_doc, sender, recipient, mime_message       │
│  )                                                          │
│       │                                                     │
│       ▼                                                     │
│  POST https://api.mailgun.net/v3/{domain}/messages.mime     │
│       │         (port 443 — HTTPS, never blocked)           │
│       ▼                                                     │
│  Mailgun delivers email                                     │
│                                                             │
│  ✗ SMTP is NEVER used                                       │
│  ✗ Port 587/465/25 is NEVER needed                          │
│  ✓ Only port 443 (HTTPS) is needed                          │
└─────────────────────────────────────────────────────────────┘
```

### Mailgun API Authentication

Mailgun uses HTTP Basic Auth:
- **Username**: `api` (literal string)
- **Password**: Your Mailgun API key (e.g., `key-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`)

Two types of API keys:
1. **Primary Account API Key** — full access to all domains and endpoints
2. **Domain Sending Key** — can only send via `/messages` and `/messages.mime` for a specific domain

For this integration, a **Domain Sending Key** is sufficient and more secure.

### Mailgun Regions

| Region | API Base URL | SMTP Server |
|--------|-------------|-------------|
| US | `https://api.mailgun.net` | `smtp.mailgun.org` |
| EU | `https://api.eu.mailgun.net` | `smtp.eu.mailgun.org` |

Your API calls must use the correct region URL matching where your domain is provisioned.

### Mailgun Rate Limits and Constraints

- Maximum message size: **25MB**
- Rate limits are in place (headers: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`)
- Supports gzip-compressed request bodies (`Content-Encoding: gzip`)
- Email addresses must pass RFC5321/RFC5322 syntax checks

### Response Codes to Handle

| Code | Meaning | Action |
|------|---------|--------|
| 200 | Success | Email accepted for delivery |
| 400 | Bad Request | Invalid parameters — log and fail |
| 401 | Unauthorized | Bad API key — log and fail |
| 403 | Forbidden | No access to domain — log and fail |
| 429 | Rate Limited | Retry with backoff (check `X-RateLimit-Reset` header) |
| 500 | Server Error | Retry with exponential backoff |

---

## Building the Mailgun Frappe App: Detailed Plan

### Overview

We will build a custom Frappe app called `frappe_mailgun` that:
1. Intercepts all outgoing emails using the `override_email_send` hook
2. Sends them via Mailgun's HTTP API (`/v3/{domain}/messages.mime`)
3. Provides a settings doctype for Mailgun configuration
4. Handles errors, retries, and logging

### App Structure

```
frappe_mailgun/
├── frappe_mailgun/
│   ├── __init__.py
│   ├── hooks.py                          # Register override_email_send hook
│   ├── mailgun.py                        # Core Mailgun HTTP API client
│   ├── frappe_mailgun/
│   │   └── doctype/
│   │       └── mailgun_settings/
│   │           ├── __init__.py
│   │           ├── mailgun_settings.py   # Settings doctype controller
│   │           ├── mailgun_settings.json # DocType definition
│   │           └── test_mailgun_settings.py
│   └── templates/
│       └── (empty)
├── setup.py
├── requirements.txt                      # requests (already a frappe dependency)
└── README.md
```

### Step 1: Scaffold the App

```bash
cd ~/frappe-bench
bench new-app frappe_mailgun
# Answer prompts:
#   App Title: Frappe Mailgun
#   App Description: Send emails via Mailgun HTTP API, bypassing SMTP port restrictions
#   App Publisher: Your Name
#   App Email: your@email.com
#   App License: MIT

bench install-app frappe_mailgun --site your-site.localhost
```

### Step 2: Create the Mailgun Settings DocType

This is a **Single** doctype (only one instance, like System Settings) to store Mailgun credentials.

**DocType: Mailgun Settings**

| Field | Fieldtype | Label | Notes |
|-------|-----------|-------|-------|
| `enabled` | Check | Enabled | Master switch |
| `sb_credentials` | Section Break | Credentials | |
| `api_key` | Password | API Key | Encrypted storage. The Mailgun API key |
| `domain_name` | Data | Domain Name | e.g., `mg.yourdomain.com` |
| `cb_1` | Column Break | | |
| `region` | Select | Region | Options: `US\nEU`. Default: `US` |
| `api_url` | Data | API URL (read-only) | Auto-computed from region |
| `sb_options` | Section Break | Options | |
| `log_emails` | Check | Log Sent Emails | Log each send to Error Log for debugging |
| `raise_on_failure` | Check | Raise Exception on Failure | If unchecked, silently log failures |

**`mailgun_settings.json`** (DocType definition):
```json
{
    "name": "Mailgun Settings",
    "doctype": "DocType",
    "module": "Frappe Mailgun",
    "issingle": 1,
    "document_type": "Setup",
    "fields": [
        {
            "fieldname": "enabled",
            "fieldtype": "Check",
            "label": "Enabled",
            "default": "0"
        },
        {
            "fieldname": "sb_credentials",
            "fieldtype": "Section Break",
            "label": "Credentials"
        },
        {
            "fieldname": "api_key",
            "fieldtype": "Password",
            "label": "API Key",
            "mandatory_depends_on": "eval: doc.enabled"
        },
        {
            "fieldname": "domain_name",
            "fieldtype": "Data",
            "label": "Domain Name",
            "description": "Your verified Mailgun sending domain (e.g., mg.yourdomain.com)",
            "mandatory_depends_on": "eval: doc.enabled"
        },
        {
            "fieldname": "cb_1",
            "fieldtype": "Column Break"
        },
        {
            "fieldname": "region",
            "fieldtype": "Select",
            "label": "Region",
            "options": "US\nEU",
            "default": "US"
        },
        {
            "fieldname": "api_url",
            "fieldtype": "Data",
            "label": "API URL",
            "read_only": 1,
            "description": "Auto-set based on region"
        },
        {
            "fieldname": "sb_options",
            "fieldtype": "Section Break",
            "label": "Options"
        },
        {
            "fieldname": "log_emails",
            "fieldtype": "Check",
            "label": "Log Sent Emails",
            "default": "0"
        },
        {
            "fieldname": "raise_on_failure",
            "fieldtype": "Check",
            "label": "Raise Exception on Failure",
            "default": "1",
            "description": "If unchecked, failures are logged silently and the email is marked as sent"
        }
    ],
    "permissions": [
        {
            "role": "System Manager",
            "read": 1,
            "write": 1,
            "create": 1
        }
    ]
}
```

**`mailgun_settings.py`** (Controller):
```python
import frappe
from frappe.model.document import Document

API_URLS = {
    "US": "https://api.mailgun.net",
    "EU": "https://api.eu.mailgun.net",
}


class MailgunSettings(Document):
    def validate(self):
        self.api_url = API_URLS.get(self.region, API_URLS["US"])

    @staticmethod
    def get_settings():
        """Return cached Mailgun settings."""
        return frappe.get_cached_doc("Mailgun Settings")
```

### Step 3: Build the Mailgun Client

**`mailgun.py`** — Core sending logic:

```python
import frappe
import requests
from frappe import _


def send_via_mailgun(email_queue_doc, sender, recipient, message):
    """
    Hook function for override_email_send.

    Called by Frappe's email queue for every outgoing email.
    Sends the pre-built MIME message via Mailgun's HTTP API.

    Args:
        email_queue_doc: EmailQueue document instance
        sender: str - Sender email (e.g., "Name <email@domain.com>")
        recipient: str - Single recipient email address
        message: bytes - Complete MIME message
    """
    settings = frappe.get_cached_doc("Mailgun Settings")

    if not settings.enabled:
        # Mailgun not enabled — fall through to default SMTP behavior.
        # NOTE: Since this is override_email_send, returning without raising
        # means the email will be marked as sent. If Mailgun is disabled,
        # we should raise so Frappe falls back. But the hook doesn't support
        # fallback — if the hook exists, SMTP is skipped entirely.
        # So if disabled, we must still send somehow or raise an error.
        frappe.throw(
            _("Mailgun is not enabled. Please enable it in Mailgun Settings or remove the app."),
            title=_("Mailgun Disabled"),
        )

    api_key = settings.get_password("api_key")
    domain = settings.domain_name
    api_url = settings.api_url or "https://api.mailgun.net"

    if not api_key or not domain:
        frappe.throw(
            _("Mailgun API Key and Domain are required. Configure in Mailgun Settings."),
            title=_("Mailgun Configuration Error"),
        )

    # Ensure message is bytes
    if isinstance(message, str):
        message = message.encode("utf-8")

    url = f"{api_url}/v3/{domain}/messages.mime"

    try:
        response = requests.post(
            url,
            auth=("api", api_key),
            data={"to": recipient},
            files={"message": ("message.mime", message, "message/rfc822")},
            timeout=30,
        )

        if settings.log_emails:
            frappe.log_error(
                title=f"Mailgun: Sent to {recipient}",
                message=(
                    f"Status: {response.status_code}\n"
                    f"Sender: {sender}\n"
                    f"Recipient: {recipient}\n"
                    f"Queue: {email_queue_doc.name}\n"
                    f"Response: {response.text}"
                ),
                reference_doctype="Email Queue",
                reference_name=email_queue_doc.name,
            )

        if response.status_code == 200:
            return  # Success — Frappe will mark as Sent

        # Handle specific error codes
        if response.status_code == 401:
            error_msg = _("Mailgun authentication failed. Check your API key.")
        elif response.status_code == 404:
            error_msg = _("Mailgun domain '{0}' not found. Check domain name and region.").format(domain)
        elif response.status_code == 429:
            error_msg = _("Mailgun rate limit exceeded. Email will be retried.")
        else:
            error_msg = _("Mailgun API error {0}: {1}").format(response.status_code, response.text)

        frappe.log_error(
            title=f"Mailgun Send Failed ({response.status_code})",
            message=error_msg,
            reference_doctype="Email Queue",
            reference_name=email_queue_doc.name,
        )

        if settings.raise_on_failure:
            frappe.throw(error_msg, title=_("Mailgun Error"))

    except requests.exceptions.Timeout:
        frappe.log_error(
            title="Mailgun Timeout",
            message=f"Request to Mailgun timed out for {recipient}",
            reference_doctype="Email Queue",
            reference_name=email_queue_doc.name,
        )
        if settings.raise_on_failure:
            frappe.throw(_("Mailgun request timed out. Email will be retried."))

    except requests.exceptions.ConnectionError:
        frappe.log_error(
            title="Mailgun Connection Error",
            message=f"Could not connect to Mailgun API for {recipient}",
            reference_doctype="Email Queue",
            reference_name=email_queue_doc.name,
        )
        if settings.raise_on_failure:
            frappe.throw(_("Could not connect to Mailgun API. Check network."))

    except Exception:
        frappe.log_error(
            title="Mailgun Unknown Error",
            reference_doctype="Email Queue",
            reference_name=email_queue_doc.name,
        )
        if settings.raise_on_failure:
            raise
```

### Step 4: Register the Hook

**`hooks.py`**:

```python
app_name = "frappe_mailgun"
app_title = "Frappe Mailgun"
app_publisher = "Your Name"
app_description = "Send emails via Mailgun HTTP API, bypassing SMTP port restrictions"
app_email = "your@email.com"
app_license = "MIT"

# This is the critical line — intercepts ALL outgoing emails
override_email_send = "frappe_mailgun.mailgun.send_via_mailgun"
```

That single line is all it takes. When Frappe processes the email queue, it calls `get_hook_method("override_email_send")`, finds our function, and routes all emails through Mailgun.

### Step 5: Configure Mailgun Settings

After installing the app:

1. Go to **Mailgun Settings** in your Frappe site
2. Check **Enabled**
3. Enter your **API Key** (from Mailgun Dashboard > Account Settings > API Keys)
4. Enter your **Domain Name** (e.g., `mg.yourdomain.com`)
5. Select **Region** (US or EU, matching where your Mailgun domain is provisioned)
6. Save

### Step 6: Configure Email Account (Simplified)

Since all emails now go through Mailgun HTTP API, the Email Account SMTP settings become irrelevant for sending. But you still need an Email Account configured:

| Field | Value |
|-------|-------|
| **Email ID** | `notifications@yourdomain.com` |
| **Enable Outgoing** | ✓ |
| **SMTP Server** | *(any value — it won't be used)* |
| **SMTP Port** | *(any value — it won't be used)* |
| **No SMTP Authentication** | ✓ |

The Email Account is still needed because Frappe requires one to queue emails, but SMTP is never contacted — the hook intercepts before that point.

### Important Considerations

#### 1. The Hook is All-or-Nothing

The `override_email_send` hook replaces **all** email sending. There is no per-account or per-service selection. When the hook is registered:
- ALL emails go through the hook function
- SMTP is NEVER used (not even for non-Mailgun accounts)
- Frappe Mail service is also bypassed

If you need some emails to go through SMTP and others through Mailgun, you'd need to add conditional logic inside the hook function:

```python
def send_via_mailgun(email_queue_doc, sender, recipient, message):
    settings = frappe.get_cached_doc("Mailgun Settings")

    if not settings.enabled:
        # Can't fall back to SMTP from inside the hook!
        # The hook's existence prevents SMTP from being called.
        # Option: Use smtplib directly as a fallback
        _send_via_smtp_fallback(email_queue_doc, sender, recipient, message)
        return

    # ... Mailgun logic ...
```

#### 2. Error Handling and Retries

When the hook function **raises an exception**:
- The `SendMailContext.__exit__` catches it
- The email status is set to "Not Sent" (or "Partially Sent" if some recipients succeeded)
- The `retry` counter is incremented
- After `get_email_retry_limit()` failures, status becomes "Error"

This means: if Mailgun returns a 5xx error and you raise, Frappe will automatically retry the email later. This is the desired behavior.

#### 3. Sender Domain Must Match Mailgun Domain

Mailgun requires the sender's domain to match your verified sending domain. If your Frappe Email Account uses `noreply@company.com`, your Mailgun domain must be `company.com` (or a subdomain like `mg.company.com` with appropriate DNS setup).

#### 4. DNS Configuration for Mailgun

Even though we're using HTTP API (not SMTP), Mailgun still requires DNS records for email deliverability:
- **SPF record**: Authorizes Mailgun to send on behalf of your domain
- **DKIM records**: Cryptographic signatures for authentication
- **MX records** (optional): Only needed if receiving email via Mailgun

#### 5. Message Size Limit

Mailgun's maximum message size is 25MB. Frappe's Email Account has an `attachment_limit` field — ensure it's set below 25MB.

### Testing

```python
# In bench console
import frappe

# Test that the hook is registered
from frappe.utils import get_hook_method
method = get_hook_method("override_email_send")
print(method)  # Should print: <function send_via_mailgun at 0x...>

# Test sending
frappe.sendmail(
    recipients=["test@example.com"],
    subject="Test via Mailgun",
    message="This email was sent via Mailgun HTTP API!",
)
```

### Complete File Listing

#### `hooks.py`
```python
app_name = "frappe_mailgun"
app_title = "Frappe Mailgun"
app_publisher = "Your Name"
app_description = "Send emails via Mailgun HTTP API, bypassing SMTP port restrictions"
app_email = "your@email.com"
app_license = "MIT"

override_email_send = "frappe_mailgun.mailgun.send_via_mailgun"
```

#### `mailgun.py`
```python
import frappe
import requests
from frappe import _


def send_via_mailgun(email_queue_doc, sender, recipient, message):
    settings = frappe.get_cached_doc("Mailgun Settings")

    if not settings.enabled:
        frappe.throw(
            _("Mailgun is not enabled. Configure in Mailgun Settings."),
            title=_("Mailgun Disabled"),
        )

    api_key = settings.get_password("api_key")
    domain = settings.domain_name
    api_url = settings.api_url or "https://api.mailgun.net"

    if isinstance(message, str):
        message = message.encode("utf-8")

    response = requests.post(
        f"{api_url}/v3/{domain}/messages.mime",
        auth=("api", api_key),
        data={"to": recipient},
        files={"message": ("message.mime", message, "message/rfc822")},
        timeout=30,
    )

    if response.status_code != 200:
        frappe.log_error(
            title=f"Mailgun Error ({response.status_code})",
            message=f"Recipient: {recipient}\nResponse: {response.text}",
            reference_doctype="Email Queue",
            reference_name=email_queue_doc.name,
        )
        frappe.throw(
            _("Mailgun API error {0}: {1}").format(response.status_code, response.text),
            title=_("Mailgun Error"),
        )
```

#### `mailgun_settings.py`
```python
import frappe
from frappe.model.document import Document

API_URLS = {
    "US": "https://api.mailgun.net",
    "EU": "https://api.eu.mailgun.net",
}


class MailgunSettings(Document):
    def validate(self):
        self.api_url = API_URLS.get(self.region, API_URLS["US"])
```

### Summary: Why This Works

| Concern | Solution |
|---------|----------|
| SMTP ports blocked | Mailgun HTTP API uses port 443 (HTTPS) |
| Complex integration needed? | No — single hook function, ~30 lines of core logic |
| Frappe MIME message reused? | Yes — passed directly to Mailgun's `/messages.mime` |
| Attachments preserved? | Yes — they're part of the MIME message |
| Email tracking preserved? | Yes — Frappe's tracking pixels are in the MIME |
| Unsubscribe links preserved? | Yes — already in the MIME headers/body |
| Error handling? | Raise exception → Frappe retries automatically |
| Configuration? | Single Settings doctype: API key + domain + region |

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
