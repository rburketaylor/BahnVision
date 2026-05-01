import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import '@testing-library/jest-dom'
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '../../components/ui/dialog'

describe('Dialog', () => {
  it('includes enter and exit animation classes on overlay and content', () => {
    render(
      <Dialog open={true}>
        <DialogContent>
          <DialogTitle>Example Dialog</DialogTitle>
          <DialogDescription>Example description</DialogDescription>
        </DialogContent>
      </Dialog>
    )

    const content = screen.getByRole('dialog')
    expect(content.className).toContain('data-[state=open]:animate-in')
    expect(content.className).toContain('data-[state=closed]:animate-out')
    expect(content.className).toContain('data-[state=closed]:zoom-out-95')

    const overlay = document.querySelector('[data-state="open"][class*="bg-black/50"]')
    expect(overlay).toBeInTheDocument()
    expect((overlay as HTMLElement).className).toContain('data-[state=closed]:animate-out')
    expect((overlay as HTMLElement).className).toContain('data-[state=closed]:fade-out-0')
  })
})
