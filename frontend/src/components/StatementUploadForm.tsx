'use client'

import { useState, useEffect } from 'react'
import { uploadStatement } from '@/lib/api/statements'
import { fetchClients, type Client } from '@/lib/api/clients'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Upload, AlertCircle } from 'lucide-react'
import { useRouter } from 'next/navigation'

interface StatementUploadFormProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onSuccess?: () => void
}

export function StatementUploadForm({ open, onOpenChange, onSuccess }: StatementUploadFormProps) {
  const [clients, setClients] = useState<Client[]>([])
  const [selectedClientId, setSelectedClientId] = useState<string>('')
  const [file, setFile] = useState<File | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [loadingClients, setLoadingClients] = useState(false)
  const router = useRouter()

  // Load clients when dialog opens
  useEffect(() => {
    if (open) {
      loadClients()
    }
  }, [open])

  const loadClients = async () => {
    try {
      setLoadingClients(true)
      const data = await fetchClients()
      setClients(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load clients')
    } finally {
      setLoadingClients(false)
    }
  }

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0]
    setError(null)
    
    if (!selectedFile) {
      setFile(null)
      return
    }

    // Validate file type
    if (selectedFile.type !== 'application/pdf') {
      setError('Only PDF files are allowed')
      setFile(null)
      return
    }

    // Validate file size (10MB limit)
    const maxSize = 10 * 1024 * 1024 // 10MB in bytes
    if (selectedFile.size > maxSize) {
      setError('File size must be 10MB or less')
      setFile(null)
      return
    }

    setFile(selectedFile)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    
    if (!selectedClientId) {
      setError('Please select a client')
      return
    }

    if (!file) {
      setError('Please select a PDF file')
      return
    }

    try {
      setLoading(true)
      setError(null)
      
      const statement = await uploadStatement(parseInt(selectedClientId), file)
      
      // Reset form
      setSelectedClientId('')
      setFile(null)
      onOpenChange(false)
      
      // Notify parent of success
      onSuccess?.()
      
      // Navigate to the statement detail page
      router.push(`/statements/${statement.id}`)
      
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to upload statement')
    } finally {
      setLoading(false)
    }
  }

  const handleClose = (open: boolean) => {
    if (!loading) {
      setSelectedClientId('')
      setFile(null)
      setError(null)
      onOpenChange(open)
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle>Upload Statement</DialogTitle>
          <DialogDescription>
            Upload a PDF bank statement for processing and transaction extraction.
          </DialogDescription>
        </DialogHeader>
        
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="client">Client</Label>
            <Select 
              value={selectedClientId} 
              onValueChange={setSelectedClientId}
              disabled={loadingClients || loading}
            >
              <SelectTrigger>
                <SelectValue placeholder={loadingClients ? "Loading clients..." : "Select a client"} />
              </SelectTrigger>
              <SelectContent>
                {clients.map((client) => (
                  <SelectItem key={client.id} value={client.id.toString()}>
                    {client.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="file">PDF Statement</Label>
            <Input
              id="file"
              type="file"
              accept=".pdf"
              onChange={handleFileChange}
              disabled={loading}
              className="cursor-pointer"
            />
            <p className="text-sm text-gray-500">
              Maximum file size: 10MB
            </p>
          </div>

          {error && (
            <div className="flex items-center space-x-2 text-red-600 text-sm">
              <AlertCircle className="h-4 w-4" />
              <span>{error}</span>
            </div>
          )}

          <div className="flex justify-end space-x-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => handleClose(false)}
              disabled={loading}
            >
              Cancel
            </Button>
            <Button 
              type="submit" 
              disabled={loading || !selectedClientId || !file}
            >
              {loading ? (
                'Uploading...'
              ) : (
                <>
                  <Upload className="mr-2 h-4 w-4" />
                  Upload
                </>
              )}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}