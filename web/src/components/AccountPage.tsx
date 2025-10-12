import React, { useState, useEffect } from 'react';
import { createAuthClient } from '@fba-enterprise/auth-client/authClient';
import { createTokenStorage } from '@fba-enterprise/auth-client/tokenStorage';
import type { UserPublic } from '@fba-enterprise/auth-client/http';

interface AccountPageProps {
  onUnauthorized?: () => void;
  onSignOut?: () => void;
}

export default function AccountPage({ onUnauthorized, onSignOut }: AccountPageProps) {
  const [profile, setProfile] = useState<UserPublic | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const client = createAuthClient();
  const storage = createTokenStorage();

  useEffect(() => {
    const fetchProfile = async () => {
      setLoading(true);
      setError(null);
      try {
        const user = await client.me();
        setProfile(user);
      } catch (err: any) {
        if (err.status === 401) {
          storage.clearToken();
          if (onUnauthorized) {
            onUnauthorized();
          } else {
            setError('Session expired. Please log in.');
          }
        } else {
          setError('Failed to load profile. Please try again.');
        }
      } finally {
        setLoading(false);
      }
    };

    fetchProfile();
  }, [onUnauthorized, storage]);

  const handleSignOut = () => {
    storage.clearToken();
    setProfile(null);
    if (onSignOut) {
      onSignOut();
    } else {
      console.info('Signed out');
    }
  };

  const handleRetry = () => {
    const fetchProfile = async () => {
      setLoading(true);
      setError(null);
      try {
        const user = await client.me();
        setProfile(user);
      } catch (err: any) {
        if (err.status === 401) {
          storage.clearToken();
          if (onUnauthorized) {
            onUnauthorized();
          } else {
            setError('Session expired. Please log in.');
          }
        } else {
          setError('Failed to load profile. Please try again.');
        }
      } finally {
        setLoading(false);
      }
    };

    fetchProfile();
  };

  if (loading) {
    return (
      <div className="card" aria-busy="true" role="status">
        <h2>Account</h2>
        <p>Loading profile…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="card">
        <h2>Account</h2>
        <p>{error}</p>
        <button
          onClick={handleRetry}
          className="btn btn-secondary"
          style={{ backgroundColor: '#007bff', marginRight: '0.5rem' }}
        >
          Retry
        </button>
        {error.includes('expired') && !onUnauthorized && (
          <button
            onClick={() => window.location.href = '/'}
            className="btn btn-secondary"
            style={{ backgroundColor: '#6c757d' }}
          >
            Go to login
          </button>
        )}
      </div>
    );
  }

  if (!profile) {
    return (
      <div className="card">
        <h2>Account</h2>
        <p>No profile data available.</p>
      </div>
    );
  }

  return (
    <div className="card">
      <h2>Account</h2>
      <p><strong>Email:</strong> {profile.email}</p>
      <p><strong>Subscription status:</strong> {profile.subscription_status || 'none'}</p>
      <p><strong>is_active:</strong> {profile.is_active ? 'true' : 'false'}</p>
      <p><strong>created_at:</strong> {profile.created_at}</p>
      <p><strong>updated_at:</strong> {profile.updated_at}</p>
      <button
        onClick={handleSignOut}
        className="btn btn-secondary"
        style={{ backgroundColor: '#dc3545', marginTop: '1rem' }}
      >
        Sign Out
      </button>
    </div>
  );
}