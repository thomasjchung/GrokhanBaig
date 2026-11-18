import { useEffect, useState } from "react"
import type { Club, Session } from "../data/types"
import { ClubList } from "./ClubList"

export function ProfileScreen({
  session,
  clubs,
  onClubs,
  onSignIn,
}: {
  session: Session
  clubs: Club[]
  onClubs: (clubIds: string[]) => Promise<void>
  onSignIn: () => void
}) {
  const [notice, setNotice] = useState<string | null>(null)
  const [pending, setPending] = useState(false)
  const [googleEmail, setGoogleEmail] = useState<string | null>(null)

  useEffect(() => {
    let cancel = false
    fetch("/api/google/session", { credentials: "include" })
      .then((response) => (response.ok ? response.json() : { connected: false }))
      .then((body: { connected?: boolean; email?: string }) => {
        if (!cancel) setGoogleEmail(body.connected ? body.email ?? null : null)
      })
      .catch(() => {
        if (!cancel) setGoogleEmail(null)
      })
    return () => {
      cancel = true
    }
  }, [])

  async function toggle(clubId: string) {
    if (pending) return
    const next = new Set(session.clubIds)
    if (next.has(clubId)) next.delete(clubId)
    else next.add(clubId)
    const ordered = clubs.map((club) => club.id).filter((id) => next.has(id))
    setPending(true)
    try {
      await onClubs(ordered)
    } finally {
      setPending(false)
    }
  }

  async function copyLink() {
    const url = session.inviteUrl
    let copied = false
    try {
      await navigator.clipboard.writeText(url)
      copied = true
    } catch {
      const field = document.createElement("textarea")
      field.value = url
      field.setAttribute("readonly", "")
      field.style.position = "fixed"
      field.style.left = "-9999px"
      document.body.appendChild(field)
      field.select()
      try {
        copied = document.execCommand("copy")
      } catch {
        copied = false
      }
      field.remove()
    }
    setNotice(copied ? "Copied" : "Copy link")
    if (copied) window.setTimeout(() => setNotice(null), 2000)
  }

  return (
    <div className="page">
      <div className="page-inner with-tabs">
        <h1>Profile</h1>
        <p className="profile-name">{session.student.name}</p>
        <p className="profile-email">{session.student.email}</p>
        <h2>Accounts</h2>
        <p className="profile-email">
          Instagram ·{" "}
          <a href="https://www.instagram.com/farhanandtommyclub/">@farhanandtommyclub</a>
        </p>
        {googleEmail ? (
          <p className="profile-email">Google · {googleEmail}</p>
        ) : (
          <a className="google-button" href="/api/google/start">
            Continue with Google
          </a>
        )}
        <h2>Clubs</h2>
        <ClubList clubs={clubs} selected={session.clubIds} onToggle={(id) => void toggle(id)} />
        <h2>Invite a friend</h2>
        <p className="invite-url">{session.inviteUrl}</p>
        <button type="button" className="text-action" onClick={() => void copyLink()}>
          {notice ?? "Copy link"}
        </button>
        <button type="button" className="text-action" onClick={onSignIn}>
          Back to sign in
        </button>
      </div>
    </div>
  )
}
