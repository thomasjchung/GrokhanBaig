export function SignIn({
  notice,
  onDemo,
}: {
  notice: string | null
  onDemo: () => void
}) {
  return (
    <main className="app">
      <div className="page">
        <div className="page-inner sign-in">
          <h1>Yale Events</h1>
          <p className="lede">
            Sign in with Google. Sheet keeps the newest upcoming invite from your inbox.
          </p>
          {notice ? <p className="lede">{notice}</p> : null}
          <a className="google-button" href="/api/google/start">
            Continue with Google
          </a>
          <button type="button" className="text-action" onClick={onDemo}>
            Continue with the demo
          </button>
        </div>
      </div>
    </main>
  )
}
