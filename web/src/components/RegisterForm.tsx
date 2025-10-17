import React, { useState } from 'react';
import { createAuthClient } from '@fba-enterprise/auth-client/authClient';
import type { UserPublic } from '../types';

interface RegisterFormProps {
  onSuccess?: () => void;
}

const RegisterForm: React.FC<RegisterFormProps> = ({ onSuccess }) => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [emailError, setEmailError] = useState<string | null>(null);
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [serverError, setServerError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [loading, setLoading] = useState(false);

  const validateEmail = (email: string): string | null => {
    if (!email.trim()) return 'Email is required';
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(email)) return 'Please enter a valid email address';
    return null;
  };

  const validatePassword = (password: string): string | null => {
    if (password.length < 8) return 'Password must be at least 8 characters';
    if (password.length > 128) return 'Password must not exceed 128 characters';
    if (!/[a-z]/.test(password)) return 'Password must contain at least one lowercase letter';
    if (!/[A-Z]/.test(password)) return 'Password must contain at least one uppercase letter';
    if (!/\d/.test(password)) return 'Password must contain at least one digit';
    if (!/[^a-zA-Z0-9]/.test(password)) return 'Password must contain at least one special character';
    return null;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setServerError(null);
    setSuccess(false);

    const emailErr = validateEmail(email);
    const passwordErr = validatePassword(password);
    setEmailError(emailErr);
    setPasswordError(passwordErr);

    if (emailErr || passwordErr) return;

    const normalizedEmail = email.trim().toLowerCase();

    setLoading(true);
    try {
      const baseUrl = (window as any).API_BASE_URL || 'http://127.0.0.1:8000';
      const client = createAuthClient({ baseUrl });
      const user = await client.register(normalizedEmail, password);
      console.log('Account created');
      setSuccess(true);
      setEmail('');
      setPassword('');
      onSuccess?.();
    } catch (error: any) {
      console.error('Registration error:', error);
      if (error.status === 409) {
        setServerError('Email already registered');
      } else if (error.status === 400) {
        setServerError('Invalid input');
      } else {
        setServerError('Something went wrong, please try again');
      }
    } finally {
      setLoading(false);
    }
  };

  if (success) {
    return (
      <div className="card container" aria-live="polite">
        <h2 className="notice">Account created</h2>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="card" style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }} aria-busy={loading}>
      <h2>Register</h2>
      {serverError && (
        <div className="error" style={{ padding: '1rem', border: '1px solid #b91c1c', borderRadius: '6px' }} role="alert" aria-live="polite">
          {serverError}
        </div>
      )}
      <div>
        <label htmlFor="email">Email:</label>
        <input
          id="email"
          type="email"
          value={email}
          onChange={(e) => {
            setEmail(e.target.value);
            setEmailError(validateEmail(e.target.value));
          }}
          disabled={loading}
          className={`input ${emailError ? 'error' : ''}`}
          required
          aria-invalid={!!emailError}
        />
        {emailError && <p className="error" role="alert">{emailError}</p>}
      </div>

      <div>
        <label htmlFor="password">Password:</label>
        <input
          id="password"
          type="password"
          value={password}
          onChange={(e) => {
            setPassword(e.target.value);
            setPasswordError(validatePassword(e.target.value));
          }}
          disabled={loading}
          className={`input ${passwordError ? 'error' : ''}`}
          required
          aria-invalid={!!passwordError}
        />
        {passwordError && <p className="error" role="alert">{passwordError}</p>}
      </div>

      <button
        type="submit"
        disabled={!!emailError || !!passwordError || loading}
        className="btn btn-primary"
        aria-busy={loading}
      >
        {loading ? 'Creating account...' : 'Create account'}
      </button>
    </form>
  );
};

export default RegisterForm;