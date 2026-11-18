# Frontend API contract

The UI is still on mocks. `src/data/index.ts` exports `api`, and today that is `mockApi`. When these routes exist, replace that binding with a client that implements `EventsApi` in `src/data/types.ts`. The screen code should not change.

Authentication, event ingestion, storage, friend relationships, and ranking belong to the backend. The frontend renders the feed order and the recommendation text it is given. It does not sort the feed, drop an event whose club was not selected, or invent lines like “Maya is going.”

The mock feed includes `rules-of-the-game` from Yale Film Archive with `reason.text` set to `Maya is going.` The sample student does not follow that club. That event must still appear, in the position the backend assigns.

Assumed transport: JSON over HTTP, session cookie issued by the backend. The browser client should use `credentials: "include"`. A `401` means the session is missing. The UI does not collect passwords. Paths below are suggestions.

Times are ISO 8601 strings with a numeric offset, interpreted in `America/New_York` by the UI.

## `GET /api/me`

```json
{
  "student": {
    "id": "sam-iyer",
    "name": "Sam Iyer",
    "email": "sam.iyer@yale.edu"
  },
  "clubIds": ["cross-campus", "whc", "yso", "beinecke", "music-office"],
  "onboardingComplete": false,
  "inviteUrl": "https://yale.events/i/k4m2"
}
```

`onboardingComplete` is false until the student finishes the club picker. `inviteUrl` is the friend link the profile copies. The backend issues it.

## `GET /api/clubs`

Club catalog, already in display order. `iconUrl` is null until a real logo exists. The UI then draws initials from the name.

```json
[
  { "id": "yso", "name": "Yale Symphony Orchestra", "iconUrl": null }
]
```

## `PUT /api/me/clubs`

Replaces the student’s club list. Used by the first-login picker and by later edits on the profile. Send ids in catalog order. An empty list is allowed after onboarding. The first successful picker submit sends `onboardingComplete: true`.

```json
{
  "clubIds": ["cross-campus", "whc", "yso"],
  "onboardingComplete": true
}
```

Response: the same body as `GET /api/me`.

Changing clubs does not tell the UI which events to show. The UI reloads `GET /api/feed` and renders that.

## `GET /api/feed`

Ordered event list. Index 0 is the first screen. The UI does not reorder or filter it.

```json
[
  {
    "id": "rules-of-the-game",
    "title": "The Rules of the Game",
    "startsAt": "2026-11-22T20:00:00-05:00",
    "location": "Humanities Quadrangle, Room L02",
    "description": "A 35mm screening of Jean Renoir’s 1939 film.",
    "organizer": {
      "id": "film",
      "name": "Yale Film Archive",
      "iconUrl": null
    },
    "clubId": "film",
    "sourceLabel": "web.library.yale.edu/film",
    "sourceUrl": "https://web.library.yale.edu/film/screenings",
    "image": {
      "url": "https://cdn.example/flyers/rules.jpg",
      "alt": "Screening room, the flyer for The Rules of the Game."
    },
    "friendsGoing": [
      {
        "id": "maya",
        "name": "Maya",
        "avatarUrl": "https://cdn.example/friends/maya.jpg"
      }
    ],
    "reason": { "text": "Maya is going." },
    "saved": false,
    "going": false
  }
]
```

Field notes:

- `image` is null for an email-only event with no flyer. The UI then uses a plain page instead of a photograph.
- `friendsGoing` is every friend who marked going, in the order to show their icons. It may be empty.
- `reason` is null when there is no extra line to show. When present, `reason.text` is rendered exactly, including punctuation.
- `reason` and `friendsGoing` are separate. A friend icon row can accompany the sentence, but the sentence is not built from the names.
- `saved` and `going` reflect the current student.
- `sourceUrl` may be an `https` link or a `mailto:` address.

## `GET /api/me/saved`

The same event shape, limited to saved events, in the order the backend wants the Saved tab to show. The reference UI puts the most recently saved event first only because the mock does. Do not assume that order.

## `PUT /api/events/:eventId/saved`

```json
{ "saved": true }
```

## `PUT /api/events/:eventId/going`

```json
{ "going": true }
```

Both are idempotent sets, not toggles with no body. Response `200` with the updated feed event (same shape as a `GET /api/feed` item) or `404` if the id is unknown. The reference UI calls the put, then reloads the feed and the saved list so order stays backend-owned.

## Errors

```json
{ "error": { "code": "unauthorized", "message": "Sign in required." } }
```

`401` for a missing session. `404` for an unknown event or club id. The UI surfaces `error.message` when a load fails.

## What the mock does locally

`src/data/mockApi.ts` stores club choices, saves, and going flags in `localStorage` under `yale-events.mock.v1`. That storage is not part of the contract. The sample student follows every club except Yale Film Archive, and the feed still includes the Film Archive screening.
