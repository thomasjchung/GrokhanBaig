import type { EventsApi, FeedEvent, SaveClubsInput, Session } from "./types"

const LIVE_KEY = "sheet.live.v1"

type LiveFlags = {
  savedIds: string[]
  goingIds: string[]
}

function loadFlags(): LiveFlags {
  try {
    const raw = localStorage.getItem(LIVE_KEY)
    if (!raw) return { savedIds: [], goingIds: [] }
    const parsed = JSON.parse(raw) as Partial<LiveFlags>
    return {
      savedIds: Array.isArray(parsed.savedIds) ? parsed.savedIds.filter((id) => typeof id === "string") : [],
      goingIds: Array.isArray(parsed.goingIds) ? parsed.goingIds.filter((id) => typeof id === "string") : [],
    }
  } catch {
    return { savedIds: [], goingIds: [] }
  }
}

function saveFlags(flags: LiveFlags) {
  try {
    localStorage.setItem(LIVE_KEY, JSON.stringify(flags))
  } catch {
    // Private mode can block storage. The in-memory copy still serves this tab.
  }
}

let memory: LiveFlags = loadFlags()
let cached: FeedEvent[] | null = null
let cachedAt = 0

async function extras(): Promise<FeedEvent[]> {
  if (cached && Date.now() - cachedAt < 1500) return cached
  try {
    const response = await fetch("/api/campus/extras", { credentials: "include" })
    if (!response.ok) return cached ?? []
    const body = (await response.json()) as { events?: FeedEvent[] }
    cached = Array.isArray(body.events) ? body.events : []
    cachedAt = Date.now()
    return cached
  } catch {
    return cached ?? []
  }
}

function apply(event: FeedEvent, flags: LiveFlags): FeedEvent {
  return {
    ...event,
    saved: flags.savedIds.includes(event.id),
    going: flags.goingIds.includes(event.id),
  }
}

/**
 * Keeps the mock feed, then adds live Instagram events and the one Gmail event.
 */
export function withLive(base: EventsApi): EventsApi {
  return {
    async getSession(): Promise<Session> {
      const session = await base.getSession()
      try {
        const response = await fetch("/api/google/session", { credentials: "include" })
        if (!response.ok) return session
        const google = (await response.json()) as {
          connected?: boolean
          id?: number
          name?: string
          email?: string
        }
        if (!google.connected || !google.email || !google.name) return session
        return {
          ...session,
          student: { id: String(google.id), name: google.name, email: google.email },
        }
      } catch {
        return session
      }
    },

    getClubs: () => base.getClubs(),

    saveClubs: (input: SaveClubsInput) => base.saveClubs(input),

    async getFeed() {
      const [feed, live] = await Promise.all([base.getFeed(), extras()])
      const flags = memory
      const liveIds = new Set(live.map((event) => event.id))
      return [...live.map((event) => apply(event, flags)), ...feed.filter((event) => !liveIds.has(event.id))]
    },

    async getSaved() {
      const [saved, live] = await Promise.all([base.getSaved(), extras()])
      const flags = memory
      const byId = new Map(live.map((event) => [event.id, event]))
      const liveSaved = flags.savedIds.flatMap((id) => {
        const event = byId.get(id)
        return event ? [apply(event, flags)] : []
      })
      return [...liveSaved, ...saved]
    },

    async setSaved(eventId, saved) {
      const live = await extras()
      if (live.some((event) => event.id === eventId)) {
        const savedIds = memory.savedIds.filter((id) => id !== eventId)
        if (saved) savedIds.unshift(eventId)
        memory = { ...memory, savedIds }
        saveFlags(memory)
        cachedAt = 0
        return
      }
      await base.setSaved(eventId, saved)
    },

    async setGoing(eventId, going) {
      const live = await extras()
      if (live.some((event) => event.id === eventId)) {
        const goingIds = memory.goingIds.filter((id) => id !== eventId)
        if (going) goingIds.push(eventId)
        memory = { ...memory, goingIds }
        saveFlags(memory)
        cachedAt = 0
        return
      }
      await base.setGoing(eventId, going)
    },
  }
}
