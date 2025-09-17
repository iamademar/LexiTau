'use client'

import { useState, useEffect, useCallback } from 'react'
import { useParams } from 'next/navigation'
import { 
  fetchStatement, 
  fetchStatementProgress, 
  fetchStatementTransactions,
  type Statement, 
  type StatementProgress, 
  type Transaction 
} from '@/lib/api/statements'
import { fetchClients, type Client } from '@/lib/api/clients'
import { SidebarInset, SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar"
import { NavSidebar } from "@/components/nav-sidebar"
import { Separator } from "@/components/ui/separator"
import { Breadcrumb, BreadcrumbItem, BreadcrumbLink, BreadcrumbList, BreadcrumbPage, BreadcrumbSeparator } from "@/components/ui/breadcrumb"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import { Skeleton } from "@/components/ui/skeleton"
import { FileText, Clock, CheckCircle, XCircle, AlertCircle } from 'lucide-react'
import { TransactionsTable } from '@/components/TransactionsTable'

const StatusIcon = ({ status }: { status: Statement['status'] }) => {
  switch (status) {
    case 'pending':
      return <Clock className="h-5 w-5 text-gray-500" />
    case 'processing':
      return <AlertCircle className="h-5 w-5 text-blue-500" />
    case 'completed':
      return <CheckCircle className="h-5 w-5 text-green-500" />
    case 'failed':
      return <XCircle className="h-5 w-5 text-red-500" />
    default:
      return <Clock className="h-5 w-5 text-gray-500" />
  }
}

const StatusBadge = ({ status }: { status: Statement['status'] }) => {
  const variants = {
    pending: 'secondary',
    processing: 'default',
    completed: 'success',
    failed: 'destructive'
  } as const

  return (
    <Badge variant={variants[status] || 'secondary'}>
      {status}
    </Badge>
  )
}

export default function StatementDetailPage() {
  const params = useParams()
  const statementId = parseInt(params.id as string)
  
  const [statement, setStatement] = useState<Statement | null>(null)
  const [client, setClient] = useState<Client | null>(null)
  const [progress, setProgress] = useState<StatementProgress | null>(null)
  const [transactions, setTransactions] = useState<Transaction[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [pollingActive, setPollingActive] = useState(false)

  // Load initial data
  const loadInitialData = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)
      
      const [statementData, clientsData] = await Promise.all([
        fetchStatement(statementId),
        fetchClients()
      ])
      
      setStatement(statementData)
      
      // Find the client for this statement
      const matchingClient = clientsData.find(c => c.id === statementData.client_id)
      setClient(matchingClient || null)
      
      // Set initial progress
      setProgress({
        progress: statementData.progress,
        status: statementData.status
      })
      
      // If completed, load transactions immediately
      if (statementData.status === 'completed') {
        const transactionsData = await fetchStatementTransactions(statementId)
        setTransactions(transactionsData)
      }
      
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load statement')
    } finally {
      setLoading(false)
    }
  }, [statementId])

  // Poll for progress updates
  const pollProgress = useCallback(async () => {
    try {
      const progressData = await fetchStatementProgress(statementId)
      setProgress(progressData)
      
      // If completed, load transactions and stop polling
      if (progressData.status === 'completed') {
        setPollingActive(false)
        const transactionsData = await fetchStatementTransactions(statementId)
        setTransactions(transactionsData)
      }
      
      // If failed, stop polling
      if (progressData.status === 'failed') {
        setPollingActive(false)
      }
      
    } catch (err) {
      console.error('Failed to poll progress:', err)
      // Don't set error state for polling failures, just stop polling
      setPollingActive(false)
    }
  }, [statementId])

  // Set up polling effect
  useEffect(() => {
    let interval: NodeJS.Timeout | null = null
    
    if (pollingActive) {
      interval = setInterval(pollProgress, 1000) // Poll every second
    }
    
    return () => {
      if (interval) {
        clearInterval(interval)
      }
    }
  }, [pollingActive, pollProgress])

  // Start polling if statement is pending or processing
  useEffect(() => {
    if (progress && (progress.status === 'pending' || progress.status === 'processing')) {
      setPollingActive(true)
    } else {
      setPollingActive(false)
    }
  }, [progress])

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
      <SidebarProvider>
        <NavSidebar />
        <SidebarInset>
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
                  <BreadcrumbLink href="/statements">Statements</BreadcrumbLink>
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
        </SidebarInset>
      </SidebarProvider>
    )
  }

  if (error || !statement) {
    return (
      <SidebarProvider>
        <NavSidebar />
        <SidebarInset>
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
                  <BreadcrumbLink href="/statements">Statements</BreadcrumbLink>
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
              <p>Error: {error || 'Statement not found'}</p>
            </div>
          </div>
        </SidebarInset>
      </SidebarProvider>
    )
  }

  return (
    <SidebarProvider>
      <NavSidebar />
      <SidebarInset>
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
                <BreadcrumbLink href="/statements">Statements</BreadcrumbLink>
              </BreadcrumbItem>
              <BreadcrumbSeparator className="hidden md:block" />
              <BreadcrumbItem>
                <BreadcrumbPage>Statement #{statement.id}</BreadcrumbPage>
              </BreadcrumbItem>
            </BreadcrumbList>
          </Breadcrumb>
        </header>
        
        <div className="container mx-auto p-6 max-w-6xl space-y-6">
          {/* Statement Header */}
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <FileText className="h-8 w-8 text-blue-500" />
              <div>
                <h1 className="text-3xl font-bold">Statement #{statement.id}</h1>
                <p className="text-gray-600">
                  {client?.name || `Client ${statement.client_id}`} • Uploaded {formatDate(statement.uploaded_at)}
                </p>
              </div>
            </div>
          </div>

          {/* Progress Card */}
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  <StatusIcon status={progress?.status || statement.status} />
                  <CardTitle>Processing Status</CardTitle>
                </div>
                <StatusBadge status={progress?.status || statement.status} />
              </div>
              <CardDescription>
                {progress?.status === 'pending' && 'Statement is queued for processing'}
                {progress?.status === 'processing' && 'Extracting transactions from statement...'}
                {progress?.status === 'completed' && 'Statement processing completed successfully'}
                {progress?.status === 'failed' && 'Statement processing failed'}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span>Progress</span>
                  <span>{progress?.progress || statement.progress}%</span>
                </div>
                <Progress value={progress?.progress || statement.progress} className="w-full" />
              </div>
              
              {pollingActive && (
                <p className="text-sm text-blue-600 mt-2">
                  Updating in real-time...
                </p>
              )}
            </CardContent>
          </Card>

          {/* Transactions Section */}
          {(progress?.status === 'completed' || statement.status === 'completed') && (
            <Card>
              <CardHeader>
                <CardTitle>Extracted Transactions</CardTitle>
                <CardDescription>
                  {transactions.length} transaction{transactions.length !== 1 ? 's' : ''} found
                </CardDescription>
              </CardHeader>
              <CardContent>
                <TransactionsTable transactions={transactions} />
              </CardContent>
            </Card>
          )}
        </div>
      </SidebarInset>
    </SidebarProvider>
  )
}