import React from 'react'
import { render, screen } from '@testing-library/react'

// Simple test component with Tailwind class
function TestComponent() {
  return <div className="rounded-2xl" data-testid="tailwind-test">Tailwind Test</div>
}

describe('Tailwind CSS Integration', () => {
  it('should render a div with Tailwind class rounded-2xl', () => {
    render(<TestComponent />)
    
    const element = screen.getByTestId('tailwind-test')
    expect(element).toBeInTheDocument()
    expect(element).toHaveClass('rounded-2xl')
  })
})
