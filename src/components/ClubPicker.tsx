import { useState } from "react"
import type { Club } from "../data/types"
import { ClubList } from "./ClubList"

export function ClubPicker({
  clubs,
  initialIds,
  onContinue,
  onSignIn,
}: {
  clubs: Club[]
  initialIds: string[]
  onContinue: (clubIds: string[]) => Promise<void>
  onSignIn: () => void
}) {
  const [selected, setSelected] = useState(initialIds)
  const [pending, setPending] = useState(false)

  function toggle(clubId: string) {
    setSelected((current) =>
      current.includes(clubId) ? current.filter((id) => id !== clubId) : [...current, clubId],
    )
  }

  async function submit() {
    if (selected.length === 0 || pending) return
    setPending(true)
    try {
      const ordered = clubs.map((club) => club.id).filter((id) => selected.includes(id))
      await onContinue(ordered)
    } finally {
      setPending(false)
    }
  }

  return (
    <div className="page">
      <div className="page-inner">
        <h1>Choose your clubs</h1>
        <p className="lede">Pick the groups you want to follow. You can change this later.</p>
        <ClubList clubs={clubs} selected={selected} onToggle={toggle} />
        <button
          type="button"
          className="text-action"
          disabled={selected.length === 0 || pending}
          onClick={() => void submit()}
        >
          {pending ? "Saving" : "Continue"}
        </button>
        <button type="button" className="text-action" onClick={onSignIn}>
          Back to sign in
        </button>
      </div>
    </div>
  )
}
