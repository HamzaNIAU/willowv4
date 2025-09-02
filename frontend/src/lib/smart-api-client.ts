/* Smart API Client with Intelligent Routing and Fallbacks */

// Smart environment detection for API routing
export const getSmartApiUrl = (): string => {
  // In browser environment
  if (typeof window !== 'undefined') {
    // Check environment variables first
    if (process.env.NEXT_PUBLIC_BACKEND_URL) {
      return process.env.NEXT_PUBLIC_BACKEND_URL;
    }
    
    // Auto-detect based on current hostname
    const hostname = window.location.hostname;
    const protocol = window.location.protocol;
    
    // Development patterns
    if (hostname === 'localhost' || hostname === '127.0.0.1') {
      return `${protocol}//${hostname}:8000`;
    }
    
    // Production patterns - adapt based on your deployment
    if (hostname.includes('vercel.app') || hostname.includes('netlify.app')) {
      // For deployed frontend, backend might be on different domain
      return process.env.NEXT_PUBLIC_BACKEND_URL || `${protocol}//${hostname}`;
    }
    
    // Default fallback
    return `${protocol}//${hostname}:8000`;
  }
  
  // Server-side environment
  return process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
};

// Smart API client with automatic retries and fallbacks
export const smartApiClient = {
  async get<T = any>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const baseUrl = getSmartApiUrl();
    const url = `${baseUrl}${endpoint.startsWith('/') ? endpoint : '/' + endpoint}`;
    
    try {
      console.log(`📡 Smart API GET: ${url}`);
      
      const response = await fetch(url, {
        ...options,
        headers: {
          'Content-Type': 'application/json',
          ...options.headers,
        },
      });
      
      if (response.ok) {
        const data = await response.json();
        console.log(`✅ API Success: ${endpoint}`);
        return data;
      } else {
        console.warn(`⚠️ API Error ${response.status}: ${endpoint}`);
        throw new Error(`API Error: ${response.status} ${response.statusText}`);
      }
    } catch (error) {
      console.error(`❌ API Call Failed: ${endpoint}`, error);
      
      // SMART FALLBACK: Try alternative URL patterns
      if (!url.includes(':8000')) {
        console.log('🔄 Trying backend port fallback...');
        const fallbackUrl = url.replace(/:3000/, ':8000');
        
        try {
          const fallbackResponse = await fetch(fallbackUrl, {
            ...options,
            headers: {
              'Content-Type': 'application/json',
              ...options.headers,
            },
          });
          
          if (fallbackResponse.ok) {
            console.log(`✅ Fallback Success: ${fallbackUrl}`);
            return await fallbackResponse.json();
          }
        } catch (fallbackError) {
          console.error('❌ Fallback also failed:', fallbackError);
        }
      }
      
      throw error;
    }
  },
  
  async post<T = any>(endpoint: string, data?: any, options: RequestInit = {}): Promise<T> {
    const baseUrl = getSmartApiUrl();
    const url = `${baseUrl}${endpoint.startsWith('/') ? endpoint : '/' + endpoint}`;
    
    try {
      console.log(`📡 Smart API POST: ${url}`);
      
      const response = await fetch(url, {
        method: 'POST',
        ...options,
        headers: {
          'Content-Type': 'application/json',
          ...options.headers,
        },
        body: data ? JSON.stringify(data) : undefined,
      });
      
      if (response.ok) {
        const result = await response.json();
        console.log(`✅ API Success: ${endpoint}`);
        return result;
      } else {
        console.warn(`⚠️ API Error ${response.status}: ${endpoint}`);
        throw new Error(`API Error: ${response.status} ${response.statusText}`);
      }
    } catch (error) {
      console.error(`❌ API Call Failed: ${endpoint}`, error);
      throw error;
    }
  }
};

// Environment info for debugging
export const getEnvironmentInfo = () => {
  return {
    apiUrl: getSmartApiUrl(),
    hostname: typeof window !== 'undefined' ? window.location.hostname : 'server',
    protocol: typeof window !== 'undefined' ? window.location.protocol : 'http:',
    environment: process.env.NODE_ENV,
    backendUrl: process.env.NEXT_PUBLIC_BACKEND_URL,
  };
};