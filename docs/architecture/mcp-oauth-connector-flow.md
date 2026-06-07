# Strata MCP OAuth 2.1 Connector — flow diagrams

How a browser connector (claude.ai web · ChatGPT) connects to the hosted Strata
MCP server at `/mcp/` with **one click**, using the co-hosted OAuth 2.1
Authorization Server (PR #125). Identity reuses Clerk; the issued opaque token
maps to the same `org_id` the API-key + RLS path uses.

- **Backend (Resource Server + Authorization Server):** `https://strata-api-production-9740.up.railway.app`
- **Frontend (Clerk-gated consent page):** `https://stratabank.vercel.app/oauth/authorize`
- **Spec basis:** MCP Authorization rev 2025-06-18 (OAuth 2.1 + RFC 8414 + 7591 + 9728 + 8707 + PKCE S256)

---

## 1. One-click connect sequence

```mermaid
sequenceDiagram
    autonumber
    actor U as User (browser)
    participant C as claude.ai / ChatGPT
    participant RS as Strata RS<br/>(/mcp/)
    participant AS as Strata AS<br/>(/oauth/*, /.well-known/*)
    participant CK as Clerk<br/>(dynamic-boa-37)
    participant FE as Consent page<br/>(stratabank.vercel.app)

    C->>RS: POST /mcp (no token)
    RS-->>C: 401 WWW-Authenticate:<br/>Bearer resource_metadata="…/oauth-protected-resource/mcp/"
    C->>RS: GET /.well-known/oauth-protected-resource(/mcp[/])
    RS-->>C: { resource, authorization_servers:[AS] }
    C->>AS: GET /.well-known/oauth-authorization-server
    AS-->>C: { authorize, token, register, S256, "none" }
    C->>AS: POST /oauth/register { redirect_uris }
    AS-->>C: 201 { client_id }
    C->>U: open /oauth/authorize?client_id&code_challenge&resource&state
    U->>AS: GET /oauth/authorize
    Note over AS: _validate_authorize()<br/>redirect_uri ∈ DCR ∧ allowlist<br/>PKCE S256 ∧ resource match (slash-tolerant)
    AS-->>U: 302 → consent page (params preserved)
    U->>FE: GET /oauth/authorize?… (Clerk-gated)
    FE->>CK: sign in (Google)
    CK-->>FE: session JWT
    U->>FE: click Approve
    FE->>AS: POST /oauth/authorize/decision<br/>(Clerk Bearer + approve)
    Note over AS: verify Clerk JWT → org_id<br/>mint single-use code bound to (org_id, resource, PKCE)
    AS-->>FE: { redirect_to: cb?code=…&state=… }
    FE-->>C: navigate redirect_to
    C->>AS: POST /oauth/token (code + code_verifier)
    Note over AS: peek → verify PKCE → atomic consume<br/>issue access+refresh, audience = code.resource
    AS-->>C: 200 { access_token, refresh_token }
    C->>RS: POST /mcp Authorization: Bearer <access_token>
    RS-->>C: 307 → https://…/mcp/ (auth preserved: proxy-headers)
    C->>RS: POST /mcp/ Authorization: Bearer <access_token>
    Note over RS: lookup_access → audience check (slash-tolerant)<br/>→ Principal(org_id) → org_session_scope + RLS
    RS-->>C: tool results (org-scoped)
```

---

## 2. Three additive bearer branches at the Resource Server

`/mcp/` always requires auth. The OAuth branch is **additive** — the existing
`strata_sk_` key and Clerk-JWT paths are untouched.

```mermaid
flowchart TD
    A[Authorization: Bearer &lt;token&gt;] --> B{prefix / shape?}
    B -->|"strata_sk_…"| K[api-key store<br/>hash → Principal org_id]
    B -->|"has dots (JWT)"| J[verify_clerk_jwt<br/>→ Principal clerk_org/clerk_user]
    B -->|"opaque, dot-free"| O[oauth_tokens lookup by hash]
    O --> O1{not expired<br/>AND audience match?}
    O1 -->|yes| P[Principal org_id]
    O1 -->|no| X[401 + WWW-Authenticate]
    K --> P
    J --> P
    P --> RLS[org_session_scope<br/>+ Postgres RLS on data tables]
```

The audience check (`row.resource.rstrip("/") == settings.mcp_resource_url.rstrip("/")`)
is the RFC 8707 binding — a token minted for a different resource never
authenticates here.

---

## 3. The trailing-slash interop fix (why the live connect 400'd)

claude.ai/ChatGPT canonicalize the pasted connector URL and send the RFC 8707
`resource` indicator **without** the trailing slash, even though the transport
is mounted at `/mcp/`. An exact-match audience check rejected it.

```mermaid
flowchart LR
    subgraph paste["User pastes connector URL"]
        U1["…/mcp"]
    end
    U1 --> CAN["client canonicalizes<br/>resource = …/mcp (no slash)"]
    CAN --> CHK{"resource == config?"}
    CHK -->|"exact match (OLD)"| F["400 resource must match<br/>❌ connect fails"]
    CHK -->|"rstrip('/') both sides (NEW)"| OK["…/mcp ≡ …/mcp/<br/>✅ 302 → consent"]

    style F fill:#fee,stroke:#c00
    style OK fill:#efe,stroke:#0a0
```

`rstrip("/")` collapses only `…/mcp` ≡ `…/mcp/` ≡ `…/mcp//` (all the same mounted
transport — one 307s to the other on https, so auth is preserved). It never
touches the host, scheme, or interior path, so genuinely-distinct resources
still compare unequal. Normalization is applied symmetrically at **mint**
(`oauth.py` `_validate_authorize`) and **acceptance** (`mcp_auth.py`), so no
token minted for a different resource becomes acceptable.

---

## Prod configuration (env)

| Var (Railway) | Value | Role |
|---|---|---|
| `STRATA_OAUTH_ISSUER` | `https://strata-api-production-9740.up.railway.app` | AS issuer (no path) |
| `STRATA_MCP_RESOURCE_URL` | `https://strata-api-production-9740.up.railway.app/mcp` | RFC 8707 audience (slash-tolerant) |
| `STRATA_OAUTH_CONSENT_URL` | `https://stratabank.vercel.app/oauth/authorize` | Clerk-gated consent page |
| `STRATA_CLERK_JWKS_URL` | `https://dynamic-boa-37.clerk.accounts.dev/.well-known/jwks.json` | consent-decision JWT verify |

> The web app's Clerk publishable key (`pk_test_…dynamic-boa-37…`) and the
> backend JWKS point at the **same** Clerk (dev) instance, so the consent
> decision verifies and the flow completes. Swap both to a `pk_live_` prod
> Clerk instance before exposing to real customers.

## Connect (claude.ai / ChatGPT)

1. Settings → Connectors → **Add custom connector**
2. URL: `https://strata-api-production-9740.up.railway.app/mcp/`
3. OAuth runs automatically → Strata consent screen → sign in (Google) → **Approve**
4. Verify with the `whoami` tool (returns your org).
