import type {
  Club,
  EventsApi,
  FeedEvent,
  Friend,
  SaveClubsInput,
  Session,
} from "./types"

const STORAGE_KEY = "yale-events.mock.v1"

const friends = {
  maya: { id: "maya", name: "Maya", avatarUrl: "/friends/maya.jpg" },
  alex: { id: "alex", name: "Alex", avatarUrl: "/friends/alex.jpg" },
  jordan: { id: "jordan", name: "Jordan", avatarUrl: "/friends/jordan.jpg" },
} satisfies Record<string, Friend>

const clubs: Club[] = [
  { id: "cross-campus", name: "Cross Campus Programs", iconUrl: null },
  { id: "whc", name: "Whitney Humanities Center", iconUrl: null },
  { id: "yso", name: "Yale Symphony Orchestra", iconUrl: null },
  { id: "beinecke", name: "Beinecke Library", iconUrl: null },
  { id: "music-office", name: "Yale School of Music", iconUrl: null },
  { id: "film", name: "Yale Film Archive", iconUrl: null },
]

/**
 * Rank order is fixed here on purpose. The film screening stays in the feed
 * even when Yale Film Archive is not one of the viewer's clubs, because Maya
 * is going. The UI must render this list as given.
 */
const catalog: FeedEvent[] = [
  {
    id: "noon-cross-campus",
    title: "Noon on Cross Campus",
    startsAt: "2026-11-23T12:00:00-05:00",
    location: "Cross Campus",
    description:
      "A short outdoor concert between classes. Blankets are welcome. If it rains, the group moves under the walkway by Berkeley College.",
    organizer: { id: "cross-campus", name: "Cross Campus Programs", iconUrl: null },
    clubId: "cross-campus",
    sourceLabel: "yale.edu",
    sourceUrl: "https://www.yale.edu/",
    image: {
      url: "/events/bright.jpg",
      alt: "Sunlit lawn and stone buildings, the flyer for Noon on Cross Campus.",
    },
    friendsGoing: [],
    reason: null,
    saved: false,
    going: false,
  },
  {
    id: "what-the-university-owes",
    title:
      "What the University Owes Its City, Its Students, and the Archive It Keeps",
    startsAt: "2026-11-24T17:00:00-05:00",
    location: "Whitney Humanities Center",
    description:
      "A public lecture on what a university owes the city around it, the students passing through, and the collections it holds in trust. Questions follow the talk.",
    organizer: { id: "whc", name: "Whitney Humanities Center", iconUrl: null },
    clubId: "whc",
    sourceLabel: "whc.yale.edu",
    sourceUrl: "https://whc.yale.edu/",
    image: {
      url: "/events/beinecke.jpg",
      alt: "A marble library interior, the flyer for the Whitney Humanities Center lecture.",
    },
    friendsGoing: [],
    reason: null,
    saved: false,
    going: false,
  },
  {
    id: "rules-of-the-game",
    title: "The Rules of the Game",
    startsAt: "2026-11-22T20:00:00-05:00",
    location: "Humanities Quadrangle, Room L02",
    description:
      "A 35mm screening of Jean Renoir’s 1939 film, with a short introduction from the archive. One hundred ten minutes, in French with English subtitles. Free and open to the public.",
    organizer: { id: "film", name: "Yale Film Archive", iconUrl: null },
    clubId: "film",
    sourceLabel: "web.library.yale.edu/film",
    sourceUrl: "https://web.library.yale.edu/film/screenings",
    image: {
      url: "/events/film.jpg",
      alt: "A dark screening room facing a lit screen, the flyer for The Rules of the Game.",
    },
    friendsGoing: [friends.maya],
    reason: { text: "Maya is going." },
    saved: false,
    going: false,
  },
  {
    id: "brahms-bartok",
    title: "Brahms and Bartók",
    startsAt: "2026-11-20T19:30:00-05:00",
    location: "Woolsey Hall",
    description:
      "The Yale Symphony Orchestra plays Brahms’s Variations on a Theme by Haydn and Bartók’s Concerto for Orchestra. Doors open at 6:45 p.m. Yale students enter with an ID.",
    organizer: { id: "yso", name: "Yale Symphony Orchestra", iconUrl: null },
    clubId: "yso",
    sourceLabel: "yso.yale.edu",
    sourceUrl: "https://yso.yale.edu/",
    image: {
      url: "/events/yso.jpg",
      alt: "A concert hall with an orchestra on stage, the flyer for Brahms and Bartók.",
    },
    friendsGoing: [friends.alex, friends.jordan],
    reason: { text: "Alex and Jordan are going." },
    saved: false,
    going: false,
  },
  {
    id: "chamber-rehearsal",
    title: "Chamber rehearsal moved",
    startsAt: "2026-11-25T16:10:00-05:00",
    location: "Hendrie Hall, Room 101",
    description:
      "Sent by email this morning. Wednesday’s chamber rehearsal is no longer in Sprague Hall. Same music, same hour, Hendrie Hall room 101.",
    organizer: { id: "music-office", name: "Yale School of Music", iconUrl: null },
    clubId: "music-office",
    sourceLabel: "music-office@yale.edu",
    sourceUrl: "mailto:music-office@yale.edu",
    image: null,
    friendsGoing: [],
    reason: null,
    saved: false,
    going: false,
  },
]

