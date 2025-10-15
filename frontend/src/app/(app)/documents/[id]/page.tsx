'use client'

import { useState, useEffect, useCallback } from 'react'
import { useParams } from 'next/navigation'
import {
  fetchDocumentFields,
  type Document,
  type DocumentFieldsResponse,
  type ExtractedField,
  type LineItem
} from '@/lib/api/documents'
import { SidebarTrigger } from "@/components/ui/sidebar"
import { Separator } from "@/components/ui/separator"
import { Breadcrumb, BreadcrumbItem, BreadcrumbLink, BreadcrumbList, BreadcrumbPage, BreadcrumbSeparator } from "@/components/ui/breadcrumb"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { Progress } from "@/components/ui/progress"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { FileText, Hash, Target, BarChart3, Receipt } from 'lucide-react'


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

const formatFieldName = (fieldName: string) => {
  return fieldName
    .split('_')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(' ');
};

export default function DocumentDetailPage() {
  const params = useParams()
  const documentId = params.id as string

  const [documentData, setDocumentData] = useState<DocumentFieldsResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Load initial data
  const loadInitialData = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)

      const data = await fetchDocumentFields(documentId)
      setDocumentData(data)

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

  const calculateSummaryStats = (fields: ExtractedField[], lineItems: LineItem[]) => {
    const totalFields = fields.length
    const fieldsWithConfidence = fields.filter(f => f.confidence !== null)
    const avgConfidence = fieldsWithConfidence.length > 0
      ? fieldsWithConfidence.reduce((sum, f) => sum + (f.confidence || 0), 0) / fieldsWithConfidence.length
      : 0
    const lowConfidenceCount = fieldsWithConfidence.filter(f => (f.confidence || 0) < 0.5).length
    const lineItemSubtotal = lineItems.reduce((sum, item) => {
      const total = item.total || (item.quantity && item.unit_price ? item.quantity * item.unit_price : 0)
      return sum + total
    }, 0)

    return { totalFields, avgConfidence, lowConfidenceCount, lineItemSubtotal }
  }

  const renderContent = () => {
    if (!documentData) return null

    const { document_info: document, extracted_fields: fields, line_items } = documentData
    const { totalFields, avgConfidence, lowConfidenceCount, lineItemSubtotal } = calculateSummaryStats(fields, line_items)

    return (
      <>
        {/* Header */}
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
          <div className="flex items-center space-x-3">
            <StatusBadge status={document.status} />
            <Badge variant="outline">{document.document_type}</Badge>
            {document.confidence_score && (
              <Badge variant="secondary">
                {(document.confidence_score * 100).toFixed(1)}% confidence
              </Badge>
            )}
          </div>
        </div>

        {/* Summary Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Total Fields</CardTitle>
              <Hash className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{totalFields}</div>
              <p className="text-xs text-muted-foreground">
                Extracted fields
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Avg Confidence</CardTitle>
              <Target className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{(avgConfidence * 100).toFixed(1)}%</div>
              <p className="text-xs text-muted-foreground">
                Average field confidence
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Low Confidence</CardTitle>
              <BarChart3 className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{lowConfidenceCount}</div>
              <p className="text-xs text-muted-foreground">
                Fields below 50%
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Line Items Total</CardTitle>
              <Receipt className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">${lineItemSubtotal.toFixed(2)}</div>
              <p className="text-xs text-muted-foreground">
                Total value
              </p>
            </CardContent>
          </Card>
        </div>

        {/* Extracted Fields Table */}
        <Card>
          <CardHeader>
            <CardTitle>Extracted Fields</CardTitle>
            <CardDescription>
              Fields extracted from the document with confidence scores
            </CardDescription>
          </CardHeader>
          <CardContent>
            {fields.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                No fields extracted from this document
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Field Name</TableHead>
                    <TableHead>Value</TableHead>
                    <TableHead>Confidence</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {fields.map((field) => {
                    const confidence = field.confidence || 0
                    const isLowConfidence = confidence < 0.5
                    return (
                      <TableRow key={field.id} className={isLowConfidence ? "bg-red-50" : ""}>
                        <TableCell className="font-medium">{formatFieldName(field.field_name)}</TableCell>
                        <TableCell>{field.value?.toString() || '-'}</TableCell>
                        <TableCell>
                          <div className="flex items-center space-x-2">
                            <span className="text-sm font-mono">
                              {(confidence * 100).toFixed(1)}%
                            </span>
                            <Progress value={confidence * 100} className="w-16" />
                          </div>
                        </TableCell>
                      </TableRow>
                    )
                  })}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>

        {/* Line Items Table */}
        <Card>
          <CardHeader>
            <CardTitle>Line Items</CardTitle>
            <CardDescription>
              Itemized breakdown from the document
            </CardDescription>
          </CardHeader>
          <CardContent>
            {line_items.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                No line items found in this document
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Description</TableHead>
                    <TableHead>Quantity</TableHead>
                    <TableHead>Unit Price</TableHead>
                    <TableHead>Total</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {line_items.map((item) => {
                    const computedTotal = item.total || (item.quantity && item.unit_price ? item.quantity * item.unit_price : 0)
                    return (
                      <TableRow key={item.id}>
                        <TableCell className="max-w-xs truncate">{item.description || '-'}</TableCell>
                        <TableCell>{item.quantity || '-'}</TableCell>
                        <TableCell>{item.unit_price ? `$${item.unit_price.toFixed(2)}` : '-'}</TableCell>
                        <TableCell className="font-medium">${computedTotal.toFixed(2)}</TableCell>
                      </TableRow>
                    )
                  })}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      </>
    )
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

  if (error || !documentData) {
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
                <BreadcrumbPage>{documentData?.document_info.filename || 'Document'}</BreadcrumbPage>
              </BreadcrumbItem>
            </BreadcrumbList>
          </Breadcrumb>
        </header>

        <div className="container mx-auto p-6 max-w-6xl space-y-6">
          {renderContent()}
        </div>
      </>
    )
}