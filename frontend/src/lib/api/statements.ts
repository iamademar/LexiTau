export interface Statement {
  id: number
  client_id: number
  progress: number
  status: 'pending' | 'processing' | 'completed' | 'failed'
  uploaded_at: string
  file_path: string
  ocr_text?: string | null
}

export interface StatementProgress {
  progress: number
  status: 'pending' | 'processing' | 'completed' | 'failed'
}

export interface Transaction {
  id: number
  date: string
  payee: string
  amount: number
  type: string
  balance?: number | null
  currency: string
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

export async function fetchStatements(): Promise<Statement[]> {
  const response = await fetch(`${API_BASE_URL}/statements/`)
  return handleApiResponse<Statement[]>(response)
}

export async function uploadStatement(clientId: number, file: File): Promise<Statement> {
  const formData = new FormData()
  formData.append('file', file)
  
  const response = await fetch(`${API_BASE_URL}/statements/?client_id=${clientId}`, {
    method: 'POST',
    body: formData,
  })
  
  return handleApiResponse<Statement>(response)
}

export async function fetchStatementProgress(statementId: number): Promise<StatementProgress> {
  const response = await fetch(`${API_BASE_URL}/statements/${statementId}/progress`)
  return handleApiResponse<StatementProgress>(response)
}

export async function fetchStatementTransactions(statementId: number): Promise<Transaction[]> {
  const response = await fetch(`${API_BASE_URL}/statements/${statementId}/transactions`)
  return handleApiResponse<Transaction[]>(response)
}

export async function fetchStatement(statementId: number): Promise<Statement> {
  const response = await fetch(`${API_BASE_URL}/statements/${statementId}`)
  return handleApiResponse<Statement>(response)
}