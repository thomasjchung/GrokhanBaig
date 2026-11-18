import { useEffect, useRef, useState, type PointerEvent as ReactPointerEvent } from "react"
import type { FeedEvent } from "../data/types"
import { OrganizerIcon } from "./OrganizerIcon"

const DISMISS_DRAG_PX = 96

export function InfoSheet({ event, onClose }: { event: FeedEvent; onClose: () => void }) {
  const sheetRef = useRef<HTMLDivElement>(null)
  const closeRef = useRef<HTMLButtonElement>(null)
  const dragOrigin = useRef<number | null>(null)
  const [dragY, setDragY] = useState(0)
  const [dragging, setDragging] = useState(false)
  const [entered, setEntered] = useState(false)
  const mail = event.sourceUrl.startsWith("mailto:")

  useEffect(() => {
    const previouslyFocused = document.activeElement
    const frame = requestAnimationFrame(() => setEntered(true))
    closeRef.current?.focus()
    const background = document.querySelectorAll(".feed, .tabbar, .page")
    background.forEach((node) => node.setAttribute("inert", ""))

    function onKey(keyEvent: KeyboardEvent) {
      if (keyEvent.key === "Escape") {
        keyEvent.preventDefault()
        onClose()
        return
      }
      if (keyEvent.key !== "Tab" || !sheetRef.current) return
      const nodes = sheetRef.current.querySelectorAll<HTMLElement>("button, a[href]")
      if (nodes.length === 0) return
      const first = nodes[0]
      const last = nodes[nodes.length - 1]
      if (keyEvent.shiftKey && document.activeElement === first) {
        keyEvent.preventDefault()
        last.focus()
      } else if (!keyEvent.shiftKey && document.activeElement === last) {
        keyEvent.preventDefault()
        first.focus()
      }
    }

    document.addEventListener("keydown", onKey)
    return () => {
      cancelAnimationFrame(frame)
      document.removeEventListener("keydown", onKey)
      background.forEach((node) => node.removeAttribute("inert"))
      if (previouslyFocused instanceof HTMLElement) previouslyFocused.focus()
    }
  }, [onClose])

  function onPointerDown(pointerEvent: ReactPointerEvent<HTMLDivElement>) {
    if (pointerEvent.button !== 0) return
    const target = pointerEvent.target
    if (target instanceof Element && target.closest("button")) return
    dragOrigin.current = pointerEvent.clientY
    setDragging(true)
    pointerEvent.currentTarget.setPointerCapture(pointerEvent.pointerId)
  }

  function onPointerMove(pointerEvent: ReactPointerEvent<HTMLDivElement>) {
    if (dragOrigin.current === null) return
    setDragY(Math.max(0, pointerEvent.clientY - dragOrigin.current))
  }

  function finishDrag(pointerEvent: ReactPointerEvent<HTMLDivElement>) {
    if (dragOrigin.current === null) return
    const traveled = Math.max(0, pointerEvent.clientY - dragOrigin.current)
    dragOrigin.current = null
    setDragging(false)
    if (traveled > DISMISS_DRAG_PX) onClose()
    else setDragY(0)
  }

  return (
    <div className="sheet-layer">
      <div className="scrim" onClick={onClose} />
      <div
        ref={sheetRef}
        className={entered ? (dragging ? "sheet is-in is-dragging" : "sheet is-in") : "sheet"}
        role="dialog"
        aria-modal="true"
        aria-labelledby="info-sheet-title"
        style={{ "--drag": `${dragY}px` } as React.CSSProperties}
      >
        <div
          className="sheet-bar"
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={finishDrag}
          onPointerCancel={finishDrag}
        >
          <span className="sheet-handle" aria-hidden="true" />
          <button ref={closeRef} type="button" className="sheet-close" onClick={onClose}>
            Close
          </button>
        </div>
        <div className="sheet-body">
          <h2 id="info-sheet-title" className="visually-hidden">
            {event.title}
          </h2>
          {event.image ? <img className="flyer" src={event.image.url} alt={event.image.alt} /> : null}
          <div className="sheet-copy">
            <p className="sheet-description">{event.description}</p>
            <p className="sheet-organizer">
              <OrganizerIcon organizer={event.organizer} />
              <span>
                <span className="quiet">Organized by </span>
                {event.organizer.name}
              </span>
            </p>
            <p className="sheet-source">
              <span className="quiet">{mail ? "Email " : "Source "}</span>
              <a
                href={event.sourceUrl}
                {...(mail ? {} : { target: "_blank", rel: "noopener noreferrer" })}
              >
                {event.sourceLabel}
                {mail ? null : <span className="visually-hidden"> (opens in a new tab)</span>}
              </a>
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
