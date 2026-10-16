# Meetup — RSVP and public API

- **Public GraphQL API:** `POST https://www.meetup.com/gql2` needs no auth for search. `api.meetup.com/gql` returns 404. Use `recommendedEvents(filter:{lat,lon,topicCategoryId,startDateRange}, first, after)`. Category ids: 546 = Technology, 405 = Career & Business. Paginate on `pageInfo.hasNextPage`, because `totalCount` is per page. The search mixes in online events and events from other countries, so filter by `venue.city` or `venue.lat/lon`. The field is `lon`; `lng` breaks the query.
- **RSVP:** the "Attend" button in the sticky footer. There are 2 matching buttons; use the last visible one. Some hosts then show "Complete registration" with free-text questions (for example, an email for building access), then "Submit". Success shows "You're going" and an event-chat promo modal.
- **Full events:** the button changes to "Join waitlist" ("0 spots left"). Clicking it opens a **Meetup+ upsell** ("Try for free" starts a paid trial). "Continue with free plan" is a small link. Do not join waitlists unless the user asks for it.
- **Logged-in check:** the header shows an avatar instead of "Log in / Sign up".
