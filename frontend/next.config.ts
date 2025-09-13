import type { NextConfig } from 'next';

const nextConfig = (): NextConfig => ({
  output: (process.env.NEXT_OUTPUT as 'standalone') || undefined,
  eslint: {
    // Avoid failing production builds due to lint warnings
    ignoreDuringBuilds: true,
  },
  typescript: {
    // Do not block production builds on TS type errors
    ignoreBuildErrors: true,
  },
  async rewrites() {
    return [
      {
        source: '/ingest/static/:path*',
        destination: 'https://eu-assets.i.posthog.com/static/:path*',
      },
      {
        source: '/ingest/:path*',
        destination: 'https://eu.i.posthog.com/:path*',
      },
      {
        source: '/ingest/flags',
        destination: 'https://eu.i.posthog.com/flags',
      },
    ];
  },
  skipTrailingSlashRedirect: true,
});

export default nextConfig;
