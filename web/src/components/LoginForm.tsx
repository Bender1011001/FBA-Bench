import { useState } from 'react'
import { createAuthClient } from '@fba-enterprise/auth-client/authClient'

// Simple email validation
const isValidEmail = (email: string): boolean => {
  const trimmed = email.trim()
  return trimmed.length > 0 && trimmed.includes('@')
}

interface LoginFormProps {
  onSuccess?: () => void
}

export default function LoginForm({ onSuccess }: LoginFormProps) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [emailError, setEmailError] = useState('')
  const [passwordError, setPasswordError] = useState('')
  const [serverError, setServerError] = useState('')
  const [successMessage, setSuccessMessage] = useState('')
  const [loading, setLoading] = useState(false)

  const validateForm = (): boolean => {
    let valid = true
    setEmailError('')
    setPasswordError('')

    if (!isValidEmail(email)) {
      setEmailError('Please enter a valid email address.')
      valid = false
    }

    if (password.trim().length === 0) {
      setPasswordError('Password is required.')
      valid = false
    }

    return valid
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setServerError('')
    setSuccessMessage('')

    if (!validateForm()) {
      return
    }

    setLoading(true)

    try {
      const client = createAuthClient()

      // Login (client normalizes email)
      await client.login(email, password)

      setSuccessMessage('Signed in')
      console.log('Signed in successfully')
      if (onSuccess) {
        onSuccess()
      }
    } catch (error: any) {
      console.error('Login error:', error)
      if (error.status === 401) {
        setServerError('Invalid email or password')
      } else if (error.status === 400) {
        setServerError('Invalid input')
      } else {
        setServerError('Something went wrong, please try again')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="card" style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      <div>
        <label htmlFor="email">Email:</label>
        <input
          id="email"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          disabled={loading}
          className={`input ${emailError ? 'error' : ''}`}
        />
        {emailError && <p className="error">{emailError}</p>}
      </div>

      <div>
        <label htmlFor="password">Password:</label>
        <input
          id="password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          disabled={loading}
          className={`input ${passwordError ? 'error' : ''}`}
        />
        {passwordError && <p className="error">{passwordError}</p>}
      </div>

      {serverError && (
        <div className="error" style={{ padding: '1rem', border: '1px solid #b91c1c', borderRadius: '6px' }}>
          {serverError}
        </div>
      )}

      {successMessage && (
        <div style={{ padding: '1rem', border: '1px solid #10b981', borderRadius: '6px', backgroundColor: '#ecfdf5', color: '#065f46' }}>
          {successMessage}
        </div>
      )}

      <button
        type="submit"
        disabled={!isValidEmail(email) || password.trim().length === 0 || loading}
        className="btn btn-primary"
        aria-busy={loading}
      >
        {loading ? 'Signing in…' : 'Log in'}
      </button>
    </form>
  )
}