# Wallapop — public search and item API (no login)

Read-only. Verified 2026-09-01 with plain `http_get` from a Mac, no cookies, no proxy.
No antibot on `api.wallapop.com`. The item **pages** on `es.wallapop.com` are a Next.js SPA and
do not expose `og:image`, so do not scrape the HTML for photos: use the API.

## Search

```
GET https://api.wallapop.com/api/v3/search
  ?source=search_box
  &keywords=quicksilver+commander+600
  &latitude=41.0713&longitude=1.0576          # centre of the radius (Cambrils here)
  &order_by=price_low_to_high                 # or newest, distance, price_high_to_low
  &min_sale_price=8000&max_sale_price=25000
```

Headers that work: `User-Agent: Mozilla/5.0`, `Accept: application/json`,
`Accept-Language: es-ES`, `X-DeviceOS: 0`. Without `X-DeviceOS` you can get a 403 on some edges.

Response shape:

```
data.section.payload.items[]  →  { id, title, price.amount, location.city, web_slug,
                                   images[0].urls.{small,medium,big} }
```

- `id` is the **hashed** id (`pj9m85dpv26e`). The numeric suffix in `web_slug`
  (`…-1139991785`) is a different id and is not accepted by the item endpoint.
- Item URL for humans: `https://es.wallapop.com/item/{web_slug}`.
- Keyword search is fuzzy and category-blind: "sea ray" returns Pokémon cards and cars.
  Filter by title on your side. Boats live under taxonomy `12485` (Otros) or `12579`
  (Deporte y ocio), so a category filter does not help.

## Item detail

```
GET https://api.wallapop.com/api/v3/items/{hashed_id}
```

Keys: `title.original`, `description.original` (**dicts**, not strings), `price.cash.amount`,
`location.city`, `modified_date` (unix seconds), `images[]` with `urls.{small,medium,big}`,
`slug`, `share_url`. No structured attributes for boats: year, seats and engine are only in
the free-text description.

`/items/{id}/detail` returns 404. A removed listing returns **404 on the web page and on the API**.

## Photos

CDN URLs look like
`https://cdn.wallapop.com/images/10420/xx/yy/__/c10420p{numeric}/i{imageId}.jpg?pictureSize=W320`.
Swap `pictureSize` for `W640` or `W800` for a larger file. Plain `urllib` with a
`User-Agent` header downloads them.

## Trap: listings disappear without notice

Three of fourteen boat listings used in a report went 404 within two weeks. Before you show a
deck or PDF that links to listings, re-check every item URL (a 404 on `http_get` is enough).
