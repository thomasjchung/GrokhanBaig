import { useCallback, useEffect, useState } from "react"
import { ClubPicker } from "./components/ClubPicker"
import { EventFeed } from "./components/EventFeed"
import { InfoSheet } from "./components/InfoSheet"
import { ProfileScreen } from "./components/ProfileScreen"
import { SavedCalendar } from "./components/SavedCalendar"
import { SignIn } from "./components/SignIn"
import { TabBar, type Tab } from "./components/TabBar"
import type { FeedEvent } from "./data/types"
import { useCampus } from "./data/useCampus"

const SKIP_KEY = "sheet.skip-google.v2"

export function App() {
  const campus = useCampus()
  const [tab, setTab] = useState<Tab>("feed")
  const [infoId, setInfoId] = useState<string | null>(null)
  const [feedIndex, setFeedIndex] = useState(0)
  const [gate, setGate] = useState<"loading" | "signin" | "app">("loading")
  const [signNotice, setSignNotice] = useState<string | null>(null)

  const onFeedIndex = useCallback((index: number) => setFeedIndex(index), [])

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const google = params.get("google")
    if (google) {
      window.history.replaceState({}, "", "/")
    }
    if (google === "denied") {
      setSignNotice("Google did not grant access.")
      setGate("signin")
      return
    }
    if (google === "connected") {
      window.localStorage.removeItem(SKIP_KEY)
      setGate("app")
      return
    }
    let cancel = false
    fetch("/api/google/session", { credentials: "include" })
      .then((response) => (response.ok ? response.json() : { connected: false }))
      .then((body: { connected?: boolean }) => {
        if (cancel) return
        if (body.connected || window.localStorage.getItem(SKIP_KEY) === "1") setGate("app")
        else setGate("signin")
      })
      .catch(() => {
        if (cancel) return
        setGate(window.localStorage.getItem(SKIP_KEY) === "1" ? "app" : "signin")
      })
    return () => {
      cancel = true
    }
  }, [])

  const infoEvent =
    campus.feed.find((event) => event.id === infoId) ??
    campus.saved.find((event) => event.id === infoId) ??
    null

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (infoEvent) return
      if (tab !== "feed") return
      if (
        event.key !== "ArrowDown" &&
        event.key !== "ArrowUp" &&
        event.key !== "PageDown" &&
        event.key !== "PageUp"
      ) {
        return
      }
      const feed = document.querySelector(".feed")
      if (!(feed instanceof HTMLElement)) return
      event.preventDefault()
      const height = feed.clientHeight
      if (height === 0) return
      const count = campus.feed.length
      const index = Math.round(feed.scrollTop / height)
      const direction = event.key === "ArrowDown" || event.key === "PageDown" ? 1 : -1
      const next = Math.max(0, Math.min(count - 1, index + direction))
      const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches
      feed.scrollTo({ top: next * height, behavior: reduceMotion ? "auto" : "smooth" })
    }

    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [campus.feed.length, infoEvent, tab])

  function selectTab(next: Tab) {
    setInfoId(null)
    setTab(next)
  }

  function returnToSignIn() {
    window.localStorage.removeItem(SKIP_KEY)
    setInfoId(null)
    setSignNotice(null)
    setGate("signin")
  }

  if (campus.error) {
    return (
      <main className="app">
        <div className="page">
          <div className="page-inner">
            <p>{campus.error}</p>
          </div>
        </div>
      </main>
    )
  }

  if (gate === "loading" || !campus.session) return <main className="app" />

  if (gate === "signin") {
    return (
      <SignIn
        notice={signNotice}
        onDemo={() => {
          window.localStorage.setItem(SKIP_KEY, "1")
          setGate("app")
        }}
      />
    )
  }

  if (!campus.session.onboardingComplete) {
    return (
      <main className="app">
        <ClubPicker
          clubs={campus.clubs}
          initialIds={campus.session.clubIds}
          onContinue={(clubIds) => campus.saveClubs({ clubIds, onboardingComplete: true })}
          onSignIn={returnToSignIn}
        />
      </main>
    )
  }

  const surface = visibleSurface(tab, campus.feed, feedIndex)

  return (
    <main className="app">
      <TabBar tab={tab} surface={surface} onChange={selectTab} />
      {tab === "feed" ? (
        <EventFeed
          events={campus.feed}
          onIndex={onFeedIndex}
          onSave={(event) => void campus.setEventSaved(event.id, !event.saved)}
          onGoing={(event) => void campus.setEventGoing(event.id, !event.going)}
          onInfo={(event) => setInfoId(event.id)}
        />
      ) : null}
      {tab === "saved" ? (
        campus.saved.length === 0 ? (
          <div className="page">
            <div className="page-inner with-tabs empty-saved">
              <p>Nothing saved yet.</p>
            </div>
          </div>
        ) : (
          <SavedCalendar
            events={campus.saved}
            onSave={(event) => void campus.setEventSaved(event.id, !event.saved)}
            onInfo={(event) => setInfoId(event.id)}
          />
        )
      ) : null}
      {tab === "profile" ? (
        <ProfileScreen
          session={campus.session}
          clubs={campus.clubs}
          onClubs={(clubIds) => campus.saveClubs({ clubIds, onboardingComplete: true })}
          onSignIn={returnToSignIn}
        />
      ) : null}
      {infoEvent ? <InfoSheet event={infoEvent} onClose={() => setInfoId(null)} /> : null}
    </main>
  )
}

function visibleSurface(tab: Tab, feed: FeedEvent[], feedIndex: number): "photo" | "paper" {
  if (tab === "profile" || tab === "saved") return "paper"
  const event = feed[feedIndex]
  return event?.image ? "photo" : "paper"
}
