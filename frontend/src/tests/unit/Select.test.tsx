import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import '@testing-library/jest-dom'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../../components/ui/select'

describe('Select', () => {
  it('applies invalid styling when aria-invalid is true', () => {
    render(
      <Select defaultValue="24h">
        <SelectTrigger aria-invalid={true}>
          <SelectValue placeholder="Select range" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="24h">Last 24 hours</SelectItem>
        </SelectContent>
      </Select>
    )

    const trigger = screen.getByRole('combobox')
    expect(trigger).toHaveClass('border-destructive/60')
    expect(trigger).toHaveClass('bg-destructive/5')
    expect(trigger).toHaveClass('focus:ring-destructive/35')
  })

  it('keeps default styling when invalid state is not set', () => {
    render(
      <Select defaultValue="24h">
        <SelectTrigger>
          <SelectValue placeholder="Select range" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="24h">Last 24 hours</SelectItem>
        </SelectContent>
      </Select>
    )

    const trigger = screen.getByRole('combobox')
    expect(trigger).not.toHaveClass('border-destructive/60')
    expect(trigger).not.toHaveClass('bg-destructive/5')
    expect(trigger).not.toHaveClass('focus:ring-destructive/35')
  })
})
