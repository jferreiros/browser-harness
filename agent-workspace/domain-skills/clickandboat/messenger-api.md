# Click&Boat — private messenger API

Owner-side messaging on the pro dashboard. There is **no public API**; the front end talks to
a private one that you can replay with the session cookie. Captured 2026-07-27 against a live
owner account.

## URLs

- Inbox: `https://www.clickandboat.com/messenger?filter=all` — redirects to the newest
  conversation, so the list itself is **server-rendered HTML**, not an API call. Scrape the
  left column or keep a set of known conversation ids.
- One conversation: `https://www.clickandboat.com/messenger/{conversationId}?filter=all`

## Endpoints

### Read a whole thread — the useful one
```
POST /api/v3/TranslateMessages
Content-Type: application/x-www-form-urlencoded
target_lang=es&id={conversationId}&formatHtml=false
```
Returns every message in the thread, guest messages included:
```json
{"status":true,"code":200,"message":null,
 "data":[{"id":44936775,"message":"Hola Claudio, me interesa tu embarcación…","disclaimer":"es"}]}
```
Despite the name it is the cheapest way to pull thread content. `target_lang` also gives you
the translation for free.

### Poll for new messages
```
GET /api/v6/messenger/chat/{conversationId}?lastMessageId={id}&lastEventId={id}&_locale=es
```
```json
{"lastMessageReadAt":"2026-07-27T17:40:40+02:00","pollingChatInterval":5000,
 "pollingChatDuration":90000,"unreadConversationCount":1}
```
The front polls this every 5 s (`pollingChatInterval`) for 90 s (`pollingChatDuration`) while a
chat is open. Deltas come back when `lastMessageId` is behind. `unreadConversationCount` is a
cheap global "is there anything new" probe — poll it on one known conversation instead of
scraping the inbox.

### Send a message
```
POST /api/v6/messenger/chat/{conversationId}/message/send?_locale=es
Content-Type: application/json
{"content":"texto plano"}
```

## Auth

**Session cookie only — no CSRF token.** The send request carries:

| Header | Value |
|---|---|
| `Cookie` | session cookie (~3.9 KB) |
| `Content-Type` | `application/json` |
| `Origin` | `https://www.clickandboat.com` |
| `Referer` | `https://www.clickandboat.com/messenger/{conversationId}?filter=all` |
| `Accept` | `application/json, text/plain, */*` |

Send `Origin` and `Referer` — the server may check them. There is no `X-CSRF-Token`,
`X-XSRF-Token` or bearer header, so a stored cookie jar is enough to replay both read and write.

## Capturing a write endpoint without writing

Sending a test message on a real account means messaging a real customer. Don't. Intercept the
request in Chrome and abort it before it leaves:

```python
cdp("Fetch.enable", patterns=[{"urlPattern": "*clickandboat.com*", "requestStage": "Request"}])
# ... drive the UI: click composer, type, click send ...
# in the drain loop, on Fetch.requestPaused:
#   POST -> record request, then cdp("Fetch.failRequest", requestId=rid, errorReason="Aborted")
#   GET  -> cdp("Fetch.continueRequest", requestId=rid)
cdp("Fetch.disable")
```
Pattern-match the whole domain, not just the endpoint you expect: anything unmatched goes
straight to the server. Reload afterwards — the composer keeps the typed text.

## Traps

- `/messenger` with no id **redirects** to the newest conversation. Don't treat it as a list API.
- Opening a conversation **marks it read** and clears the unread badge. Reading through the UI
  has a visible side effect for the owner; the API calls above do not.
- The page fires a lot of third-party analytics (TikTok, Criteo, Reddit, Clarity, Sentry).
  Filter to `clickandboat.com` when capturing or the signal drowns.
- Frontend bundles do **not** contain the `/api/v6/messenger/...` strings in cleartext, so
  grepping the JS finds nothing. Capture the network instead.
- The composer is a plain input; `content` is plain text, not HTML.

## Booking-request actions (owner side)

A pending request shows a **Preaprobar** button and a custom-offer form in the right-hand
"Detalles" panel.

### Pre-approve
```
POST /messenger/request-details/prospective/{prospectiveId}/pre-accept
(no body)
```
`prospectiveId` is **not** the conversation id — conversation `7642221` mapped to prospective
`8440574`. Read it from the request-details panel.

### Send a customized offer
```
POST /api/v6/customized-offer/create?_locale=es
Content-Type: application/json

{"productId":204215,"sourceConversationId":7642221,
 "startDate":"2026-08-19 09:30:00.000000","endDate":"2026-08-19 18:00:00.000000",
 "expirationDate":"2026-07-30 20:27:15.275974","amount":280,"extras":[]}
```
`productId` is the listing. Dates are `YYYY-MM-DD HH:MM:SS.ffffff`, **not** ISO-8601.
`expirationDate` is computed client-side (3 days out in the capture). `amount` is the total
in euros. The button is labelled "Enviar oferta especial"; the panel link "Crear una nueva
oferta personalizada" only expands the form.

## Click&Boat runs its own AI assistant

Messages authored by **"Asistente IA"** appear in owner threads, answering guests before the
owner does — including quoting a price. The owner gets edit/delete controls on them.

Any bot you build has to account for it or the guest gets two answers, potentially with
different prices. Detect `Asistente IA` as a message author and decide explicitly whether to
stay quiet, escalate, or take over.

## Coordinate clicks miss in the Détails panel

`click_at_xy` on the "Preabrobar" / offer buttons did nothing on a 1512×718 viewport with a
2× DPR screenshot. Clicking through the DOM is reliable:

```python
js("""(()=>{const b=[...document.querySelectorAll('button,a')]
  .find(e=>/preabrobar/i.test(e.innerText||''));if(b){b.click();return true}return false})()""")
```
Note the label is spelled **"Preabrobar"** in the ES locale (typo in their UI) — match loosely.
