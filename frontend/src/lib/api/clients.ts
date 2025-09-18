// Client-side safe functions that use the proxy route

/** Match backend shape */
export interface Client {
  id: number;
  name: string;
  business_id: number;
  created_at: string;
  // keep these optional so existing UI that reads them doesn't crash
  contact_name?: string | null;
  contact_email?: string | null;
}

export interface ClientCreate {
  name: string;
}

/** If you keep this type, it won't be used for now */
export interface ClientUpdate {
  name?: string | null;
  contact_name?: string | null;
  contact_email?: string | null;
}

/** Shared response handler */
async function handleApiResponse<T>(resp: Response): Promise<T> {
  if (!resp.ok) {
    const error = await resp.text().catch(() => "");
    throw new Error(`API Error: ${resp.status} - ${error || resp.statusText}`);
  }
  if (resp.status === 204) return {} as T;
  return resp.json();
}

/** List clients (GET /clients) - Client-safe via proxy route */
export async function fetchClients(): Promise<Client[]> {
  const resp = await fetch("/api/clients", {
    method: "GET",
    cache: "no-store"
  });
  return handleApiResponse<Client[]>(resp);
}

/** Create client (POST /clients) - Client-safe via proxy route */
export async function createClient(data: ClientCreate): Promise<Client> {
  const resp = await fetch("/api/clients", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name: data.name }), // backend expects only { name }
    cache: "no-store"
  });
  return handleApiResponse<Client>(resp);
}

/** Not available on backend yet – keep exports to avoid breaking imports */
export async function fetchClient(id: number): Promise<Client> {
  throw new Error(`Fetching client ${id} by id is not supported yet.`);
}

export async function updateClient(id: number, data: ClientUpdate): Promise<Client> {
  throw new Error(`Updating client ${id} is not supported yet. Data: ${JSON.stringify(data)}`);
}

/** Keep deleteClient, but make it a safe stub for now */
export async function deleteClient(id: number): Promise<void> {
  // Intentionally not calling the backend (no endpoint yet)
  // Reject so callers can surface a clear message.
  return Promise.reject(new Error(`Deleting client ${id} is not supported yet.`));
}