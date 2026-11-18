import { useState } from "react"
import type { FeedEvent } from "../data/types"
import { formatWhen } from "../formatWhen"

const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]

function nyKey(iso: string) {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return ""
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "America/New_York",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(date)
  return parts
}

function weekdayIndex(year: number, month: number, day: number) {
  const date = new Date(Date.UTC(year, month - 1, day, 17, 0, 0))
  const name = new Intl.DateTimeFormat("en-US", {
    timeZone: "America/New_York",
    weekday: "short",
  }).format(date)
  const index = WEEKDAYS.indexOf(name)
  return index < 0 ? 0 : index
}

function monthLabel(year: number, month: number) {
  const date = new Date(Date.UTC(year, month - 1, 1, 17, 0, 0))
  return new Intl.DateTimeFormat("en-US", {
    timeZone: "America/New_York",
    month: "long",
    year: "numeric",
  }).format(date)
}

function dayLabel(key: string) {
  const [year, month, day] = key.split("-").map(Number)
  const date = new Date(Date.UTC(year, month - 1, day, 17, 0, 0))
  return new Intl.DateTimeFormat("en-US", {
    timeZone: "America/New_York",
    weekday: "long",
    month: "long",
    day: "numeric",
  }).format(date)
}

function shiftMonth(year: number, month: number, delta: number) {
  const next = new Date(Date.UTC(year, month - 1 + delta, 1, 17, 0, 0))
  return { year: next.getUTCFullYear(), month: next.getUTCMonth() + 1 }
}

export function SavedCalendar({
  events,
  onSave,
  onInfo,
}: {
  events: FeedEvent[]
  onSave: (event: FeedEvent) => void
  onInfo: (event: FeedEvent) => void
}) {
  const grouped = new Map<string, FeedEvent[]>()
  for (const event of events) {
    const key = nyKey(event.startsAt)
    if (!key) continue
    const list = grouped.get(key) ?? []
    list.push(event)
    grouped.set(key, list)
  }
  const savedDays = [...grouped.keys()].sort()
  const [selected, setSelected] = useState<string | null>(null)
  const active = selected ?? savedDays[0] ?? nyKey(new Date().toISOString())
  const [yearText, monthText] = active.split("-")
  const initial = { year: Number(yearText), month: Number(monthText) }
  const [visible, setVisible] = useState(initial)
  const daysInMonth = new Date(visible.year, visible.month, 0).getDate()
  const pad = weekdayIndex(visible.year, visible.month, 1)
  const cells: Array<number | null> = [...Array(pad).fill(null), ...Array.from({ length: daysInMonth }, (_, index) => index + 1)]
  const dayEvents = grouped.get(active) ?? []

  return (
    <div className="page">
      <div className="page-inner with-tabs">
        <h1>Saved</h1>
        <div className="calendar-head">
          <h2>{monthLabel(visible.year, visible.month)}</h2>
          <div className="calendar-nav">
            <button
              type="button"
              className="text-action calendar-shift"
              onClick={() => setVisible((current) => shiftMonth(current.year, current.month, -1))}
            >
              Prev
            </button>
            <button
              type="button"
              className="text-action calendar-shift"
              onClick={() => setVisible((current) => shiftMonth(current.year, current.month, 1))}
            >
              Next
            </button>
          </div>
        </div>
        <div className="calendar-grid" role="grid" aria-label={monthLabel(visible.year, visible.month)}>
          {WEEKDAYS.map((name) => (
            <div key={name} className="calendar-dow" role="columnheader">
              {name}
            </div>
          ))}
          {cells.map((day, index) => {
            if (day === null) return <div key={`pad-${index}`} />
            const key = `${visible.year}-${String(visible.month).padStart(2, "0")}-${String(day).padStart(2, "0")}`
            const count = grouped.get(key)?.length ?? 0
            return (
              <button
                key={key}
                type="button"
                role="gridcell"
                className={count > 0 ? "calendar-day has-events" : "calendar-day"}
                aria-pressed={key === active}
                aria-label={count > 0 ? `${dayLabel(key)}, ${count} saved` : dayLabel(key)}
                onClick={() => setSelected(key)}
              >
                {day}
              </button>
            )
          })}
        </div>
        <section className="day-events" aria-label={dayLabel(active)}>
          <h2>{dayLabel(active)}</h2>
          {dayEvents.length === 0 ? <p className="lede">Nothing saved this day.</p> : null}
          {dayEvents.map((event) => {
            const when = formatWhen(event.startsAt)
            return (
              <div key={event.id} className="day-event">
                <button type="button" className="day-event-open" onClick={() => onInfo(event)}>
                  <span className="day-event-title">{event.title}</span>
                  <span className="day-event-meta">
                    {when.timeLabel}
                    <span aria-hidden="true"> · </span>
                    {event.location}
                  </span>
                </button>
                <button type="button" className="text-action day-unsave" onClick={() => onSave(event)}>
                  Saved
                </button>
              </div>
            )
          })}
        </section>
      </div>
    </div>
  )
}