type MockState = {
  clubIds: string[]
  onboardingComplete: boolean
  savedIds: string[]
  goingIds: string[]
}

const defaultState = (): MockState => ({
  clubIds: ["cross-campus", "whc", "yso", "beinecke", "music-office"],
  onboardingComplete: false,
  savedIds: [],
  goingIds: [],
})

const student = {
  id: "sam-iyer",
  name: "Sam Iyer",
  email: "sam.iyer@yale.edu",
}

const inviteUrl = "https://yale.events/i/k4m2"

function loadState(): MockState {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return defaultState()
    const parsed = JSON.parse(raw) as Partial<MockState>
    const base = defaultState()
    return {
      clubIds: Array.isArray(parsed.clubIds) ? parsed.clubIds.filter((id) => typeof id === "string") : base.clubIds,
      onboardingComplete: Boolean(parsed.onboardingComplete),
      savedIds: Array.isArray(parsed.savedIds) ? parsed.savedIds.filter((id) => typeof id === "string") : [],
      goingIds: Array.isArray(parsed.goingIds) ? parsed.goingIds.filter((id) => typeof id === "string") : [],
    }
  } catch {
    return defaultState()
  }
}

let state = loadState()

function persist() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
  } catch {
    // Private mode can block storage. The in-memory copy still serves this tab.
  }
}

function withFlags(event: FeedEvent, state: MockState): FeedEvent {
  return {
    ...event,
    organizer: { ...event.organizer },
    image: event.image ? { ...event.image } : null,
    friendsGoing: event.friendsGoing.map((friend) => ({ ...friend })),
    reason: event.reason ? { text: event.reason.text } : null,
    saved: state.savedIds.includes(event.id),
    going: state.goingIds.includes(event.id),
  }
}

function sessionFrom(current: MockState): Session {
  return {
    student: { ...student },
    clubIds: [...current.clubIds],
    onboardingComplete: current.onboardingComplete,
    inviteUrl,
  }
}

export const mockApi: EventsApi = {
  async getSession() {
    return sessionFrom(state)
  },

  async getClubs() {
    return clubs.map((club) => ({ ...club }))
  },

  async saveClubs(input: SaveClubsInput) {
    const known = new Set(clubs.map((club) => club.id))
    state = {
      ...state,
      clubIds: clubs.map((club) => club.id).filter((id) => input.clubIds.includes(id) && known.has(id)),
      onboardingComplete: input.onboardingComplete || state.onboardingComplete,
    }
    persist()
    return sessionFrom(state)
  },

  async getFeed() {
    return catalog.map((event) => withFlags(event, state))
  },

  async getSaved() {
    const byId = new Map(catalog.map((event) => [event.id, event]))
    return state.savedIds.flatMap((id) => {
      const event = byId.get(id)
      return event ? [withFlags(event, state)] : []
    })
  },

  async setSaved(eventId, saved) {
    const savedIds = state.savedIds.filter((id) => id !== eventId)
    if (saved) savedIds.unshift(eventId)
    state = { ...state, savedIds }
    persist()
  },

  async setGoing(eventId, going) {
    const goingIds = state.goingIds.filter((id) => id !== eventId)
    if (going) goingIds.push(eventId)
    state = { ...state, goingIds }
    persist()
  },
}
