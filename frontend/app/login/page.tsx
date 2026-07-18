import { LoginPage } from '@/components/auth/LoginPage';
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Sign In — ZentroApp',
  description: 'Sign in to your ZentroApp account.',
};

export default function LoginRoute() {
  return <LoginPage />;
}
