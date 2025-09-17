export interface Client {
  id: number
  name: string
  contact_name: string | null
  contact_email: string | null
  created_at: string
}

export interface ClientCreate {
  name: string
  contact_name?: string | null
  contact_email?: string | null
}

export interface ClientUpdate {
  name?: string | null
  contact_name?: string | null
  contact_email?: string | null
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

async function handleApiResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const error = await response.text()
    throw new Error(`API Error: ${response.status} - ${error}`)
  }
  
  if (response.status === 204) {
    return {} as T
  }
  
  return response.json()
}

export async function fetchClients(): Promise<Client[]> {
  const response = await fetch(`${API_BASE_URL}/clients/`)
  return handleApiResponse<Client[]>(response)
}

export async function fetchClient(id: number): Promise<Client> {
  const response = await fetch(`${API_BASE_URL}/clients/${id}`)
  return handleApiResponse<Client>(response)
}

export async function createClient(data: ClientCreate): Promise<Client> {
  const response = await fetch(`${API_BASE_URL}/clients/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  })
  return handleApiResponse<Client>(response)
}

export async function updateClient(id: number, data: ClientUpdate): Promise<Client> {
  const response = await fetch(`${API_BASE_URL}/clients/${id}`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  })
  return handleApiResponse<Client>(response)
}

export async function deleteClient(id: number): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/clients/${id}`, {
    method: 'DELETE',
  })
  return handleApiResponse<void>(response)
}