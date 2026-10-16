# Wallapop — auth and the private messaging API

Seller-side chat. There is **no public API**; the Angular SPA at `es.wallapop.com/app/chat`
talks to a private one you can replay from Node. Captured 2026-08-17 against a live seller
account. No antibot: plain `curl` gets through `api.wallapop.com` with no challenge.

## The one thing that will waste your day: how the token is renewed

`Authorization: Bearer {accessToken}` for every read. That token **lives 300 seconds**, so you
cannot copy it into an env var — you must mint one per run.

**The refresh does NOT go to `api.wallapop.com`.** It goes to a next-auth route on the Next.js
front, returns an **empty body**, and hands you the token in a `Set-Cookie`:

```
GET https://es.wallapop.com/api/auth/federated-session
Cookie: __Secure-next-auth.session-token={credential}

→ 200, EMPTY BODY
  Set-Cookie: accessToken=<JWT ~951 chars>                  ← the token, 300 s
  Set-Cookie: __Secure-next-auth.session-token=<NEW VALUE>  ← rotated, sliding 30 days
  Set-Cookie: __Host-next-auth.csrf-token=…
  Set-Cookie: __Secure-next-auth.callback-url=…
```

- **The credential is `__Secure-next-auth.session-token`** (httpOnly, ~3.5 kB, opaque JWE — not a
  JWT, don't try to decode it). Not `refreshToken`.
- **Parse the token out of `Set-Cookie`**, not the body. Use `headers.getSetCookie()`; if you fall
  back to `headers.get('set-cookie')` the values arrive comma-joined and `Expires=Tue, 17 Aug …`
  has a comma inside, so split only on `,\s*(?=[\w!#$%&'*+\-.^_`|~]+=)`.
- **Use `redirect: 'manual'`.** A dead session answers with a redirect to the login page; following
  it gives you a 200 full of HTML and a useless diagnosis.
- `device_id` and the `DeviceOS` / `X-DeviceOS` / `X-DeviceID` / `X-AppVersion` headers are
  **optional** — the inbox returns 200 without any of them.

### TRAP: `POST /api/v3/access/refresh` is dead — 400 with an empty body

Every guide (and the bundle) documents this as the refresh, with `X-RefreshSession` (old access
token) and `X-DeviceToken`, returning `{"token":…}`. It returns **400 with a zero-length body**
(`x-wallapop-service: auth`), which tells you nothing. Tried with a *live* `refreshToken` cookie,
with/without `X-RefreshSession`, with/without device headers, with the full cookie jar, and from
the page's own origin with `credentials: 'include'`. Six for six: 400.

It is still in the bundle because it is the **fallback**. In `chunk-WGXZ7CT5.js`:

```js
refreshToken() {                                    // AuthService
  return this.tryFederatedSession().pipe(
    switchMap(t => t ? of(t) : this.tryLegacyRefresh()), …)
}
tryFederatedSession() {                             // GET webseoBaseUrl + api/auth/federated-session
  return this.federatedSessionHttpService.session().pipe(
    map(() => { let t = this.accessTokenService.accessToken;   // ← reads the COOKIE, not the response
                return t ? { token: t } : null; }), …)
}
```

That `map()` reading the cookie instead of the response body is the tell: the endpoint does not
*return* the token, it *sets* it.

### The credential rotates — persist it

Every refresh returns a different `__Secure-next-auth.session-token` with a sliding 30-day expiry.
If you keep the credential in a config file and never update it, your integration dies 30 days
after you copied the cookie, with no warning.

**The old value keeps working after rotation** (verified: reused the pre-rotation value, still
minted tokens). It's a stateless JWE, not a server-side session, so rotating does **not** log the
human out of their browser. That means you can exercise the refresh freely while developing.

### Accounts can be on different auth stacks

Same site, two shapes of access token — check before assuming:

| stack | `iss` | length | lifetime |
|---|---|---|---|
| Keycloak / next-auth | `https://accounts.wallapop.com/realms/wallapop-internal` | 951 | **300 s** |
| older | (absent) | 552 | **24 h** |

Only the first has `federated-session` working (it needs the next-auth session cookie). If the
cookie jar has **no** `__Secure-next-auth.*` cookie, that profile is on the other stack and there
is currently no working refresh for it.

The access token's claims are useful and free: `hashed_sub` is the messaging user hash, `sub` the
numeric account id. **Verify `hashed_sub` before trusting a cookie jar** — a browser can be logged
into a personal account and a business account in two different Chrome profiles, and every endpoint
returns 200 for the wrong one.

### The 401 tells you which kind it is — in a header

Response header **`x-wallapop-unauthorized`**: `ACCESS_TOKEN_EXPIRED` (renew and retry once) or
`REFRESH_TOKEN_EXPIRED` (session dead, stop). The body usually repeats it as
`{"code":"ACCESS_TOKEN_EXPIRED"}`, but the header is what their own interceptor reads. Check both.
A 401 with **no** such header also means "session dead" in their code.

## Reading

Base `https://api.wallapop.com/`. One GET gets you the inbox *with messages inside*:

```
GET /bff/messaging/inbox?page_size=30&max_messages=30
```
```json
{"user_hash":"<ours>", "unread_messages":0,
 "conversations":[{
   "hash":"<conversationId>",
   "with_user":{"hash","name","blocked","available","slug","image_url","response_rate",
                "rating_average","location","malicious","reviews_count","score","preferences"},
   "item":{"hash","price","title","image_url","slug","status","is_mine","category_id"},
   "messages":{"messages":[…]},
   "unread_messages":0, "translatable":true,
   "channel":"chat.<userHash>.…", "topic_id":…, "items_count":…,
   "sale":null, "map_enabled":false
 }]}
```

