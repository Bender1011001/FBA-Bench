import '@testing-library/jest-dom'

// Ensure consistent localStorage between tests
beforeEach(() => {
  window.localStorage.clear()
})
