import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { NextRequest } from 'next/server';
import { POST } from '../src/app/api/chat/route';

// Mock environment variables
const mockEnv = vi.hoisted(() => ({
  BACKEND_URL: 'http://localhost:8001',
}));

vi.stubEnv('BACKEND_URL', mockEnv.BACKEND_URL);

// Mock fetch globally
const mockFetch = vi.fn();
global.fetch = mockFetch;

describe('/api/chat route', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  const createMockRequest = (body: any) => {
    return new NextRequest('http://localhost:3000/api/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    });
  };

  it('should return 200 with passthrough body when backend returns success', async () => {
    const requestBody = {
      messages: [
        { role: 'user', content: 'Hello' },
      ],
    };

    const backendResponse = {
      choices: [{ message: { role: 'assistant', content: 'Hi there!' } }],
    };

    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      headers: new Headers({ 'content-type': 'application/json' }),
      text: () => Promise.resolve(JSON.stringify(backendResponse)),
    });

    const request = createMockRequest(requestBody);
    const response = await POST(request);

    expect(response.status).toBe(200);
    expect(response.headers.get('Cache-Control')).toBe('no-store');
    expect(response.headers.get('Content-Type')).toBe('application/json');

    const responseBody = await response.json();
    expect(responseBody).toEqual(backendResponse);

    expect(mockFetch).toHaveBeenCalledWith(
      'http://localhost:8001/vanna/analysis',
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestBody),
      }
    );
  });

  it('should return 500 with same status and body when backend returns error', async () => {
    const requestBody = {
      messages: [
        { role: 'user', content: 'Hello' },
      ],
    };

    const backendErrorResponse = {
      error: 'Internal server error',
    };

    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
      headers: new Headers({ 'content-type': 'application/json' }),
      text: () => Promise.resolve(JSON.stringify(backendErrorResponse)),
    });

    const request = createMockRequest(requestBody);
    const response = await POST(request);

    expect(response.status).toBe(500);
    expect(response.headers.get('Cache-Control')).toBe('no-store');
    expect(response.headers.get('Content-Type')).toBe('application/json');

    const responseBody = await response.json();
    expect(responseBody).toEqual(backendErrorResponse);
  });

  it('should return 502 JSON error when network error occurs', async () => {
    const requestBody = {
      messages: [
        { role: 'user', content: 'Hello' },
      ],
    };

    mockFetch.mockRejectedValueOnce(new Error('Network error'));

    const request = createMockRequest(requestBody);
    const response = await POST(request);

    expect(response.status).toBe(502);
    expect(response.headers.get('Cache-Control')).toBe('no-store');

    const responseBody = await response.json();
    expect(responseBody).toEqual({
      error: 'Failed to connect to backend service',
    });
  });

  it('should return 400 for invalid request format', async () => {
    const invalidRequestBody = {
      messages: [
        { role: 'invalid_role', content: 'Hello' }, // Invalid role
      ],
    };

    const request = createMockRequest(invalidRequestBody);
    const response = await POST(request);

    expect(response.status).toBe(400);

    const responseBody = await response.json();
    expect(responseBody).toEqual({
      error: 'Invalid request format',
    });

    // Should not make backend call for invalid requests
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it('should return 500 when BACKEND_URL is not configured', async () => {
    // Temporarily unset the environment variable
    vi.stubEnv('BACKEND_URL', '');

    const requestBody = {
      messages: [
        { role: 'user', content: 'Hello' },
      ],
    };

    const request = createMockRequest(requestBody);
    const response = await POST(request);

    expect(response.status).toBe(500);

    const responseBody = await response.json();
    expect(responseBody).toEqual({
      error: 'Backend URL not configured',
    });

    // Restore environment variable
    vi.stubEnv('BACKEND_URL', mockEnv.BACKEND_URL);
  });

  it('should preserve content-type from backend response', async () => {
    const requestBody = {
      messages: [
        { role: 'user', content: 'Hello' },
      ],
    };

    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      headers: new Headers({ 'content-type': 'text/plain' }),
      text: () => Promise.resolve('Plain text response'),
    });

    const request = createMockRequest(requestBody);
    const response = await POST(request);

    expect(response.status).toBe(200);
    expect(response.headers.get('Content-Type')).toBe('text/plain');
    expect(response.headers.get('Cache-Control')).toBe('no-store');

    const responseBody = await response.text();
    expect(responseBody).toBe('Plain text response');
  });

  it('should handle requests without messages field', async () => {
    const requestBody = {
      query: 'What is the weather?',
      // No messages field
    };

    const backendResponse = { result: 'Sunny' };

    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      headers: new Headers({ 'content-type': 'application/json' }),
      text: () => Promise.resolve(JSON.stringify(backendResponse)),
    });

    const request = createMockRequest(requestBody);
    const response = await POST(request);

    expect(response.status).toBe(200);
    
    const responseBody = await response.json();
    expect(responseBody).toEqual(backendResponse);

    expect(mockFetch).toHaveBeenCalledWith(
      'http://localhost:8001/vanna/analysis',
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestBody),
      }
    );
  });
});
