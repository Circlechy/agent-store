import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import App from './App'

describe('App', () => {
  it('renders without crashing', () => {
    // Basic smoke test
    // Note: App uses Router, so we might need MemoryRouter if not wrapped, but App has BrowserRouter inside.
    // However, App is exported as default.
    // Since App has BrowserRouter inside, rendering it in test environment (jsdom) works fine.
    render(<App />)
    // Check if main layout exists (Sidebar or Header text)
    // Sidebar has "智能相册" or "AI"
    expect(screen.getByText(/智能相册/i)).toBeInTheDocument()
  })
})
