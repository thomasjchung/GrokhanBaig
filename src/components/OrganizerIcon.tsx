import type { Organizer } from "../data/types"

const SKIP = new Set(["of", "the", "at", "and", "yale"])

export function organizerInitials(name: string) {
  const words = name
    .split(/\s+/)
    .map((word) => word.replace(/[^A-Za-z]/g, ""))
    .filter((word) => word && !SKIP.has(word.toLowerCase()))
  return words
    .slice(0, 2)
    .map((word) => word[0]!.toUpperCase())
    .join("")
}

export function OrganizerIcon({ organizer }: { organizer: Organizer }) {
  if (organizer.iconUrl) {
    return <img className="organizer-icon is-image" src={organizer.iconUrl} alt="" />
  }
  return (
    <span className="organizer-icon" aria-hidden="true">
      {organizerInitials(organizer.name)}
    </span>
  )
}
