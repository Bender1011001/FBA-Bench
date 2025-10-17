import { useState, useEffect } from 'react'
import LoginForm from './components/LoginForm'
import RegisterForm from './components/RegisterForm'
import AccountPage from './components/AccountPage'
import OnboardingOverlay from './components/OnboardingOverlay'
import HelpButton from './components/HelpButton'
import HelpModal from './components/HelpModal'
import { createTokenStorage } from '@fba-enterprise/auth-client/tokenStorage'

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [view, setView] = useState<'login' | 'register'>('login')
  const [onboardingDismissed, setOnboardingDismissed] = useState(false)
  const [helpOpen, setHelpOpen] = useState(false)
  const [helpContext, setHelpContext] = useState<'login' | 'register' | 'account'>('login')

  const storage = createTokenStorage()

  useEffect(() => {
    setIsAuthenticated(storage.isAuthenticated())
  }, [])

  useEffect(() => {
    const dismissed = localStorage.getItem('fbaee_onboarding_dismissed') === 'true'
    setOnboardingDismissed(dismissed)
  }, [])

  const handleHelpClick = () => {
    setHelpContext(isAuthenticated ? 'account' : view)
    setHelpOpen(true)
  }

  const handleLoginSuccess = () => {
    setIsAuthenticated(true)
  }

  const handleRegisterSuccess = () => {
    setView('login')
  }

  const handleUnauthorized = () => {
    setIsAuthenticated(false)
  }

  const handleSignOut = () => {
    setIsAuthenticated(false)
  }

  if (!onboardingDismissed) {
    return (
      <>
        <OnboardingOverlay onClose={() => setOnboardingDismissed(true)} />
        <div className="container" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '100vh' }}>
          <h1 style={{ textAlign: 'center' }}>FBA Enterprise Login</h1>
          {view === 'login' ? (
            <>
              <LoginForm onSuccess={handleLoginSuccess} />
              <p style={{ textAlign: 'center', marginTop: '1rem' }}>
                <button
                  onClick={() => setView('register')}
                  style={{
                    background: 'none',
                    border: 'none',
                    color: '#007bff',
                    cursor: 'pointer',
                    textDecoration: 'underline',
                    fontSize: '1rem'
                  }}
                  type="button"
                >
                  Create an account
                </button>
              </p>
            </>
          ) : (
            <>
              <RegisterForm onSuccess={handleRegisterSuccess} />
              <p style={{ textAlign: 'center', marginTop: '1rem' }}>
                <button
                  onClick={() => setView('login')}
                  style={{
                    background: 'none',
                    border: 'none',
                    color: '#007bff',
                    cursor: 'pointer',
                    textDecoration: 'underline',
                    fontSize: '1rem'
                  }}
                  type="button"
                >
                  Back to login
                </button>
              </p>
            </>
          )}
          <HelpButton onClick={handleHelpClick} />
        </div>
        <HelpModal open={helpOpen} onClose={() => setHelpOpen(false)} context={helpContext} />
      </>
    )
  }

  if (isAuthenticated) {
    return (
      <>
        <div className="container" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '100vh' }}>
          <h1 style={{ textAlign: 'center' }}>FBA Enterprise</h1>
          <AccountPage onUnauthorized={handleUnauthorized} onSignOut={handleSignOut} />
          <HelpButton onClick={handleHelpClick} />
        </div>
        <HelpModal open={helpOpen} onClose={() => setHelpOpen(false)} context="account" />
      </>
    )
  }

  return (
    <>
      <div className="container" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '100vh' }}>
        <h1 style={{ textAlign: 'center' }}>FBA Enterprise Login</h1>
        {view === 'login' ? (
          <>
            <LoginForm onSuccess={handleLoginSuccess} />
            <p style={{ textAlign: 'center', marginTop: '1rem' }}>
              <button
                onClick={() => setView('register')}
                style={{
                  background: 'none',
                  border: 'none',
                  color: '#007bff',
                  cursor: 'pointer',
                  textDecoration: 'underline',
                  fontSize: '1rem'
                }}
                type="button"
              >
                Create an account
              </button>
            </p>
          </>
        ) : (
          <>
            <RegisterForm onSuccess={handleRegisterSuccess} />
            <p style={{ textAlign: 'center', marginTop: '1rem' }}>
              <button
                onClick={() => setView('login')}
                style={{
                  background: 'none',
                  border: 'none',
                  color: '#007bff',
                  cursor: 'pointer',
                  textDecoration: 'underline',
                  fontSize: '1rem'
                }}
                type="button"
              >
                Back to login
              </button>
            </p>
          </>
        )}
        <HelpButton onClick={handleHelpClick} />
      </div>
      <HelpModal open={helpOpen} onClose={() => setHelpOpen(false)} context={helpContext} />
    </>
  )
}

export default App