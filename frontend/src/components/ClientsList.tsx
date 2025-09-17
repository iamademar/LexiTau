'use client'

import { useState, useEffect } from 'react'
import { fetchClients, deleteClient, type Client } from '@/lib/api/clients'
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
import { Trash2, Edit, Plus } from 'lucide-react'

interface ClientsListProps {
  onEditClient?: (client: Client) => void
  onCreateClient?: () => void
  refreshTrigger?: number
}

export function ClientsList({ onEditClient, onCreateClient, refreshTrigger }: ClientsListProps) {
  const [clients, setClients] = useState<Client[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [deletingId, setDeletingId] = useState<number | null>(null)

  const loadClients = async () => {
    try {
      setLoading(true)
      setError(null)
      const data = await fetchClients()
      setClients(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load clients')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadClients()
  }, [refreshTrigger])

  const handleDelete = async (id: number, name: string) => {
    if (!window.confirm(`Are you sure you want to delete client "${name}"?`)) {
      return
    }

    try {
      setDeletingId(id)
      await deleteClient(id)
      await loadClients()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete client')
    } finally {
      setDeletingId(null)
    }
  }

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="flex justify-between items-center">
          <Skeleton className="h-8 w-32" />
          <Skeleton className="h-10 w-32" />
        </div>
        <div className="space-y-2">
          {[...Array(5)].map((_, i) => (
            <Skeleton key={i} className="h-12 w-full" />
          ))}
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="space-y-4">
        <div className="flex justify-between items-center">
          <h2 className="text-2xl font-bold">Clients</h2>
          {onCreateClient && (
            <Button onClick={onCreateClient}>
              <Plus className="w-4 h-4 mr-2" />
              Add Client
            </Button>
          )}
        </div>
        <div className="text-red-600 p-4 border border-red-200 rounded-md bg-red-50">
          Error: {error}
          <Button 
            variant="outline" 
            size="sm" 
            onClick={loadClients}
            className="ml-4"
          >
            Retry
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h2 className="text-2xl font-bold">Clients</h2>
        {onCreateClient && (
          <Button onClick={onCreateClient}>
            <Plus className="w-4 h-4 mr-2" />
            Add Client
          </Button>
        )}
      </div>

      {clients.length === 0 ? (
        <div className="text-center py-8 text-gray-500">
          <p>No clients found.</p>
          {onCreateClient && (
            <Button onClick={onCreateClient} className="mt-4">
              Create your first client
            </Button>
          )}
        </div>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Contact Name</TableHead>
              <TableHead>Contact Email</TableHead>
              <TableHead>Created</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {clients.map((client) => (
              <TableRow key={client.id}>
                <TableCell className="font-medium">{client.name}</TableCell>
                <TableCell>{client.contact_name || '-'}</TableCell>
                <TableCell>{client.contact_email || '-'}</TableCell>
                <TableCell>
                  {new Date(client.created_at).toLocaleDateString()}
                </TableCell>
                <TableCell className="text-right">
                  <div className="flex justify-end gap-2">
                    {onEditClient && (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => onEditClient(client)}
                      >
                        <Edit className="w-4 h-4" />
                      </Button>
                    )}
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleDelete(client.id, client.name)}
                      disabled={deletingId === client.id}
                    >
                      <Trash2 className="w-4 h-4" />
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  )
}