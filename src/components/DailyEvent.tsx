import { useState, type FormEvent } from "react"
import { loadEntry, parseKrillionResult, saveEntry, standings, todayKey, todayLabel, type DailyEntry } from "../daily"

export function DailyEvent({ name }: { name: string }) {
  const [entry, setEntry] = useState<DailyEntry | null>(() => loadEntry())
  const [draft, setDraft] = useState(() => loadEntry()?.raw ?? "")
  const [error, setError] = useState<string | null>(null)

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const parsed = parseKrillionResult(draft)
    if (!parsed.ok) {
      setError(parsed.message)
      return
    }
    const next: DailyEntry = {
      day: todayKey(),
      raw: draft.trim(),
      ...parsed.value,
    }
    saveEntry(next)
    setEntry(next)
    setError(null)
  }

  const rows = standings(entry ? { name, score: entry.score, emoji: entry.emoji } : null)

  return (
    <div className="page">
      <div className="page-inner with-tabs">
        <h1>Daily Event: <span className="daily-title-name">Krillion 🦑</span></h1>
        <p className="lede">{todayLabel()}. Paste the result link from today’s Krillion dive.</p>
        <h2>Leaderboard</h2>
        <ol className="board">
          {rows.map((row, index) => (
            <li key={row.id} className={row.you ? "board-row is-you" : "board-row"}>
              <span className="board-rank">{index + 1}</span>
              <span className="board-who">
                <span className="board-name">
                  {row.name}
                  {row.you ? <span className="visually-hidden"> (you)</span> : null}
                </span>
                {row.emoji ? <span className="board-emoji">{row.emoji}</span> : null}
              </span>
              <span className="board-score">{row.score}</span>
            </li>
          ))}
        </ol>
        {entry ? null : <p className="board-note">You are not on the board yet.</p>}
        <h2>Your result</h2>
        <form onSubmit={onSubmit}>
          <label className="field-label" htmlFor="krillion-result">
            Krillion result link
          </label>
          <textarea
            id="krillion-result"
            className="krillion-field"
            name="result"
            rows={4}
            spellCheck={false}
            autoComplete="off"
            placeholder={"Krillion #120\n345\nhttps://krillion.io"}
            aria-describedby={error ? "krillion-error" : undefined}
            value={draft}
            onChange={(event) => {
              setDraft(event.target.value)
              if (error) setError(null)
            }}
          />
          {error ? (
            <p id="krillion-error" className="form-note" role="alert">
              {error}
            </p>
          ) : null}
          <button type="submit" className="text-action">
            {entry ? "Update" : "Enter"}
          </button>
        </form>
      </div>
    </div>
  )
}
