'use client';

import Image from 'next/image';
import { useTheme } from 'next-themes';
import { useEffect, useState } from 'react';

interface WillowLogoProps {
  size?: number;
}

export function WillowLogo({ size = 24 }: WillowLogoProps) {
  const { theme, systemTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  // After mount, we can access the theme
  useEffect(() => {
    setMounted(true);
  }, []);

  const isDarkMode = mounted && (
    theme === 'dark' || (theme === 'system' && systemTheme === 'dark')
  );

  // Use appropriate logo for theme - willow.svg for light mode, willow2.svg for dark mode
  const logoSrc = isDarkMode ? '/willow2.svg' : '/willow.svg';

  return (
    <Image
        src={logoSrc}
        alt="Willow"
        width={size}
        height={size}
        className="flex-shrink-0"
        style={{ width: size, height: size, minWidth: size, minHeight: size }}
      />
  );
}