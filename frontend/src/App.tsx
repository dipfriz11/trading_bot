import { TerminalProvider } from "@/contexts/TerminalContext"
import { Terminal } from "@/components/terminal/Terminal"

export function App() {
  return (
    <TerminalProvider>
      <Terminal />
    </TerminalProvider>
  )
}

export default App
