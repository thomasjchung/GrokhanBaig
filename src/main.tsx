import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import "@fontsource-variable/newsreader/standard.css"
import { App } from "./App"
import "./styles.css"

const root = document.getElementById("root")
if (!root) throw new Error("Root element missing")

createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
