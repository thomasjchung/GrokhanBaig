export type Tab = "feed" | "saved" | "profile"

const tabs: { id: Tab; label: string }[] = [
  { id: "feed", label: "Feed" },
  { id: "saved", label: "Saved" },
  { id: "profile", label: "Profile" },
]

export function TabBar({
  tab,
  onChange,
}: {
  tab: Tab | null
  onChange: (tab: Tab) => void
}) {
  return (
    <nav className="tabbar" aria-label="Sections">
      {tabs.map((item) => (
        <button
          key={item.id}
          type="button"
          className="tab"
          aria-current={tab === item.id ? "page" : undefined}
          onClick={() => onChange(item.id)}
        >
          {item.label}
        </button>
      ))}
    </nav>
  )
}
