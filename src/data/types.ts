/** Shapes the UI needs. The HTTP mapping is documented in docs/frontend-api.md. */

export type Friend = {
  id: string
  name: string
  avatarUrl: string
}

export type Organizer = {
  id: string
  name: string
  /** Null until a club has a real logo. The UI draws initials from the name. */
  iconUrl: string | null
}

export type RecommendationReason = {
  /** Render this verbatim. The UI does not write recommendation copy. */
  text: string
}

export type FeedEvent = {
  id: string
  title: string
  /** ISO 8601 with a numeric offset. The UI formats it for display. */
  startsAt: string
  location: string
  description: string
  organizer: Organizer
  /** Club this event belongs to. May be absent from the viewer's selections. */
  clubId: string
  sourceLabel: string
  sourceUrl: string
  image: { url: string; alt: string } | null
  /** Friends who said they are going, in the order the backend sends. */
  friendsGoing: Friend[]
  /** Why this event is in the feed. Null when there is nothing extra to say. */
  reason: RecommendationReason | null
  saved: boolean
  going: boolean
}

export type Club = {
  id: string
  name: string
  iconUrl: string | null
}

export type Student = {
  id: string
  name: string
  email: string
}

export type Session = {
  student: Student
  clubIds: string[]
  onboardingComplete: boolean
  inviteUrl: string
}

export type SaveClubsInput = {
  clubIds: string[]
  onboardingComplete: boolean
}

/**
 * Replace the mock with a client that calls these operations over HTTP.
 * The UI only talks to this interface.
 */
export interface EventsApi {
  getSession(): Promise<Session>
  getClubs(): Promise<Club[]>
  saveClubs(input: SaveClubsInput): Promise<Session>
  /** Events in backend rank order. Do not sort or filter this list. */
  getFeed(): Promise<FeedEvent[]>
  /** Saved events in the order the backend returns. */
  getSaved(): Promise<FeedEvent[]>
  setSaved(eventId: string, saved: boolean): Promise<void>
  setGoing(eventId: string, going: boolean): Promise<void>
}
