# SamBoat — owner reservation pages

Owner side of a booking request. Captured 2026-07-27 on a live owner account (`samboat.es`).

**SamBoat is not an API.** Unlike Click&Boat's JSON endpoints, everything here is
server-rendered HTML with classic form POSTs and a Laravel-style `_token` CSRF field. Any
automation must GET the page, scrape `_token`, then POST.

## URLs

- Requests list: `https://www.samboat.es/private/reservation?tab=ongoing&page=1`
- One request: `https://www.samboat.es/private/reservation/{reservationId}?tab=ongoing&page=1`

Status pipeline shown on the page: `Solicitud → Preaprobada → Pagado → En curso → Finalizado`.

## Forms on the reservation page

### Send a message
```
POST /private/reservation/{reservationId}
Content-Type: application/x-www-form-urlencoded

_token={csrf}&content={text}
```
Returns HTML (`Accept: text/html`), not JSON. The `_token` is a hidden input, 40 chars.

### Make an offer (change price, dates or boat)
Revealed by the "Hacer una oferta" link, which expands an inline form — no navigation.
```
POST /private/reservation/{reservationId}/make-offer
Content-Type: application/x-www-form-urlencoded

_token={csrf}
start={YYYY-MM-DD}
end={YYYY-MM-DD}
halfday={0|1}
half_day_slot={...}
custom_half_day_slot={...}
custom_half_day_slot_period={...}
price={number}
content={message}
```

## Auth

Session cookie **plus** the per-page `_token`. Scrape `_token` from the hidden input on every
GET; it is form-scoped, so read it from the form you are about to submit.

## reCAPTCHA

A `g-recaptcha-response` textarea exists in the DOM (reCAPTCHA v3, injected globally and
invisible) but it is **not inside** either the message form or the offer form. Confirmed by
mapping each `<form>` to its own descendants:

```js
[...document.querySelectorAll('form')].map(f => ({
  action: f.action,
  fields: [...f.querySelectorAll('input,select,textarea')].map(e => e.name).filter(Boolean),
  recaptcha: !!f.querySelector('[name="g-recaptcha-response"], .g-recaptcha, [data-sitekey]')
}))
```
Both come back `recaptcha: false`. Don't assume a page-level captcha element gates a form —
check containment.

## Discovering a form without submitting it

Submitting an offer or a message on a live account touches a real customer. Read the form
definition out of the DOM instead (the snippet above) — action, method and field names, with
zero requests. Use interception + abort only when you also need the exact encoding:

```python
cdp("Fetch.enable", patterns=[{"urlPattern": "*samboat.*", "requestStage": "Request"}])
# POST -> record, then cdp("Fetch.failRequest", requestId=rid, errorReason="Aborted")
# GET  -> cdp("Fetch.continueRequest", requestId=rid)
cdp("Fetch.disable")
```

## Traps

- `scroll()` on this page can time out on the screenshot round-trip; `js("window.scrollTo(0,N)")`
  is more reliable.
- The reservation page is ~2500 px tall; the composer sits around page-y 665 and its `Enviar`
  button around page-y 799. Locate them via `getBoundingClientRect()` + `window.scrollY`
  rather than guessing.
- The "Hacer una oferta" link expands an inline form, it does not navigate. The URL stays the
  same, so don't wait for a navigation event.
