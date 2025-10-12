import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import RegisterForm from './RegisterForm';
import { createAuthClient } from '@fba-enterprise/auth-client/authClient';

// Mock the auth client
vi.mock('@fba-enterprise/auth-client/authClient', () => ({
  createAuthClient: vi.fn(() => ({
    register: vi.fn(),
  })),
}));

describe('RegisterForm', () => {
  it('renders the registration form', () => {
    render(<RegisterForm />);
    expect(screen.getByText('Register')).toBeInTheDocument();
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /create account/i })).toBeInTheDocument();
  });

  it('shows inline validation errors for invalid email', async () => {
    render(<RegisterForm />);
    const emailInput = screen.getByLabelText(/email/i);
    fireEvent.change(emailInput, { target: { value: 'invalid-email' } });
    expect(screen.getByText('Please enter a valid email address')).toBeInTheDocument();
  });

  it('shows inline validation errors for empty email', async () => {
    render(<RegisterForm />);
    const emailInput = screen.getByLabelText(/email/i);
    fireEvent.change(emailInput, { target: { value: '' } });
    expect(screen.getByText('Email is required')).toBeInTheDocument();
  });

  it('shows inline validation errors for invalid password', async () => {
    render(<RegisterForm />);
    const passwordInput = screen.getByLabelText(/password/i);
    fireEvent.change(passwordInput, { target: { value: 'short' } });
    expect(screen.getByText('Password must be at least 8 characters')).toBeInTheDocument();
  });

  it('shows multiple password validation errors', async () => {
    render(<RegisterForm />);
    const passwordInput = screen.getByLabelText(/password/i);
    fireEvent.change(passwordInput, { target: { value: 'Abc1defg' } }); // Missing special char
    expect(screen.getByText('Password must contain at least one special character')).toBeInTheDocument();
  });

  it('enables submit button only when form is valid', async () => {
    render(<RegisterForm />);
    const emailInput = screen.getByLabelText(/email/i);
    const passwordInput = screen.getByLabelText(/password/i);
    const submitButton = screen.getByRole('button', { name: /create account/i });

    // Invalid state
    expect(submitButton).toBeDisabled();

    // Valid email
    fireEvent.change(emailInput, { target: { value: 'test@example.com' } });
    expect(submitButton).toBeDisabled(); // Password still invalid

    // Valid password
    fireEvent.change(passwordInput, { target: { value: 'Password1!' } });
    expect(submitButton).not.toBeDisabled();
  });

  it('does not call register on invalid form submission', async () => {
    const mockRegister = vi.fn();
    vi.mocked(createAuthClient).mockReturnValue({ register: mockRegister } as any);

    render(<RegisterForm />);
    const form = screen.getByRole('form');
    fireEvent.submit(form);

    expect(mockRegister).not.toHaveBeenCalled();
  });

  it('calls register on valid form submission', async () => {
    const mockRegister = vi.fn().mockResolvedValue({} as any);
    vi.mocked(createAuthClient).mockReturnValue({ register: mockRegister } as any);

    render(<RegisterForm />);
    const emailInput = screen.getByLabelText(/email/i);
    const passwordInput = screen.getByLabelText(/password/i);
    const form = screen.getByRole('form');

    fireEvent.change(emailInput, { target: { value: ' test@example.com ' } });
    fireEvent.change(passwordInput, { target: { value: 'Password1!' } });
    fireEvent.submit(form);

    expect(mockRegister).toHaveBeenCalledWith('test@example.com', 'Password1!');
  });

  it('shows success message after successful registration', async () => {
    const mockRegister = vi.fn().mockResolvedValue({} as any);
    vi.mocked(createAuthClient).mockReturnValue({ register: mockRegister } as any);

    render(<RegisterForm />);
    const emailInput = screen.getByLabelText(/email/i);
    const passwordInput = screen.getByLabelText(/password/i);
    const form = screen.getByRole('form');

    fireEvent.change(emailInput, { target: { value: 'test@example.com' } });
    fireEvent.change(passwordInput, { target: { value: 'Password1!' } });
    fireEvent.submit(form);

    // Wait for async
    await vi.waitFor(() => {
      expect(screen.getByText('Account created')).toBeInTheDocument();
    });
  });

  it('shows server error for 409 conflict', async () => {
    const mockRegister = vi.fn().mockRejectedValue({ status: 409 });
    vi.mocked(createAuthClient).mockReturnValue({ register: mockRegister } as any);

    render(<RegisterForm />);
    const emailInput = screen.getByLabelText(/email/i);
    const passwordInput = screen.getByLabelText(/password/i);
    const form = screen.getByRole('form');

    fireEvent.change(emailInput, { target: { value: 'test@example.com' } });
    fireEvent.change(passwordInput, { target: { value: 'Password1!' } });
    fireEvent.submit(form);

    await vi.waitFor(() => {
      expect(screen.getByText('Email already registered')).toBeInTheDocument();
    });
  });

  it('shows server error for 400 bad request', async () => {
    const mockRegister = vi.fn().mockRejectedValue({ status: 400 });
    vi.mocked(createAuthClient).mockReturnValue({ register: mockRegister } as any);

    render(<RegisterForm />);
    const emailInput = screen.getByLabelText(/email/i);
    const passwordInput = screen.getByLabelText(/password/i);
    const form = screen.getByRole('form');

    fireEvent.change(emailInput, { target: { value: 'test@example.com' } });
    fireEvent.change(passwordInput, { target: { value: 'Password1!' } });
    fireEvent.submit(form);

    await vi.waitFor(() => {
      expect(screen.getByText('Invalid input')).toBeInTheDocument();
    });
  });

  it('shows network error for unknown error', async () => {
    const mockRegister = vi.fn().mockRejectedValue({ status: 500 });
    vi.mocked(createAuthClient).mockReturnValue({ register: mockRegister } as any);

    render(<RegisterForm />);
    const emailInput = screen.getByLabelText(/email/i);
    const passwordInput = screen.getByLabelText(/password/i);
    const form = screen.getByRole('form');

    fireEvent.change(emailInput, { target: { value: 'test@example.com' } });
    fireEvent.change(passwordInput, { target: { value: 'Password1!' } });
    fireEvent.submit(form);

    await vi.waitFor(() => {
      expect(screen.getByText('Something went wrong, please try again')).toBeInTheDocument();
    });
  });

  it('invokes onSuccess callback on successful registration', async () => {
    const mockOnSuccess = vi.fn();
    const mockRegister = vi.fn().mockResolvedValue({} as any);
    vi.mocked(createAuthClient).mockReturnValue({ register: mockRegister } as any);

    render(<RegisterForm onSuccess={mockOnSuccess} />);
    const emailInput = screen.getByLabelText(/email/i);
    const passwordInput = screen.getByLabelText(/password/i);
    const form = screen.getByRole('form');

    fireEvent.change(emailInput, { target: { value: 'test@example.com' } });
    fireEvent.change(passwordInput, { target: { value: 'Password1!' } });
    fireEvent.submit(form);

    await vi.waitFor(() => {
      expect(mockOnSuccess).toHaveBeenCalled();
    });
  });

  it('shows loading state during submission', async () => {
    const mockRegister = vi.fn().mockImplementation(() => new Promise(resolve => setTimeout(resolve, 100)));
    vi.mocked(createAuthClient).mockReturnValue({ register: mockRegister } as any);

    render(<RegisterForm />);
    const emailInput = screen.getByLabelText(/email/i);
    const passwordInput = screen.getByLabelText(/password/i);
    const form = screen.getByRole('form');
    const submitButton = screen.getByRole('button', { name: /creating account/i });

    fireEvent.change(emailInput, { target: { value: 'test@example.com' } });
    fireEvent.change(passwordInput, { target: { value: 'Password1!' } });
    fireEvent.submit(form);

    expect(submitButton).toBeDisabled();
    expect(submitButton).toHaveAttribute('aria-busy', 'true');
    const emailField = screen.getByLabelText(/email/i);
    const passwordField = screen.getByLabelText(/password/i);
    expect(emailField).toBeDisabled();
    expect(passwordField).toBeDisabled();

    await vi.waitFor(() => {
      expect(screen.getByText('Account created')).toBeInTheDocument();
    });

    expect(submitButton).not.toBeDisabled();
    expect(submitButton).toHaveAttribute('aria-busy', 'false');
    expect(emailField).not.toBeDisabled();
    expect(passwordField).not.toBeDisabled();
  });

  it('has accessible indicators for errors and success', async () => {
    render(<RegisterForm />);
    const emailInput = screen.getByLabelText(/email/i);
    fireEvent.change(emailInput, { target: { value: 'invalid' } });

    const error = screen.getByText('Please enter a valid email address');
    expect(error).toHaveAttribute('role', 'alert');

    // Success
    const mockRegister = vi.fn().mockResolvedValue({} as any);
    vi.mocked(createAuthClient).mockReturnValue({ register: mockRegister } as any);

    fireEvent.change(emailInput, { target: { value: 'test@example.com' } });
    const passwordInput = screen.getByLabelText(/password/i);
    fireEvent.change(passwordInput, { target: { value: 'Password1!' } });
    fireEvent.submit(screen.getByRole('form'));

    await vi.waitFor(() => {
      const success = screen.getByText('Account created');
      expect(success).toHaveAttribute('aria-live', 'polite');
    });
  });
});