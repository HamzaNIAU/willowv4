import { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Create Agent | Rzvi',
  description: 'Create an agent',
  openGraph: {
    title: 'Create Agent | Rzvi',
    description: 'Create an agent',
    type: 'website',
  },
};

export default async function NewAgentLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
