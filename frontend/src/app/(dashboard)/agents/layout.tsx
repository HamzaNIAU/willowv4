import { agentPlaygroundFlagFrontend } from '@/flags';
import { isFlagEnabled } from '@/lib/feature-flags';
import { Metadata } from 'next';
import { redirect } from 'next/navigation';

export const metadata: Metadata = {
  title: 'Agent Conversation | Rzvi Willow',
  description: 'Interactive agent conversation powered by Rzvi Willow',
  openGraph: {
    title: 'Agent Conversation | Rzvi Willow',
    description: 'Interactive agent conversation powered by Rzvi Willow',
    type: 'website',
  },
};

export default async function AgentsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
