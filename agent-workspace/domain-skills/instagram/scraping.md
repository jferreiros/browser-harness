# Instagram — scraping (hashtags + perfiles)

Requires a logged-in session (use the user's Chrome). Anonymous requests hit login walls immediately.

## Internal web API (fast path)

Both endpoints need header `x-ig-app-id: 936619743392459` and must be fetched **from a page context on instagram.com** (cookies do the auth):

- Hashtag: `GET /api/v1/tags/web_info/?tag_name=<tag>` — returns `top.sections` + `recent.sections` with medias. Slow (5-15s per tag). To extract authors, recursively walk the JSON for objects that have `user.username` alongside `like_count`/`comment_count` — the section layout nesting varies (`one_by_two_item`, clips, fill_items…), a recursive walk beats path-picking.
- Profile: `GET /api/v1/users/web_profile_info/?username=<user>` — returns `data.user` with `edge_followed_by.count`, `biography`, `category_name`, `is_business_account`, and last 12 posts with like/comment counts (good for engagement rate).

## Trap: js() await times out on these fetches

`js("(async () => { await fetch(...) })()")` times out the harness CDP socket because the API can take >10s. Use fire-and-forget + poll:

```python
js('window.__r = "pending"; (async () => { ... window.__r = result; })(); "started"')
# then poll js('window.__r === "pending" ? "pending" : "done"') every 1-2s
```

## Trap: profile API soft-blocks after ~20 rapid calls

After ~20 `web_profile_info` calls at 2s cadence, requests **hang forever** (no 429, no error — the fetch never resolves). Cooldown is >15 min and page reload doesn't clear it. The tag endpoint kept working while the profile endpoint was blocked — limits are per-endpoint-family.

## Fallback that sustains volume: page loads

Normal navigation is far more tolerant — 350+ profile page loads at ~4s cadence with zero blocks (same session where the API was throttled):

```python
goto_url("https://www.instagram.com/<user>/")
wait_for_load()
# counts: meta[property="og:description"] → "12.5K Followers, 300 Following, 210 Posts - ..."
# bio + category + name: document.querySelector("header").innerText
```

Parse K/M suffixes on the counts ("12.5K" → 12500). No per-post like counts via this route — combine with the likes captured from the hashtag sweep for a rough ER.

## Notes

- A username that is also a hashtag word (e.g. `decobarcelona`) can exist as an empty account — check `posts > 0` before trusting a profile.
- Renamed/deleted accounts return a page with no `og:description` counts — record as error and move on (~2-3% of hashtag authors).
- Hashtag top-posts skew toward businesses gaming tags; expect heavy filtering (in a 366-author deco sweep, only ~5% were genuine personal accounts).
