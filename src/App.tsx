import { useCallback, useEffect, useState } from "react"
import { ClubPicker } from "./components/ClubPicker"
import { DailyEvent } from "./components/DailyEvent"
import { EventFeed } from "./components/EventFeed"
import { InfoSheet } from "./components/InfoSheet"
import { ProfileScreen } from "./components/ProfileScreen"
import { TabBar, type Tab } from "./components/TabBar"
import type { FeedEvent } from "./data/types"
import { useCampus } from "./data/useCampus"

export function App() {
  const campus = useCampus()
  const [tab, setTab] = useState<Tab>("feed")
  const [infoId, setInfoId] = useState<string | null>(null)
  const [feedIndex, setFeedIndex] = useState(0)
  const [savedIndex, setSavedIndex] = useState(0)
  const [dailyOpen, setDailyOpen] = useState(false)

  const onFeedIndex = useCallback((index: number) => setFeedIndex(index), [])
  const onSavedIndex = useCallback((index: number) => setSavedIndex(index), [])

  const infoEvent =
    campus.feed.find((event) => event.id === infoId) ??
    campus.saved.find((event) => event.id === infoId) ??
    null

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (infoEvent || dailyOpen) return
      if (tab !== "feed" && tab !== "saved") return
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
      const count = tab === "feed" ? campus.feed.length : campus.saved.length
      const index = Math.round(feed.scrollTop / height)
      const direction = event.key === "ArrowDown" || event.key === "PageDown" ? 1 : -1
      const next = Math.max(0, Math.min(count - 1, index + direction))
      const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches
      feed.scrollTo({ top: next * height, behavior: reduceMotion ? "auto" : "smooth" })
    }

    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [campus.feed.length, campus.saved.length, dailyOpen, infoEvent, tab])

  function selectTab(next: Tab) {
    setInfoId(null)
    setDailyOpen(false)
    setTab(next)
  }

  function toggleDaily() {
    setInfoId(null)
    setDailyOpen((open) => !open)
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

  if (!campus.session) return <main className="app" />

  if (!campus.session.onboardingComplete) {
    return (
      <main className="app">
        <ClubPicker
          clubs={campus.clubs}
          initialIds={campus.session.clubIds}
          onContinue={(clubIds) => campus.saveClubs({ clubIds, onboardingComplete: true })}
        />
      </main>
    )
  }

  const surface = dailyOpen ? "paper" : visibleSurface(tab, campus.feed, campus.saved, feedIndex, savedIndex)

  return (
    <main className="app">
      <div className={surface === "paper" ? "chrome on-paper" : "chrome"}>
        <button
          type="button"
          className="daily-link"
          aria-current={dailyOpen ? "page" : undefined}
          onClick={toggleDaily}
        >
          <span className="daily-link-label">Daily Event!</span>
        </button>
        <TabBar tab={dailyOpen ? null : tab} onChange={selectTab} />
        <span className="chrome-spacer" aria-hidden="true">
          Daily Event!
        </span>
      </div>
      <div className="stage" hidden={dailyOpen}>
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
            <EventFeed
              events={campus.saved}
              onIndex={onSavedIndex}
              onSave={(event) => void campus.setEventSaved(event.id, !event.saved)}
              onGoing={(event) => void campus.setEventGoing(event.id, !event.going)}
              onInfo={(event) => setInfoId(event.id)}
            />
          )
        ) : null}
        {tab === "profile" ? (
          <ProfileScreen
            session={campus.session}
            clubs={campus.clubs}
            onClubs={(clubIds) => campus.saveClubs({ clubIds, onboardingComplete: true })}
          />
        ) : null}
      </div>
      {dailyOpen ? <DailyEvent name={campus.session.student.name} /> : null}
      {infoEvent ? <InfoSheet event={infoEvent} onClose={() => setInfoId(null)} /> : null}
    </main>
  )
}

function visibleSurface(
  tab: Tab,
  feed: FeedEvent[],
  saved: FeedEvent[],
  feedIndex: number,
  savedIndex: number,
): "photo" | "paper" {
  if (tab === "profile") return "paper"
  if (tab === "saved") {
    const event = saved[savedIndex]
    return event?.image ? "photo" : "paper"
  }
  const event = feed[feedIndex]
  return event?.image ? "photo" : "paper"
}