- **`next_from` is OMITTED at the root when there are no more pages** — it is not `null`. With a
  small `page_size` it shows up as an 84-char base64 token.
- The `messages` block has **no** `next_from` inside it (guides say it does).
- No `phone_shared` / `phone_number` (guides say there are).
- **`item.is_mine`** — `false` means you are the *buyer* in that thread. Per-conversation, no
  inference needed.
- **`channel`** — present ⇒ the account is on PubNub; absent ⇒ legacy XMPP. Their code does
  `if (!conversation.channel) return;` before publishing, so this is a runtime signal, not a guess.

Message shape: `{id, text, from_self, timestamp, status, type, time_token}`. **`timestamp` is
milliseconds** (13 digits). `from_self` is a real boolean — no sender-name cross-referencing like
Click&Boat. `type` is `text` or `server-message`. No `payload` here (that's the PubNub publish).

Other endpoints:

```
GET /bff/messaging/conversation/{id}        → the conversation BARE, not wrapped in {"conversation":…}
GET /api/v3/instant-messaging/messages/unread  → {"unread_counter":N}    cheap global probe
GET /api/v3/instant-messaging/token        → 201 (not 200!) {"token":"…"} AT THE ROOT
                                             (guides say {"data":{"token"}}). PubNub PAM v3 token.
GET /bff/messaging/archived?page_size=30&max_messages=30    Pro accounts only
```

## Sending: there is no REST endpoint

The full `instant-messaging` table is `/conversation`, `/conversations/{archive,unarchive,translate}`,
`/privacy/user`, `/messages/unread`, `/archive/conversation/{id}/messages`, `/token`, plus
`bff/messaging/{inbox,archived,conversation}`. Nothing else. Chat is real time: legacy XMPP
(`wss://mongooseimprotool-prod.wallapop.com:443/ws-xmpp`, stanza.io) migrating to PubNub, chosen by
the Amplitude flag `paco_chat_migration`. Publishing to PubNub is plain HTTP, so you don't need a
persistent connection — but note nothing acknowledges delivery, so re-read the thread to confirm
instead of retrying blind.

## Finding things in the bundle

`es.wallapop.com/app/chat` is Angular, served from `web-static.wallapop.com/angular/es/main-*.js`.
`main.js` is only ~94 kB: the logic lives in **~561 lazy chunks** that must be resolved
**transitively** (8 rounds to close the graph). Get the script name from the page HTML, then:

```python
NAME_RE = re.compile(r'["\']?((?:chunk|main|polyfills)-[A-Z0-9]{8}\.js)["\']?')
# BFS from main-XXXXXXXX.js over https://web-static.wallapop.com/angular/es/,
# ThreadPoolExecutor(32) — the whole graph downloads in a few seconds.
```

Useful landmarks once you have the chunks:

- `chunk-JMQTD2HW.js` — endpoint constants (`api/v3/access/refresh`, `api/auth/federated-session`,
  `api/v3/access/{login,google,facebook,authorize}`), the header-name table (`Nd`), and the
  device-header interceptor with its per-path conditions.
- `chunk-WGXZ7CT5.js` — `AuthService`, the refresh flow, and the 401 response interceptor.
- `chunk-PDD2ZLXE.js` — the environment block: `baseUrl: "https://api.wallapop.com/"`,
  **`webseoBaseUrl: "/"`** (so `federated-session` is same-origin), CDN, feature-flag host,
  Braze/Amplitude/ThreatMetrix keys.
- No request signing on web. Searching `X-Signature`/HMAC/`signRequest` only hits AWS SigV4 (maps),
  CryptoJS inside the PubNub SDK, and `create-hmac` inside stanza.io. The `X-Signature` documented
  elsewhere belongs to the **mobile** API.

## Observing the refresh live (CDP)

The account's own tab renews every ~5 minutes, but if its token is still fresh nothing happens and
waiting is a trap. Don't break the cookie to force it — the front's failure path calls `logout()`.
Instead, run the request yourself from the page's own context so the browser attaches the httpOnly
cookies, and watch the `Set-Cookie` headers:

```python
sid = cdp("Target.attachToTarget", targetId=TID, flatten=True)["sessionId"]
cdp("Network.enable", session_id=sid)
cdp("Runtime.evaluate", session_id=sid, awaitPromise=True, returnByValue=True,
    expression="fetch('/api/auth/federated-session',{credentials:'include'}).then(r=>r.status)")
# Set-Cookie only shows up in Network.responseReceivedExtraInfo, not responseReceived.
cdp("Network.disable", session_id=sid); cdp("Target.detachFromTarget", sessionId=sid)
```

Two gotchas that cost time here:

- **Chrome profiles are separate browser contexts.** `Storage.getCookies` with no session returns
  the *default* context only, so a business-account profile looks like it has no Wallapop cookies at
  all. Group `Target.getTargets` page targets by `browserContextId` to find the right profile, then
  read cookies with `Network.getCookies` on a session attached to a tab in that context.
- httpOnly cookies never appear in `document.cookie`. Read them via CDP, and use
  `Page.getNavigationHistory` to tell your own tabs from the user's before closing anything.
