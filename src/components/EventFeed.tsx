import { useEffect, useRef } from "react"
import type { FeedEvent } from "../data/types"
import { formatWhen } from "../formatWhen"
import { OrganizerIcon } from "./OrganizerIcon"

export function EventFeed({
  events,
  onIndex,
  onSave,
  onGoing,
  onInfo,
}: {
  events: FeedEvent[]
  onIndex: (index: number) => void
  onSave: (event: FeedEvent) => void
  onGoing: (event: FeedEvent) => void
  onInfo: (event: FeedEvent) => void
}) {
  const feedRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    onIndex(0)
  }, [onIndex, events.length])

  function reportIndex() {
    const feed = feedRef.current
    if (!feed || feed.clientHeight === 0) return
    const index = Math.round(feed.scrollTop / feed.clientHeight)
    onIndex(Math.max(0, Math.min(events.length - 1, index)))
  }

  return (
    <div className="feed" ref={feedRef} onScroll={reportIndex}>
      {events.map((event) => (
        <EventSlide
          key={event.id}
          event={event}
          onSave={() => onSave(event)}
          onGoing={() => onGoing(event)}
          onInfo={() => onInfo(event)}
        />
      ))}
    </div>
  )
}

function EventSlide({
  event,
  onSave,
  onGoing,
  onInfo,
}: {
  event: FeedEvent
  onSave: () => void
  onGoing: () => void
  onInfo: () => void
}) {
  const titleId = `${event.id}-title`
  const when = formatWhen(event.startsAt)
  const paper = event.image === null

  return (
    <article className={paper ? "event event-paper" : "event"} aria-labelledby={titleId}>
      {event.image ? (
        <img className="event-photo" src={event.image.url} alt="" />
      ) : null}
      {event.image ? <div className="event-shade" /> : null}
      <div className="event-copy">
        <FriendGoing friends={event.friendsGoing} reason={event.reason?.text ?? null} />
        <h1 id={titleId} className="event-title">
          {event.title}
        </h1>
        <p className="event-when">
          <time dateTime={event.startsAt}>
            {when.dateLabel}
            <span aria-hidden="true"> · </span>
            {when.timeLabel}
          </time>
        </p>
        <p className="event-where">{event.location}</p>
        <p className="organizer-line">
          <OrganizerIcon organizer={event.organizer} />
          <span>{event.organizer.name}</span>
        </p>
        <div className="event-controls" role="group" aria-label={`${event.title} actions`}>
          <button type="button" className="control" aria-pressed={event.saved} onClick={onSave}>
            {event.saved ? "Saved" : "Save"}
          </button>
          <button type="button" className="control" aria-pressed={event.going} onClick={onGoing}>
            Going
          </button>
          <button type="button" className="control" onClick={onInfo}>
            Info
          </button>
        </div>
      </div>
    </article>
  )
}

function FriendGoing({
  friends,
  reason,
}: {
  friends: FeedEvent["friendsGoing"]
  reason: string | null
}) {
  if (friends.length === 0 && !reason) return null
  return (
    <div className="social">
      {friends.length > 0 ? (
        <div
          className="friend-icons"
          aria-hidden={reason ? true : undefined}
          aria-label={reason ? undefined : `Going: ${friends.map((friend) => friend.name).join(", ")}`}
        >
          {friends.map((friend) => (
            <img key={friend.id} className="friend-icon" src={friend.avatarUrl} alt="" />
          ))}
        </div>
      ) : null}
      {reason ? <p className="reason">{reason}</p> : null}
    </div>
  )
}
