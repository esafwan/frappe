# Frappe Authentication & Integration Audit Checklist

Use this checklist to track execution of the **Frappe Authentication & Integration Infrastructure Audit**.

## 0) Setup & Scope Control

- [ ] Confirm target repository path and branch.
- [ ] Record audited Frappe version (v14/v15, commit SHA).
- [ ] Create output file: `FRAPPE_AUTH_INFRASTRUCTURE.md`.
- [ ] Confirm all required audit paths exist.
- [ ] Define notation for unresolved findings: `NEEDS VERIFICATION`.

## 1) File Coverage Checklist

### 1.1 Core OAuth Infrastructure

- [ ] `frappe/utils/oauth.py`
- [ ] `frappe/integrations/oauth2.py`
- [ ] `frappe/auth.py`

### 1.2 OAuth DocTypes (Schema + Controllers)

- [ ] `frappe/integrations/doctype/oauth_client/`
- [ ] `frappe/integrations/doctype/oauth_bearer_token/`
- [ ] `frappe/integrations/doctype/oauth_authorization_code/`
- [ ] `frappe/integrations/doctype/oauth_provider_settings/`
- [ ] `frappe/integrations/doctype/oauth_scope/`
- [ ] `frappe/integrations/doctype/oauth_client_role/`
- [ ] `frappe/integrations/doctype/oauth_settings/`

### 1.3 Connected Apps Framework

- [ ] `frappe/integrations/doctype/connected_app/`
- [ ] `frappe/integrations/doctype/token_cache/`
- [ ] `frappe/integrations/utils.py`

### 1.4 Google-Specific Implementations

- [ ] `frappe/integrations/doctype/google_settings/`
- [ ] `frappe/integrations/doctype/google_calendar/`

## 2) Research Execution Checklist

### 2.1 OAuth Flow Verification

- [ ] Authorization Code flow traced end-to-end.
- [ ] PKCE support validated in code.
- [ ] Client Credentials support validated in code.
- [ ] Implicit flow support validated in code.
- [ ] For each supported flow, entry point + params + return value documented.

### 2.2 Token Lifecycle Verification

- [ ] Token storage DocTypes and DB tables identified.
- [ ] Token issuance and refresh paths traced.
- [ ] Token expiration and invalidation behavior documented.
- [ ] Token cleanup mechanism (if any) documented.
- [ ] Encryption-at-rest/security controls verified.

### 2.3 Endpoint Mapping

- [ ] All auth endpoints discovered.
- [ ] HTTP method for each endpoint confirmed.
- [ ] Handler function mapped to each endpoint.
- [ ] Purpose/side effects recorded.

### 2.4 Credential Storage Assessment

- [ ] `Password` fieldtype implementation traced.
- [ ] Secret encryption/hashing logic located.
- [ ] API key / OAuth secret suitability assessed.
- [ ] Token Cache schema + linkage analyzed.
- [ ] Production hardening recommendations drafted.

### 2.5 Connected App End-to-End Trace

- [ ] Admin configuration flow traced.
- [ ] User “Connect” initiation path traced.
- [ ] OAuth callback/token exchange path traced.
- [ ] Token retrieval helper methods documented.
- [ ] API call usage patterns documented.

### 2.6 Google Case Study / Anti-Pattern Review

- [ ] `google_settings` structure analyzed.
- [ ] `google_calendar` auth/token behavior analyzed.
- [ ] Hardcoded vs configurable elements listed.
- [ ] Generic abstraction opportunities identified.
- [ ] Reusable design recommendation drafted for HUF.

### 2.7 Integration Target Analysis

For each target, complete full matrix + narrative:

- [ ] Slack
- [ ] ClickUp
- [ ] Gmail
- [ ] Meta Messenger
- [ ] Odoo

Per-target minimum checks:

- [ ] OAuth/auth model identified.
- [ ] Fit with Frappe Connected App assessed.
- [ ] Token storage strategy recommendation defined.
- [ ] Multi-tenant implications documented.
- [ ] Refresh/re-auth lifecycle recommendation documented.
- [ ] Final verdict: Reuse / Extend / Build Custom.

## 3) Deliverable Quality Checklist

### 3.1 Structure Completeness

- [ ] Section 1: Executive Summary complete.
- [ ] Section 2: OAuth deep dive complete.
- [ ] Section 3: Credential & secret storage complete.
- [ ] Section 4: Connected Apps framework complete.
- [ ] Section 5: Google anti-pattern analysis complete.
- [ ] Section 6: Integration target assessment complete.
- [ ] Section 7: Decision framework complete.
- [ ] Section 8: Code examples complete.
- [ ] Section 9: Appendices complete.

### 3.2 Evidence & Citation Quality

- [ ] Every critical claim has a code reference.
- [ ] References use `file:line` or `file:function_name()` format.
- [ ] Assumptions are explicitly marked.
- [ ] Unknowns are marked `NEEDS VERIFICATION`.

### 3.3 Implementation Readiness

- [ ] Recommendations are specific and actionable.
- [ ] Reuse/extend/build decisions are justified.
- [ ] Examples are copy-paste ready (or clearly pseudocode).
- [ ] Decision matrix is usable for planning.

## 4) Sign-off Block

- Auditor: `____________________`
- Date: `____________________`
- Frappe version / SHA: `____________________`
- Overall confidence: `High / Medium / Low`
- Open risks:
  - `____________________`
  - `____________________`
