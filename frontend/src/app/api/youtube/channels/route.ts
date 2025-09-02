// Next.js API Route - Smart Proxy for YouTube Channels
// Provides intelligent routing with fallbacks

import { NextRequest, NextResponse } from 'next/server';

// Use backend:8000 when running in Docker, localhost:8000 otherwise
const BACKEND_URL = process.env.BACKEND_INTERNAL_URL || process.env.NEXT_PUBLIC_BACKEND_URL || 'http://backend:8000/api';

export async function GET(request: NextRequest) {
  try {
    // Get auth token from request headers
    const authHeader = request.headers.get('authorization');
    if (!authHeader) {
      return NextResponse.json(
        { error: 'Authorization header required' },
        { status: 401 }
      );
    }
    
    console.log('📡 API Proxy: Fetching YouTube channels');
    
    try {
      // Proxy to backend API (BACKEND_URL already includes /api)
      const backendResponse = await fetch(`${BACKEND_URL}/youtube/channels`, {
        headers: {
          'Authorization': authHeader,
          'Content-Type': 'application/json',
        },
        cache: 'no-store',
      });
      
      if (backendResponse.ok) {
        const data = await backendResponse.json();
        console.log('✅ YouTube channels proxy success');
        
        return NextResponse.json({
          ...data,
          _proxy_info: {
            source: 'backend_api_proxy',
            backend_url: BACKEND_URL,
            success: true
          }
        });
      } else {
        const errorText = await backendResponse.text();
        console.error(`❌ Backend returned ${backendResponse.status}: ${errorText}`);
        
        return NextResponse.json(
          { 
            error: `Backend API error: ${backendResponse.status}`,
            details: errorText,
            _proxy_info: {
              source: 'backend_error',
              success: false
            }
          },
          { status: backendResponse.status }
        );
      }
    } catch (error) {
      console.error('❌ Backend API call failed:', error);
      
      return NextResponse.json(
        { 
          error: 'Failed to reach backend API',
          details: error instanceof Error ? error.message : 'Network error',
          _proxy_info: {
            source: 'network_error',
            backend_url: BACKEND_URL,
            success: false
          }
        },
        { status: 503 }
      );
    }
    
  } catch (error) {
    console.error('❌ API proxy error:', error);
    return NextResponse.json(
      { 
        error: 'Internal proxy error',
        details: error instanceof Error ? error.message : 'Unknown error'
      },
      { status: 500 }
    );
  }
}