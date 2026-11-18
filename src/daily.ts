/** Local daily board. Not part of the events API. */

const STORAGE_KEY = "yale-events.daily.v1"

const TIER: Record<string, number> = {
  "🌟": 100,
  "🏮": 85,
  "🦑": 60,
  "🐟": 30,
  "🤡": 15,
  "🫧": 10,
  "⬛": 0,
}

export type ParsedResult = {
  link: string
  score: number
  emoji: string | null
}

export type DailyEntry = ParsedResult & {
  /** Calendar day in America/New_York, YYYY-MM-DD. */
  day: string
  raw: string
}

export type BoardRow = {
  id: string
  name: string
  score: number
  you?: boolean
  emoji?: string | null
}

/** Sample standings so the board is not empty before anyone pastes a result. */
const FIELD: BoardRow[] = [
  { id: "maya", name: "Maya", score: 460 },
  { id: "alex", name: "Alex", score: 305 },
  { id: "jordan", name: "Jordan", score: 180 },
]

export function todayKey(now = new Date()): string {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "America/New_York",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(now)
}

export function todayLabel(now = new Date()): string {
  return new Intl.DateTimeFormat("en-US", {
    timeZone: "America/New_York",
    weekday: "long",
    month: "long",
    day: "numeric",
  }).format(now)
}

export function findKrillionLink(text: string): string | null {
  const explicit = text.match(/https?:\/\/(?:www\.)?krillion\.io[^\s)]*/i)
  const bare = explicit
    ? null
    : text.match(/(?:^|\s)((?:www\.)?krillion\.io\b[^\s)]*)/i)
  const found = explicit?.[0] ?? bare?.[1]
  if (!found) return null
  let link = found.replace(/[.,;:]+$/, "")
  if (!/^https?:\/\//i.test(link)) link = `https://${link}`
  return link
}

function longestTierRun(text: string): string | null {
  let best = ""
  let current = ""
  for (const char of text) {
    if (char in TIER) {
      current += char
      if (current.length > best.length) best = current
    } else {
      current = ""
    }
  }
  return best.length > 0 ? best : null
}

function emojiScore(row: string): number {
  let score = 0
  for (const char of row) score += TIER[char] ?? 0
  return score
}

export function parseKrillionResult(
  raw: string,
): { ok: true; value: ParsedResult } | { ok: false; message: string } {
  const text = raw.trim()
  const link = findKrillionLink(text)
  if (!link) return { ok: false, message: "Paste a krillion.io result link." }

  const labelled = text.match(/\b(?:score\s*)?(\d{1,4})\s*(?:points|pts)\b/i)
  const sameLine = text.match(/krillion[^\n]*#\s*\d+[^\d\n]+(\d{1,4})\b/i)
  let score: number | null = null
  if (labelled) {
    score = Number(labelled[1])
  } else if (sameLine) {
    score = Number(sameLine[1])
  } else {
    for (const line of text.split(/\r?\n/)) {
      const trimmed = line.trim()
      if (/^\d{1,4}$/.test(trimmed)) {
        score = Number(trimmed)
        break
      }
    }
  }

  const emoji = longestTierRun(text)
  if (score === null && emoji) score = emojiScore(emoji)
  if (score === null) {
    return { ok: false, message: "Include the score from the result Krillion copies." }
  }
  if (score > 700) return { ok: false, message: "That score is outside a Krillion dive." }

  return { ok: true, value: { link, score, emoji } }
}

export function loadEntry(now = new Date()): DailyEntry | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as Partial<DailyEntry>
    if (parsed.day !== todayKey(now)) return null
    if (typeof parsed.raw !== "string" || typeof parsed.link !== "string") return null
    if (typeof parsed.score !== "number" || !Number.isFinite(parsed.score)) return null
    return {
      day: parsed.day,
      raw: parsed.raw,
      link: parsed.link,
      score: parsed.score,
      emoji: typeof parsed.emoji === "string" ? parsed.emoji : null,
    }
  } catch {
    return null
  }
}

export function saveEntry(entry: DailyEntry) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(entry))
  } catch {
    // Private mode can block storage. The in-memory entry still shows on this screen.
  }
}

export function standings(you: { name: string; score: number; emoji: string | null } | null): BoardRow[] {
  const rows: BoardRow[] = FIELD.map((row) => ({ ...row }))
  if (you) {
    rows.push({ id: "you", name: you.name, score: you.score, you: true, emoji: you.emoji })
  }
  rows.sort((a, b) => b.score - a.score || Number(Boolean(a.you)) - Number(Boolean(b.you)))
  return rows
}
