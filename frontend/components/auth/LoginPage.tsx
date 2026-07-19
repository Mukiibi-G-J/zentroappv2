'use client';

import { Suspense, useEffect, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { Building2, Lock, Eye, EyeOff, ArrowRight, User } from 'lucide-react';
import { cn } from '@/lib/utils';
import axios from 'axios';
import api, { setAccessTokenCookie } from '@/lib/api';
import { clearCookiesThatCause431 } from '@/lib/clearBloatedCookies';
import { fetchAuthSession, type TokenLoginResponse } from '@/services/auth.service';
import { writeStoredSession } from '@/lib/session';
import { applyLoginBranchState } from '@/lib/loginBranch'
import { resolvePostLoginPath } from '@/lib/postLoginRedirect'
import { buildMainAppUrl, tenantSlugFromHostname } from '@/lib/tenantUrl';
import { ensureTenantWorkspaceExists } from '@/lib/ensureTenantWorkspace';

function LoginForm() {
  const searchParams = useSearchParams();
  const redirectTo = searchParams.get('redirect');
  const emailFromQuery = (searchParams.get('email') || '').trim();
  const [workspaceSlug, setWorkspaceSlug] = useState<string | null>(null);
  const [workspacePickerUrl, setWorkspacePickerUrl] = useState('/workspace');

  useEffect(() => {
    // Oversized Cookie headers on *.localhost make /api/auth/token/ return 431.
    clearCookiesThatCause431();
    setWorkspaceSlug(tenantSlugFromHostname(window.location.hostname));
    setWorkspacePickerUrl(buildMainAppUrl('/workspace'));
    void ensureTenantWorkspaceExists();
  }, []);

  const [formData, setFormData] = useState({ email: emailFromQuery, password: '' });
  const [showPassword, setShowPassword] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
    if (error) setError(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setError(null);
    try {
      const res = await api.post<TokenLoginResponse>('/api/auth/token/', {
        email: formData.email.trim(),
        password: formData.password,
      });

      if (res.data.otp_channel) {
        const params = new URLSearchParams({
          email: formData.email.trim(),
        });
        params.set('otp_channel', res.data.otp_channel);
        window.location.replace(`/verify-otp?${params.toString()}`);
        return;
      }

      localStorage.setItem('access_token', res.data.access);
      setAccessTokenCookie(res.data.access);
      if (res.data.refresh) localStorage.setItem('refresh_token', res.data.refresh);

      try {
        const session = await fetchAuthSession();
        writeStoredSession(session);
        applyLoginBranchState(res.data.access, session);
      } catch {
        applyLoginBranchState(res.data.access, null);
      }

      const destination = resolvePostLoginPath(res.data.access, {
        mustChangePassword: res.data.must_change_password,
        redirectTo,
      })
      // Full navigation so middleware receives the session cookie on the first dashboard request.
      window.location.replace(destination)
    } catch (err) {
      const status = axios.isAxiosError(err) ? err.response?.status : undefined
      if (status === 431) {
        clearCookiesThatCause431()
        setError(
          'Login blocked by oversized browser cookies (HTTP 431). Cookies were cleared — try Sign In again.',
        )
      } else {
        setError('Invalid username or password. Please try again.')
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-s1/5 via-white to-s2/5 flex items-center justify-center p-4">
      <div className="w-full max-w-md rounded-lg border border-strokeColor bg-white text-mainTextColor shadow-sm p-8">
        {/* Logo / Brand */}
        <div className="text-center mb-8">
          <div className="w-16 h-16 bg-s1 rounded-full flex items-center justify-center mx-auto mb-4">
            <Building2 className="w-8 h-8 text-white" />
          </div>
          <h1 className="text-2xl font-bold text-mainTextColor mb-2">
            {workspaceSlug ? (
              <>
                Sign in to{' '}
                <span className="text-s1">{workspaceSlug}</span>
              </>
            ) : (
              'Welcome to ZentroApp'
            )}
          </h1>
          <p className="text-bodyText">
            {workspaceSlug
              ? 'Enter your credentials for this workspace'
              : 'Sign in to access your ERP dashboard'}
          </p>
        </div>

        {/* Error */}
        {error && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg">
            <p className="text-red-600 text-sm">{error}</p>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Email or Phone */}
          <div>
            <label
              htmlFor="email"
              className="block text-sm font-medium text-mainTextColor mb-2"
            >
              Email or Phone
            </label>
            <div className="relative">
              <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-bodyText" />
              <input
                id="email"
                name="email"
                type="text"
                value={formData.email}
                onChange={handleInputChange}
                placeholder="you@company.com or 0700123456"
                autoComplete="email"
                required
                className={cn(
                  'flex h-10 w-full rounded-lg border border-strokeColor bg-white pl-10 pr-3 py-2',
                  'text-sm text-mainTextColor placeholder:text-bodyText',
                  'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-s2 focus-visible:ring-offset-2',
                  'disabled:cursor-not-allowed disabled:opacity-50',
                )}
              />
            </div>
          </div>

          {/* Password */}
          <div>
            <label
              htmlFor="password"
              className="block text-sm font-medium text-mainTextColor mb-2"
            >
              Password
            </label>
            <div className="relative">
              <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-bodyText" />
              <input
                id="password"
                name="password"
                type={showPassword ? 'text' : 'password'}
                value={formData.password}
                onChange={handleInputChange}
                placeholder="Enter your password"
                autoComplete="current-password"
                required
                className={cn(
                  'flex h-10 w-full rounded-lg border border-strokeColor bg-white pl-10 pr-10 py-2',
                  'text-sm text-mainTextColor placeholder:text-bodyText',
                  'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-s2 focus-visible:ring-offset-2',
                  'disabled:cursor-not-allowed disabled:opacity-50',
                )}
              />
              <button
                type="button"
                onClick={() => setShowPassword(v => !v)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-bodyText hover:text-mainTextColor"
                tabIndex={-1}
              >
                {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
            <div className="mt-2 flex justify-end">
              <a
                href="/forgot-password"
                className="text-sm font-medium text-s1 hover:text-s2"
              >
                Forgot Password?
              </a>
            </div>
          </div>

          {/* Submit */}
          <button
            type="submit"
            disabled={isSubmitting}
            className={cn(
              'inline-flex items-center justify-center w-full h-10 px-4 rounded-lg',
              'text-sm font-medium text-white bg-s1 hover:bg-s1/90 transition-colors',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-s2 focus-visible:ring-offset-2',
              'disabled:opacity-50 disabled:pointer-events-none',
            )}
          >
            {isSubmitting ? (
              <>
                <svg
                  className="mr-2 h-4 w-4 animate-spin"
                  xmlns="http://www.w3.org/2000/svg"
                  fill="none"
                  viewBox="0 0 24 24"
                >
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                  />
                </svg>
                Signing in...
              </>
            ) : (
              <>
                Sign In
                <ArrowRight className="w-4 h-4 ml-2" />
              </>
            )}
          </button>
        </form>

        <div className="mt-6 text-center space-y-2">
          <p className="text-sm text-bodyText">
            Wrong workspace?{' '}
            <a href={workspacePickerUrl} className="text-s1 hover:text-s2 font-medium">
              Switch company
            </a>
          </p>
          <p className="text-sm text-bodyText">
            Need access?{' '}
            <a href="mailto:info@zentroapp.com" className="text-s1 hover:text-s2 font-medium">
              Contact support
            </a>
          </p>
        </div>
      </div>
    </div>
  );
}

export function LoginPage() {
  return (
    <Suspense fallback={<div className="min-h-screen flex items-center justify-center">Loading…</div>}>
      <LoginForm />
    </Suspense>
  );
}
