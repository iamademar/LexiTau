import React from 'react'
import { render, screen } from '@testing-library/react'
import { cn } from '@/lib/utils'

// Simple test component with Tailwind class using cn() utility
function TestComponent() {
  return (
    <div 
      className={cn("rounded-2xl", "p-4", "bg-blue-500")} 
      data-testid="tailwind-test"
    >
      Tailwind Test
    </div>
  )
}

describe('Tailwind CSS Integration', () => {
  it('should render a div with Tailwind classes using cn() utility', () => {
    render(<TestComponent />)
    
    const element = screen.getByTestId('tailwind-test')
    expect(element).toBeInTheDocument()
    expect(element).toHaveClass('rounded-2xl', 'p-4', 'bg-blue-500')
  })
})
