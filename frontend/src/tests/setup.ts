/**
 * Test setup file
 * Runs before all tests
 */

import '@testing-library/jest-dom'
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

// Cleanup after each test
afterEach(() => {
  cleanup()
})

// Mock environment variables
process.env.VITE_API_BASE_URL = 'http://localhost:8000'
process.env.VITE_ENABLE_DEBUG_LOGS = 'false'
