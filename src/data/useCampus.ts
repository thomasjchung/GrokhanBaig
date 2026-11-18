import { useCallback, useEffect, useState } from "react"
import { api } from "./index"
import type { Club, FeedEvent, SaveClubsInput, Session } from "./types"

export function useCampus() {
  const [session, setSession] = useState<Session | null>(null)
  const [clubs, setClubs] = useState<Club[]>([])
  const [feed, setFeed] = useState<FeedEvent[]>([])
  const [saved, setSaved] = useState<FeedEvent[]>([])
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    const [nextSession, nextClubs, nextFeed, nextSaved] = await Promise.all([
      api.getSession(),
      api.getClubs(),
      api.getFeed(),
      api.getSaved(),
    ])
    setSession(nextSession)
    setClubs(nextClubs)
    setFeed(nextFeed)
    setSaved(nextSaved)
    setError(null)
  }, [])

  useEffect(() => {
    let cancel = false
    refresh().catch((reason: unknown) => {
      if (cancel) return
      setError(reason instanceof Error ? reason.message : "The feed didn’t load.")
    })
    return () => {
      cancel = true
    }
  }, [refresh])

  async function saveClubs(input: SaveClubsInput) {
    await api.saveClubs(input)
    await refresh()
  }

  async function setEventSaved(eventId: string, next: boolean) {
    await api.setSaved(eventId, next)
    await refresh()
  }

  async function setEventGoing(eventId: string, next: boolean) {
    await api.setGoing(eventId, next)
    await refresh()
  }

  return {
    session,
    clubs,
    feed,
    saved,
    error,
    saveClubs,
    setEventSaved,
    setEventGoing,
  }
}
