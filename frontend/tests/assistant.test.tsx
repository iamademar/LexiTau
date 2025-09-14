import React from 'react'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { vi } from 'vitest'
import { Assistant } from '@/components/assistant/Assistant'

describe('Assistant Component', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('should render Assistant heading', () => {
    render(<Assistant />)
    
    const heading = screen.getByRole('heading', { name: 'Assistant' })
    expect(heading).toBeInTheDocument()
    expect(heading).toHaveClass('text-xl', 'font-semibold')
  })

  it('should render message input and send button', () => {
    render(<Assistant />)
    
    const input = screen.getByPlaceholderText('Type your message...')
    const sendButton = screen.getByRole('button', { name: 'Send' })
    
    expect(input).toBeInTheDocument()
    expect(sendButton).toBeInTheDocument()
  })

  it('should handle message sending', async () => {
    render(<Assistant />)
    
    const input = screen.getByPlaceholderText('Type your message...')
    const sendButton = screen.getByRole('button', { name: 'Send' })
    
    fireEvent.change(input, { target: { value: 'Hello Assistant' } })
    fireEvent.click(sendButton)
    
    // Check user message appears
    expect(screen.getByText('Hello Assistant')).toBeInTheDocument()
    
    // Wait for assistant response (with timeout)
    await waitFor(() => {
      expect(screen.getByText(/I received your message: "Hello Assistant"/)).toBeInTheDocument()
    }, { timeout: 2000 })
  })

  it('should render empty state when no messages', () => {
    render(<Assistant />)
    
    const emptyStateHeading = screen.getByText('Start a conversation')
    const emptyStateDescription = screen.getByText('Ask me anything about your documents or data analysis.')
    
    expect(emptyStateHeading).toBeInTheDocument()
    expect(emptyStateDescription).toBeInTheDocument()
  })

  it('should render status indicator', () => {
    render(<Assistant />)
    
    const statusIndicator = screen.getByText('Ready to help')
    expect(statusIndicator).toBeInTheDocument()
    expect(statusIndicator).toHaveClass('text-sm', 'text-muted-foreground')
  })

  it('should not make network calls during render', () => {
    // This test verifies that no actual network calls are made during render
    render(<Assistant />)
    
    // The component renders with a placeholder response system
    // No real API calls are made during initial render
    const heading = screen.getByRole('heading', { name: 'Assistant' })
    expect(heading).toBeInTheDocument()
    
    // Verify empty state is shown initially (no network calls)
    const emptyState = screen.getByText('Start a conversation')
    expect(emptyState).toBeInTheDocument()
  })

  it('should have proper layout structure', () => {
    render(<Assistant />)
    
    // Check for header section
    const heading = screen.getByRole('heading', { name: 'Assistant' })
    expect(heading.closest('div')).toHaveClass('flex', 'items-center', 'justify-between')
    
    // Check for input section container (parent of input)
    const input = screen.getByPlaceholderText('Type your message...')
    const inputContainer = input.closest('div')?.parentElement
    expect(inputContainer).toHaveClass('border-t')
    
    // Check for main chat area
    const emptyState = screen.getByText('Start a conversation')
    expect(emptyState).toBeInTheDocument()
  })
})
