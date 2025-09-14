import { NextRequest, NextResponse } from 'next/server';
import { z } from 'zod';

// Request validation schema
const ChatRequestSchema = z.object({
  messages: z.array(z.object({
    role: z.enum(['user', 'assistant', 'system']),
    content: z.string(),
  })).optional(),
  // Allow other fields for flexibility
}).passthrough();

export async function POST(request: NextRequest) {
  try {
    // Parse and validate request body
    const body = await request.json();
    
    try {
      ChatRequestSchema.parse(body);
    } catch (validationError) {
      return NextResponse.json(
        { error: 'Invalid request format' },
        { status: 400 }
      );
    }

    const backendUrl = process.env.BACKEND_URL;
    if (!backendUrl) {
      return NextResponse.json(
        { error: 'Backend URL not configured' },
        { status: 500 }
      );
    }

    // Forward request to backend
    const response = await fetch(`${backendUrl}/vanna/analysis`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    });

    // Get response body
    const responseBody = await response.text();
    
    // Determine content type from backend response
    const contentType = response.headers.get('content-type') || 'application/json';

    // Return response with same status and body, adding no-store cache control
    return new NextResponse(responseBody, {
      status: response.status,
      headers: {
        'Content-Type': contentType,
        'Cache-Control': 'no-store',
      },
    });

  } catch (error) {
    // Network errors or other failures
    console.error('Chat proxy error:', error);
    return NextResponse.json(
      { error: 'Failed to connect to backend service' },
      { 
        status: 502,
        headers: {
          'Cache-Control': 'no-store',
        },
      }
    );
  }
}
