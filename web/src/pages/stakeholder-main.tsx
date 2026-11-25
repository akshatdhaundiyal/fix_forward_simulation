import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import "@/index.css"
import { StakeholderPage } from "./stakeholder"

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <StakeholderPage />
  </StrictMode>,
)
