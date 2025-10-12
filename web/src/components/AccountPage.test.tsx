import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import AccountPage from './AccountPage';
import type { UserPublic, ApiError } from '@fba-enterprise/auth-client/http';

const mockUser: UserPublic = {
  id: '123',
  email: 'test@example.com',
  is_active: true,
  subscription_status: 'active',
  created_at: '2023-01-01T00:00:00Z',
  updated_at: '2023-01-01T00:00:00Z',
};

const mockOnUnauthorized = vi.fn();
const mockOnSignOut = vi.fn();

vi.mock('@fba-enterprise/auth-client/authClient', () => ({
  createAuthClient: vi.fn(() => ({
    me: vi.fn(),
  })),
}));

vi.mock('@fba-enterprise/auth-client/tokenStorage', () => ({
  createTokenStorage: vi.fn(() => ({
    clearToken: vi.fn(),
    isAuthenticated: vi.fn(() => true),
  })),
}));

const mockedCreateAuthClient = vi.mocked(require('@fba-enterprise/auth-client/authClient').createAuthClient);
const mockedCreateTokenStorage = vi.mocked(require('@fba-enterprise/auth-client/tokenStorage').createTokenStorage);

describe('AccountPage', () => {
  const mockClient = {
    me: vi.fn(),
  };
  const mockStorage = {
    clearToken: vi.fn(),
    isAuthenticated: vi.fn(() => true),
  };

  beforeEach(() => {
    vi.clearAllMocks();
    mockedCreateAuthClient.mockReturnValue(mockClient as any);
    mockedCreateTokenStorage.mockReturnValue(mockStorage as any);
    mockClient.me.mockResolvedValue(mockUser);
    mockStorage.isAuthenticated.mockReturnValue(true);
  });

  it('renders loading and then profile on success', async () => {
    render(<AccountPage onUnauthorized={mockOnUnauthorized} onSignOut={mockOnSignOut} />);

    expect(screen.getByText('Loading profile…')).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText('Email: test@example.com')).toBeInTheDocument();
      expect(screen.getByText('Subscription status: active')).toBeInTheDocument();
      expect(screen.getByText('is_active: true')).toBeInTheDocument();
      expect(screen.getByText('created_at: 2023-01-01T00:00:00Z')).toBeInTheDocument();
      expect(screen.getByText('updated_at: 2023-01-01T00:00:00Z')).toBeInTheDocument();
    });

    expect(mockClient.me).toHaveBeenCalledTimes(1);
  });

  it('handles 401 from me, clears token, and calls onUnauthorized', async () => {
    const mockAuthError: ApiError = {
      status: 401,
      message: 'Unauthorized',
    };
    mockClient.me.mockRejectedValue(mockAuthError);
    mockStorage.isAuthenticated.mockReturnValue(true); // Pre-seed token

    render(<AccountPage onUnauthorized={mockOnUnauthorized} onSignOut={mockOnSignOut} />);

    await waitFor(() => {
      expect(mockOnUnauthorized).toHaveBeenCalledTimes(1);
    });

    expect(mockStorage.clearToken).toHaveBeenCalledTimes(1);
    expect(mockClient.me).toHaveBeenCalledTimes(1);
  });

  it('handles 401 without onUnauthorized, shows session expired message', async () => {
    const mockAuthError: ApiError = {
      status: 401,
      message: 'Unauthorized',
    };
    mockClient.me.mockRejectedValue(mockAuthError);
    mockStorage.isAuthenticated.mockReturnValue(true);

    render(<AccountPage onSignOut={mockOnSignOut} />); // No onUnauthorized

    await waitFor(() => {
      expect(screen.getByText('Session expired. Please log in.')).toBeInTheDocument();
      expect(screen.getByText('Go to login')).toBeInTheDocument();
    });

    expect(mockStorage.clearToken).toHaveBeenCalledTimes(1);
  });

  it('sign out button clears token and calls onSignOut', async () => {
    render(<AccountPage onUnauthorized={mockOnUnauthorized} onSignOut={mockOnSignOut} />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Sign Out' })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: 'Sign Out' }));

    expect(mockStorage.clearToken).toHaveBeenCalledTimes(1);
    expect(mockOnSignOut).toHaveBeenCalledTimes(1);
  });

  it('retry on generic error', async () => {
    const mockGenericError: ApiError = {
      status: 500,
      message: 'Internal Server Error',
    };
    mockClient.me
      .mockRejectedValueOnce(mockGenericError)
      .mockResolvedValueOnce(mockUser);

    render(<AccountPage onUnauthorized={mockOnUnauthorized} onSignOut={mockOnSignOut} />);

    await waitFor(() => {
      expect(screen.getByText('Failed to load profile. Please try again.')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Retry' })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: 'Retry' }));

    await waitFor(() => {
      expect(screen.getByText('Email: test@example.com')).toBeInTheDocument();
    });

    expect(mockClient.me).toHaveBeenCalledTimes(2);
  });
});