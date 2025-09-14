import React from 'react'
import { render, screen, fireEvent } from '@testing-library/react'
import { vi } from 'vitest'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { FormField, FormLabel, FormControl } from '@/components/ui/form'

describe('Button Component', () => {
  it('should render with default variant', () => {
    render(<Button>Default Button</Button>)
    
    const button = screen.getByRole('button', { name: 'Default Button' })
    expect(button).toBeInTheDocument()
    expect(button).toHaveClass('bg-primary')
  })

  it('should render with ghost variant', () => {
    render(<Button variant="ghost">Ghost Button</Button>)
    
    const button = screen.getByRole('button', { name: 'Ghost Button' })
    expect(button).toBeInTheDocument()
    expect(button).toHaveClass('hover:bg-accent')
    expect(button).not.toHaveClass('bg-primary')
  })

  it('should handle click events', () => {
    const handleClick = vi.fn()
    render(<Button onClick={handleClick}>Click Me</Button>)
    
    const button = screen.getByRole('button', { name: 'Click Me' })
    fireEvent.click(button)
    
    expect(handleClick).toHaveBeenCalledTimes(1)
  })

  it('should be disabled when disabled prop is true', () => {
    render(<Button disabled>Disabled Button</Button>)
    
    const button = screen.getByRole('button', { name: 'Disabled Button' })
    expect(button).toBeDisabled()
    expect(button).toHaveClass('disabled:opacity-50')
  })
})

describe('Input Component', () => {
  it('should render input with placeholder', () => {
    render(<Input placeholder="Enter text" />)
    
    const input = screen.getByPlaceholderText('Enter text')
    expect(input).toBeInTheDocument()
    expect(input).toHaveClass('flex', 'h-10', 'w-full')
  })

  it('should accept value and onChange', () => {
    const handleChange = vi.fn()
    render(<Input value="test value" onChange={handleChange} />)
    
    const input = screen.getByDisplayValue('test value')
    expect(input).toBeInTheDocument()
    
    fireEvent.change(input, { target: { value: 'new value' } })
    expect(handleChange).toHaveBeenCalled()
  })

  it('should handle different input types', () => {
    render(<Input type="email" placeholder="Email" />)
    
    const input = screen.getByPlaceholderText('Email')
    expect(input).toHaveAttribute('type', 'email')
  })

  it('should be disabled when disabled prop is true', () => {
    render(<Input disabled placeholder="Disabled input" />)
    
    const input = screen.getByPlaceholderText('Disabled input')
    expect(input).toBeDisabled()
    expect(input).toHaveClass('disabled:opacity-50')
  })
})

describe('FormField Component', () => {
  it('should show error text when provided an error', () => {
    render(
      <FormField name="test-field" error="This field is required">
        <FormLabel>Test Label</FormLabel>
        <FormControl>
          <Input placeholder="Test input" />
        </FormControl>
      </FormField>
    )
    
    const errorMessage = screen.getByText('This field is required')
    expect(errorMessage).toBeInTheDocument()
    expect(errorMessage).toHaveClass('text-destructive')
  })

  it('should not show error text when no error is provided', () => {
    render(
      <FormField name="test-field">
        <FormLabel>Test Label</FormLabel>
        <FormControl>
          <Input placeholder="Test input" />
        </FormControl>
      </FormField>
    )
    
    const errorMessage = screen.queryByText('This field is required')
    expect(errorMessage).not.toBeInTheDocument()
  })

  it('should render with error styling when error is present', () => {
    render(
      <FormField name="test-field" error="This field is required">
        <FormLabel>Test Label</FormLabel>
        <FormControl>
          <Input placeholder="Test input" />
        </FormControl>
      </FormField>
    )
    
    const input = screen.getByPlaceholderText('Test input')
    const errorMessage = screen.getByText('This field is required')
    
    expect(input).toBeInTheDocument()
    expect(errorMessage).toHaveAttribute('id', 'test-field-error')
  })

  it('should render label and input correctly', () => {
    render(
      <FormField name="email-field">
        <FormLabel>Email Address</FormLabel>
        <FormControl>
          <Input type="email" placeholder="Enter your email" />
        </FormControl>
      </FormField>
    )
    
    const label = screen.getByText('Email Address')
    const input = screen.getByPlaceholderText('Enter your email')
    
    expect(label).toBeInTheDocument()
    expect(input).toBeInTheDocument()
    expect(input).toHaveAttribute('type', 'email')
  })
})
