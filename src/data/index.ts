import { mockApi } from "./mockApi"
import type { EventsApi } from "./types"

export type {
  Club,
  EventsApi,
  FeedEvent,
  Friend,
  Organizer,
  RecommendationReason,
  SaveClubsInput,
  Session,
  Student,
} from "./types"

/**
 * The only place the UI chooses an implementation.
 * Point this at an HTTP client when the API in docs/frontend-api.md is ready.
 */
export const api: EventsApi = mockApi
