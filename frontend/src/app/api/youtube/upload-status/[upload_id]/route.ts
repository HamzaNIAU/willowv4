import { NextRequest, NextResponse } from 'next/server';

// Use backend:8000 when running in Docker, localhost:8000 otherwise
const BACKEND_URL = process.env.BACKEND_INTERNAL_URL || process.env.NEXT_PUBLIC_BACKEND_URL || 'http://backend:8000/api';

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ upload_id: string }> }
) {
  try {
    const { upload_id } = await params;
    console.log(`[YouTube Upload Status API] Fetching status for upload: ${upload_id}`);
    
    // Get auth token from request headers
    const authHeader = request.headers.get('authorization');
    if (!authHeader) {
      console.log('[YouTube Upload Status API] No authorization header provided');
      return NextResponse.json(
        { error: 'Authorization header required' },
        { status: 401 }
      );
    }
    
    // Simple proxy to backend (BACKEND_URL already includes /api)
    const backendUrl = `${BACKEND_URL}/youtube/upload-status/${upload_id}`;
    console.log(`[YouTube Upload Status API] Proxying to backend: ${backendUrl}`);
    
    const backendResponse = await fetch(backendUrl, {
      headers: {
        'Authorization': authHeader,
        'Content-Type': 'application/json',
      },
      cache: 'no-store',
    });
    
    console.log(`[YouTube Upload Status API] Backend response status: ${backendResponse.status}`);
    
    // Handle different response statuses
    if (backendResponse.status === 404) {
      // Upload not found - might still be initializing
      return NextResponse.json({
        success: false,
        error: 'Upload not found',
        message: 'Upload is being initialized, please wait...',
        status: 'initializing'
      }, { status: 404 });
    }
    
    if (backendResponse.status === 500) {
      // Internal server error - log it and return a user-friendly message
      const errorText = await backendResponse.text();
      console.error(`[YouTube Upload Status API] Backend error: ${errorText}`);
      
      return NextResponse.json({
        success: false,
        error: 'Server error',
        message: 'Unable to fetch upload status. The upload may still be processing.',
        status: 'unknown'
      }, { status: 500 });
    }
    
    // Return successful response
    const data = await backendResponse.json();
    return NextResponse.json(data, { status: backendResponse.status });
    
  } catch (error) {
    console.error('[YouTube Upload Status API] Error:', error);
    return NextResponse.json(
      { 
        error: 'Internal server error',
        message: error instanceof Error ? error.message : 'Unknown error'
      },
      { status: 500 }
    );
  }
}