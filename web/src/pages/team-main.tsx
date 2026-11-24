import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import "@/index.css"
import { TeamPage } from "./team"

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <TeamPage />
  </StrictMode>,
)
