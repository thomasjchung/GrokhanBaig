export function formatWhen(startsAt: string) {
  const date = new Date(startsAt)
  const dateLabel = new Intl.DateTimeFormat("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
    timeZone: "America/New_York",
  }).format(date)
  const time = new Intl.DateTimeFormat("en-US", {
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
    timeZone: "America/New_York",
  }).format(date)
  const timeLabel = time.replace(/\s*([AP])\.?M\.?$/i, (_, half: string) => ` ${half.toLowerCase()}.m.`)
  return { dateLabel, timeLabel }
}
