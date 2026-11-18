import type { Club } from "../data/types"
import { OrganizerIcon } from "./OrganizerIcon"

export function ClubList({
  clubs,
  selected,
  onToggle,
}: {
  clubs: Club[]
  selected: string[]
  onToggle: (clubId: string) => void
}) {
  const chosen = new Set(selected)
  return (
    <div className="club-list">
      {clubs.map((club) => {
        const pressed = chosen.has(club.id)
        return (
          <button
            key={club.id}
            type="button"
            className="club"
            aria-pressed={pressed}
            onClick={() => onToggle(club.id)}
          >
            <OrganizerIcon organizer={{ id: club.id, name: club.name, iconUrl: club.iconUrl }} />
            <span className="club-name">{club.name}</span>
          </button>
        )
      })}
    </div>
  )
}
