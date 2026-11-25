import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import "@/index.css"
import { ProjectorPage } from "./projector"

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ProjectorPage />
  </StrictMode>,
)
