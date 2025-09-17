'use client'

import { useState, useEffect } from 'react'
import { fetchStatements, type Statement } from '@/lib/api/statements'
import { fetchClients, type Client } from '@/lib/api/clients'
import { Button } from '@/components/ui/button'
import { 
  Table, 
  TableBody, 
  TableCell, 
  TableHead, 
  TableHeader, 
  TableRow 
} from '@/components/ui/table'
import { Skeleton } from '@/components/ui/skeleton'
import { Badge } from '@/components/ui/badge'
import { FileText, Plus, Eye } from 'lucide-react'
import Link from 'next/link'

interface StatementsListProps {
  onUploadStatement?: () => void
  refreshTrigger?: number
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

export function StatementsList({ onUploadStatement, refreshTrigger }: StatementsListProps) {
  const [statements, setStatements] = useState<Statement[]>([])
  const [clients, setClients] = useState<Client[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const loadData = async () => {
    try {
      setLoading(true)
      setError(null)
      const [statementsData, clientsData] = await Promise.all([
        fetchStatements(),
        fetchClients()
      ])
      setStatements(statementsData)
      setClients(clientsData)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load statements')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadData()
  }, [refreshTrigger])

  const getClientName = (clientId: number) => {
    const client = clients.find(c => c.id === clientId)
    return client?.name || `Client ${clientId}`
  }

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString()
  }

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="flex justify-between items-center">
          <h1 className="text-3xl font-bold">Statements</h1>
          <Button disabled>
            <Plus className="mr-2 h-4 w-4" />
            Upload Statement
          </Button>
        </div>
        <div className="border rounded-lg">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>ID</TableHead>
                <TableHead>Client</TableHead>
                <TableHead>Upload Date</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Progress</TableHead>
                <TableHead>Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {[...Array(5)].map((_, i) => (
                <TableRow key={i}>
                  <TableCell><Skeleton className="h-4 w-8" /></TableCell>
                  <TableCell><Skeleton className="h-4 w-24" /></TableCell>
                  <TableCell><Skeleton className="h-4 w-20" /></TableCell>
                  <TableCell><Skeleton className="h-4 w-16" /></TableCell>
                  <TableCell><Skeleton className="h-4 w-12" /></TableCell>
                  <TableCell><Skeleton className="h-4 w-16" /></TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="space-y-4">
        <div className="flex justify-between items-center">
          <h1 className="text-3xl font-bold">Statements</h1>
          <Button onClick={onUploadStatement}>
            <Plus className="mr-2 h-4 w-4" />
            Upload Statement
          </Button>
        </div>
        <div className="text-center py-8 text-red-600">
          <p>Error: {error}</p>
          <Button onClick={loadData} className="mt-4">
            Try Again
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h1 className="text-3xl font-bold">Statements</h1>
        <Button onClick={onUploadStatement}>
          <Plus className="mr-2 h-4 w-4" />
          Upload Statement
        </Button>
      </div>

      {statements.length === 0 ? (
        <div className="text-center py-12 border rounded-lg">
          <FileText className="mx-auto h-12 w-12 text-gray-400 mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">No statements yet</h3>
          <p className="text-gray-500 mb-6">Upload your first PDF statement to get started.</p>
          <Button onClick={onUploadStatement}>
            <Plus className="mr-2 h-4 w-4" />
            Upload Statement
          </Button>
        </div>
      ) : (
        <div className="border rounded-lg">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>ID</TableHead>
                <TableHead>Client</TableHead>
                <TableHead>Upload Date</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Progress</TableHead>
                <TableHead>Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {statements.map((statement) => (
                <TableRow key={statement.id}>
                  <TableCell className="font-medium">#{statement.id}</TableCell>
                  <TableCell>{getClientName(statement.client_id)}</TableCell>
                  <TableCell>{formatDate(statement.uploaded_at)}</TableCell>
                  <TableCell>
                    <StatusBadge status={statement.status} />
                  </TableCell>
                  <TableCell>{statement.progress}%</TableCell>
                  <TableCell>
                    <Button asChild variant="outline" size="sm">
                      <Link href={`/statements/${statement.id}`}>
                        <Eye className="mr-2 h-4 w-4" />
                        View
                      </Link>
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  )
}