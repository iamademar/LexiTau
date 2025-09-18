'use client'

import { useState, useEffect, useCallback } from 'react'
import { useParams } from 'next/navigation'
import {
  fetchDocument,
  type Document
} from '@/lib/api/documents'
import { fetchClients, type Client } from '@/lib/api/clients'
import { SidebarTrigger } from "@/components/ui/sidebar"
import { Separator } from "@/components/ui/separator"
import { Breadcrumb, BreadcrumbItem, BreadcrumbLink, BreadcrumbList, BreadcrumbPage, BreadcrumbSeparator } from "@/components/ui/breadcrumb"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { FileText, Clock, CheckCircle, XCircle, AlertCircle } from 'lucide-react'

const StatusIcon = ({ status }: { status: Document['status'] }) => {
  switch (status) {
    case 'PENDING':
      return <Clock className="h-5 w-5 text-gray-500" />
    case 'PROCESSING':
      return <AlertCircle className="h-5 w-5 text-blue-500" />
    case 'COMPLETED':
      return <CheckCircle className="h-5 w-5 text-green-500" />
    case 'FAILED':
      return <XCircle className="h-5 w-5 text-red-500" />
    default:
      return <Clock className="h-5 w-5 text-gray-500" />
  }
}

const StatusBadge = ({ status }: { status: Document['status'] }) => {
  const variants = {
    PENDING: 'secondary',
    PROCESSING: 'default',
    COMPLETED: 'success',
    FAILED: 'destructive'
  } as const

  return (
    <Badge variant={variants[status] || 'secondary'}>
      {status.toLowerCase()}
    </Badge>
  )
}

export default function DocumentDetailPage() {
  const params = useParams()
  const documentId = params.id as string

  const [document, setDocument] = useState<Document | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Load initial data
  const loadInitialData = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)

      const documentData = await fetchDocument(documentId)
      setDocument(documentData)

    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load document')
    } finally {
      setLoading(false)
    }
  }, [documentId])

  // Load initial data on mount
  useEffect(() => {
    loadInitialData()
  }, [loadInitialData])

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  }

  if (loading) {
    return (
      <>
        <header className="flex h-16 shrink-0 items-center gap-2 border-b px-4">
          <SidebarTrigger />
          <Separator orientation="vertical" className="mr-2 h-4" />
          <Breadcrumb>
            <BreadcrumbList>
              <BreadcrumbItem className="hidden md:block">
                <BreadcrumbLink href="#">LexExtract</BreadcrumbLink>
              </BreadcrumbItem>
              <BreadcrumbSeparator className="hidden md:block" />
              <BreadcrumbItem>
                <BreadcrumbLink href="/documents">Documents</BreadcrumbLink>
              </BreadcrumbItem>
              <BreadcrumbSeparator className="hidden md:block" />
              <BreadcrumbItem>
                <BreadcrumbPage>Loading...</BreadcrumbPage>
              </BreadcrumbItem>
            </BreadcrumbList>
          </Breadcrumb>
        </header>
        <div className="container mx-auto p-6 max-w-6xl">
          <div className="space-y-6">
            <Skeleton className="h-8 w-48" />
            <Skeleton className="h-32 w-full" />
            <Skeleton className="h-64 w-full" />
          </div>
        </div>
      </>
    )
  }

  if (error || !document) {
    return (
      <>
        <header className="flex h-16 shrink-0 items-center gap-2 border-b px-4">
          <SidebarTrigger />
          <Separator orientation="vertical" className="mr-2 h-4" />
          <Breadcrumb>
            <BreadcrumbList>
              <BreadcrumbItem className="hidden md:block">
                <BreadcrumbLink href="#">LexExtract</BreadcrumbLink>
              </BreadcrumbItem>
              <BreadcrumbSeparator className="hidden md:block" />
              <BreadcrumbItem>
                <BreadcrumbLink href="/documents">Documents</BreadcrumbLink>
              </BreadcrumbItem>
              <BreadcrumbSeparator className="hidden md:block" />
              <BreadcrumbItem>
                <BreadcrumbPage>Error</BreadcrumbPage>
              </BreadcrumbItem>
            </BreadcrumbList>
          </Breadcrumb>
        </header>
        <div className="container mx-auto p-6 max-w-6xl">
          <div className="text-center py-8 text-red-600">
            <p>Error: {error || 'Document not found'}</p>
          </div>
        </div>
      </>
    )
  }

  return (
    <>
        <header className="flex h-16 shrink-0 items-center gap-2 border-b px-4">
          <SidebarTrigger />
          <Separator orientation="vertical" className="mr-2 h-4" />
          <Breadcrumb>
            <BreadcrumbList>
              <BreadcrumbItem className="hidden md:block">
                <BreadcrumbLink href="#">LexExtract</BreadcrumbLink>
              </BreadcrumbItem>
              <BreadcrumbSeparator className="hidden md:block" />
              <BreadcrumbItem>
                <BreadcrumbLink href="/documents">Documents</BreadcrumbLink>
              </BreadcrumbItem>
              <BreadcrumbSeparator className="hidden md:block" />
              <BreadcrumbItem>
                <BreadcrumbPage>{document.filename}</BreadcrumbPage>
              </BreadcrumbItem>
            </BreadcrumbList>
          </Breadcrumb>
        </header>

        <div className="container mx-auto p-6 max-w-6xl space-y-6">
          {/* Document Header */}
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <FileText className="h-8 w-8 text-blue-500" />
              <div>
                <h1 className="text-3xl font-bold">{document.filename}</h1>
                <p className="text-gray-600">
                  Uploaded {formatDate(document.created_at)}
                </p>
              </div>
            </div>
          </div>

          {/* Document Details Card */}
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  <StatusIcon status={document.status} />
                  <CardTitle>Document Details</CardTitle>
                </div>
                <StatusBadge status={document.status} />
              </div>
              <CardDescription>
                {document.status === 'PENDING' && 'Document is queued for processing'}
                {document.status === 'PROCESSING' && 'Processing document...'}
                {document.status === 'COMPLETED' && 'Document processing completed successfully'}
                {document.status === 'FAILED' && 'Document processing failed'}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-sm font-medium text-gray-500">File Type</label>
                  <p className="text-sm font-mono">{document.file_type}</p>
                </div>
                <div>
                  <label className="text-sm font-medium text-gray-500">Document Type</label>
                  <p className="text-sm">{document.document_type}</p>
                </div>
                <div>
                  <label className="text-sm font-medium text-gray-500">Classification</label>
                  <p className="text-sm">{document.classification}</p>
                </div>
                {document.confidence_score && (
                  <div>
                    <label className="text-sm font-medium text-gray-500">Confidence Score</label>
                    <p className="text-sm">{(document.confidence_score * 100).toFixed(1)}%</p>
                  </div>
                )}
                <div>
                  <label className="text-sm font-medium text-gray-500">Reviewed</label>
                  <p className="text-sm">{document.is_reviewed ? 'Yes' : 'No'}</p>
                </div>
                {document.reviewed_at && (
                  <div>
                    <label className="text-sm font-medium text-gray-500">Reviewed At</label>
                    <p className="text-sm">{formatDate(document.reviewed_at)}</p>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </div>
      </>
    )
}