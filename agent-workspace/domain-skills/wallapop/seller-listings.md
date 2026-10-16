# Wallapop — check a seller's listings and a price change

Verified 2026-10-16 on a business seller account. Read-only checks; all public, no login.

## List one seller's live items

```
GET https://api.wallapop.com/api/v3/users/{user_hash}/items
→ {"data":[{"id","title","price":{"amount","currency"},"web_slug",…}], "meta":{…}}
```

- `user_hash` is the `hashed_sub` claim of the seller's access token (see auth-and-messaging-api.md).
- No auth needed. Send `X-DeviceOS: 0` and `Accept: application/json`.
- The list also holds rental or service ads, so match items by title, not by position.

## Confirm a price change happened

`GET /api/v3/items/{hashed_id}` shows a price drop in two fields:

- `discount: {"previous_price":{"amount":…}, "percentage":…}` — present only after a drop.
- `modified_date` (unix seconds) moves to the time of the edit.

Check these before you edit. Someone else (the owner, another agent) may have done the change
already, and a second save is a needless write.

## Trap: the description keeps the old price

Sellers often write the price in the free text (`"… 18.000 €. Entrega en …"`).
A price edit changes only `price`. The public page then shows the new price at the top and the
old one in the description. Grep `description.original` for `€` after every price change and
tell the owner. Do not edit the description unless the owner asks.

## Public page check

`es.wallapop.com/item/{web_slug}` is server-rendered enough for `http_get`. The HTML holds
`"amount":<new>` and the formatted price. Old prices in the same HTML come from the
description, not from a stale cache.

## Traps in the browser

- A Chrome **profile** is not a CDP browser context you can create tabs in.
  `Target.createTarget(browserContextId=<profile ctx>)` fails with "Failed to find browser
  context". To act as the profile's account, attach to a tab that is already open in it.
- The daemon session is shared. Another agent can move it to its own tab between two of your
  calls, and your `js(...)` then runs on the wrong page. For a multi-step job in someone
  else's tab, attach with `Target.attachToTarget` and pass your own `session_id` to
  `Runtime.evaluate` on every call.
