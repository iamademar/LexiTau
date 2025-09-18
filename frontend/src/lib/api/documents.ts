// frontend/src/lib/api/documents.ts

/** Backend enum mirrors (string unions are simplest for TS-side) */
export type FileType = "PDF" | "JPG" | "PNG";
export type DocumentType = "INVOICE" | "RECEIPT";
export type DocumentStatus = "PENDING" | "PROCESSING" | "COMPLETED" | "FAILED";
export type DocumentClassification = "REVENUE" | "EXPENSE";

/** Shapes mirrored from backend schemas */
export interface Document {
  id: string;                // UUID
  user_id: number;
  business_id: number;
  filename: string;
  file_url: string;
  file_type: FileType;
  document_type: DocumentType;
  classification: DocumentClassification;
  status: DocumentStatus;
  confidence_score?: number | null;
  reviewed_at?: string | null;
  reviewed_by?: number | null;
  is_reviewed: boolean;
  created_at: string;
  updated_at?: string | null;
}

export interface PaginationMeta {
  page: number;
  per_page: number;
  total_items: number;
  total_pages: number;
  has_next: boolean;
  has_prev: boolean;
}

export interface DocumentListResponse {
  documents: Document[];
  pagination: PaginationMeta;
}

export interface DocumentUploadResult {
  success: boolean;
  filename: string;
  document_id?: string | null;
  blob_url?: string | null;
  error_message?: string | null;
  file_size?: number | null;
  file_type?: FileType | null;
}

export interface DocumentUploadResponse {
  total_files: number;
  successful_uploads: number;
  failed_uploads: number;
  results: DocumentUploadResult[];
}

async function handleApiResponse<T>(resp: Response): Promise<T> {
  if (!resp.ok) {
    const txt = await resp.text().catch(() => "");
    throw new Error(`API Error: ${resp.status} - ${txt || resp.statusText}`);
  }
  if (resp.status === 204) return {} as T;
  return resp.json();
}

export interface ListDocumentsParams {
  page?: number;
  per_page?: number;
  status?: DocumentStatus;
  document_type?: DocumentType;
  classification?: DocumentClassification;
  is_reviewed?: boolean;
  client_id?: number;
  project_id?: number;
  category_id?: number;
}

/** GET /documents via proxy */
export async function listDocuments(params: ListDocumentsParams = {}): Promise<DocumentListResponse> {
  const qs = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null) qs.set(k, String(v));
  });

  const resp = await fetch(`/api/documents${qs.toString() ? `?${qs.toString()}` : ""}`, {
    method: "GET",
    cache: "no-store",
  });
  return handleApiResponse<DocumentListResponse>(resp);
}

/** POST /documents/upload via proxy (multipart; field name "files") */
export async function uploadDocuments(files: File[]): Promise<DocumentUploadResponse> {
  if (!files.length) throw new Error("Please select at least one file.");
  const form = new FormData();
  for (const f of files) form.append("files", f);

  const resp = await fetch("/api/documents/upload", {
    method: "POST",
    body: form,
    cache: "no-store",
  });
  return handleApiResponse<DocumentUploadResponse>(resp);
}

/** GET /documents/{id} via proxy */
export async function fetchDocument(id: string): Promise<Document> {
  const resp = await fetch(`/api/documents/${id}`, { method: "GET", cache: "no-store" });
  return handleApiResponse<Document>(resp);
}