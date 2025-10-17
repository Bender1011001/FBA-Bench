import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import LoginForm from './LoginForm'

// Mock createAuthClient to avoid real API calls
const mockedCreateAuthClient = vi.hoisted(() => vi.fn())
vi.mock('@fba-enterprise/auth-client/authClient', () => ({
  createAuthClient: mockedCreateAuthClient
}))

describe('LoginForm', () => {
  const mockOnSuccess = vi.fn()
  const user = userEvent.setup()

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders form elements', () => {
    render(<LoginForm onSuccess={mockOnSuccess} />)
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /log in/i })).toBeInTheDocument()
  })

  it('validation prevents submit when fields are empty', async () => {
    render(<LoginForm onSuccess={mockOnSuccess} />)

    const submitButton = screen.getByRole('button', { name: /log in/i })

    fireEvent.click(submitButton)

    await waitFor(() => {
      expect(screen.getByText(/valid email address/i)).toBeInTheDocument()
      expect(screen.getByText(/password is required/i)).toBeInTheDocument()
    })

    expect(submitButton).toBeDisabled()
  })

  it('shows email validation error for invalid email', async () => {
    render(<LoginForm onSuccess={mockOnSuccess} />)

    const emailInput = screen.getByLabelText(/email/i)
    const submitButton = screen.getByRole('button', { name: /log in/i })

    await user.type(emailInput, 'invalid')

    fireEvent.click(submitButton)

    await waitFor(() => {
      expect(screen.getByText(/valid email address/i)).toBeInTheDocument()
    })

    expect(submitButton).toBeDisabled()
  })

  it('successful login shows loading then success message', async () => {
    const mockLogin = vi.fn().mockResolvedValue({ access_token: 'mock-token', token_type: 'bearer', expires_in: 3600 })
    mockedCreateAuthClient.mockReturnValue({
      login: mockLogin
    })

    render(<LoginForm onSuccess={mockOnSuccess} />)

    const emailInput = screen.getByLabelText(/email/i)
    const passwordInput = screen.getByLabelText(/password/i)
    const submitButton = screen.getByRole('button', { name: /log in/i })

    await user.type(emailInput, 'test@example.com')
    await user.type(passwordInput, 'password123')

    expect(submitButton).not.toBeDisabled()

    await user.click(submitButton)

    // Loading state
    expect(submitButton).toHaveTextContent('Signing in…')
    expect(submitButton).toBeDisabled()
    expect(emailInput).toBeDisabled()
    expect(passwordInput).toBeDisabled()

    await waitFor(() => {
      expect(mockLogin).toHaveBeenCalledWith('test@example.com', 'password123')
      expect(screen.getByText('Signed in')).toBeInTheDocument()
    })

    // Re-enabled
    expect(submitButton).not.toBeDisabled()
    expect(emailInput).not.toBeDisabled()
    expect(passwordInput).not.toBeDisabled()

    expect(mockOnSuccess).toHaveBeenCalled()
  })

  it('shows 401 error message on invalid credentials', async () => {
    const mockLogin = vi.fn().mockRejectedValue({ status: 401 })
    mockedCreateAuthClient.mockReturnValue({
      login: mockLogin
    })

    render(<LoginForm onSuccess={mockOnSuccess} />)

    const emailInput = screen.getByLabelText(/email/i)
    const passwordInput = screen.getByLabelText(/password/i)
    const submitButton = screen.getByRole('button', { name: /log in/i })

    await user.type(emailInput, 'test@example.com')
    await user.type(passwordInput, 'wrongpass')

    await user.click(submitButton)

    await waitFor(() => {
      expect(screen.getByText('Invalid email or password')).toBeInTheDocument()
    })

    expect(mockLogin).toHaveBeenCalled()
    expect(mockOnSuccess).not.toHaveBeenCalled()
  })

  it('shows 400 error message on invalid input', async () => {
    const mockLogin = vi.fn().mockRejectedValue({ status: 400 })
    mockedCreateAuthClient.mockReturnValue({
      login: mockLogin
    })

    render(<LoginForm onSuccess={mockOnSuccess} />)

    const emailInput = screen.getByLabelText(/email/i)
    const passwordInput = screen.getByLabelText(/password/i)
    const submitButton = screen.getByRole('button', { name: /log in/i })

    await user.type(emailInput, 'test@example.com')
    await user.type(passwordInput, 'password123')

    await user.click(submitButton)

    await waitFor(() => {
      expect(screen.getByText('Invalid input')).toBeInTheDocument()
    })
  })

  it('shows network error message', async () => {
    const mockLogin = vi.fn().mockRejectedValue(new Error('Network error'))
    mockedCreateAuthClient.mockReturnValue({
      login: mockLogin
    })

    render(<LoginForm onSuccess={mockOnSuccess} />)

    const emailInput = screen.getByLabelText(/email/i)
    const passwordInput = screen.getByLabelText(/password/i)
    const submitButton = screen.getByRole('button', { name: /log in/i })

    await user.type(emailInput, 'test@example.com')
    await user.type(passwordInput, 'password123')

    await user.click(submitButton)

    await waitFor(() => {
      expect(screen.getByText('Something went wrong, please try again')).toBeInTheDocument()
    })
  })

  it('accessibility: button and inputs disabled during loading', async () => {
    const mockLogin = vi.fn().mockResolvedValue({ access_token: 'mock-token', token_type: 'bearer', expires_in: 3600 })
    mockedCreateAuthClient.mockReturnValue({
      login: mockLogin
    })

    render(<LoginForm onSuccess={mockOnSuccess} />)

    const emailInput = screen.getByLabelText(/email/i)
    const passwordInput = screen.getByLabelText(/password/i)
    const submitButton = screen.getByRole('button', { name: /log in/i })

    await user.type(emailInput, 'test@example.com')
    await user.type(passwordInput, 'password123')

    await user.click(submitButton)

    // During loading
    expect(submitButton).toBeDisabled()
    expect(submitButton.getAttribute('aria-busy')).toBe('true')
    expect(emailInput).toBeDisabled()
    expect(passwordInput).toBeDisabled()

    await waitFor(() => {
      expect(screen.getByText('Signed in')).toBeInTheDocument()
    })

    // After
    expect(submitButton).not.toBeDisabled()
    expect(submitButton.getAttribute('aria-busy')).toBeNull()
    expect(emailInput).not.toBeDisabled()
    expect(passwordInput).not.toBeDisabled()
  })
})