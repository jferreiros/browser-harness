# Luma — public API and registration

- `lu.ma` redirects (301) to `luma.com`. The APIs work on both `api.lu.ma` and `api.luma.com`.
- **City feed:** `GET /discover/get-paginated-events?discover_place_api_id=discplace-...`. Barcelona is `discplace-WcS4REeayDPXV4n`. It returns only about 20 featured events. Community events live in calendars.
- **Calendar feed:** `GET /calendar/get-items?calendar_api_id=cal-...&period=future&pagination_limit=50`, with `pagination_cursor`/`has_more`. Global calendars (for example Claude Community `cal-TOpA5LAFfuDeFpu`) span months and cities. Filter by `geo_address_info`, or by names like "Madrid | …".
- **Slug to event:** `GET /url?url=<slug>` returns `data.event`, `ticket_types`, `guest_count` and the calendar.
- **Trap:** responses can contain raw control characters. Use `json.loads(text, strict=False)`.
- **Trap:** `event.waitlist_status == "active"` only means a waitlist is enabled, even when registration is open. Use `waitlist_active` / `ticket_info.is_sold_out`.
- **Registration:** "Request to Join" (approval) or "Register" opens a modal with required custom questions and a terms checkbox. In a background tab the modal does not submit until you enable `Emulation.setFocusEmulationEnabled`. Verify with `fetch("https://api.luma.com/url?url=<slug>", {credentials:"include"})`. `data.guest_data.approval_status` is `pending_approval` or `approved`.
