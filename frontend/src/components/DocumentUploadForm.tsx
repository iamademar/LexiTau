'use client'

import { useState } from 'react'
import { uploadDocuments } from '@/lib/api/documents'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Upload, AlertCircle } from 'lucide-react'
import { useRouter } from 'next/navigation'

interface DocumentUploadFormProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onSuccess?: () => void
}

export function DocumentUploadForm({ open, onOpenChange, onSuccess }: DocumentUploadFormProps) {
  const [files, setFiles] = useState<File[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const router = useRouter()

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFiles = Array.from(e.target.files || [])
    setError(null)

    if (selectedFiles.length === 0) {
      setFiles([])
      return
    }

    // Validate file types
    const validTypes = ['application/pdf', 'image/jpeg', 'image/png']
    const invalidFiles = selectedFiles.filter(file => !validTypes.includes(file.type))

    if (invalidFiles.length > 0) {
      setError('Only PDF, JPG, and PNG files are allowed')
      setFiles([])
      return
    }

    // Validate file size (10MB limit per file)
    const maxSize = 10 * 1024 * 1024 // 10MB in bytes
    const oversizedFiles = selectedFiles.filter(file => file.size > maxSize)

    if (oversizedFiles.length > 0) {
      setError('Each file must be 10MB or less')
      setFiles([])
      return
    }

    setFiles(selectedFiles)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    if (files.length === 0) {
      setError('Please select at least one file')
      return
    }

    try {
      setLoading(true)
      setError(null)

      const response = await uploadDocuments(files)

      // Reset form
      setFiles([])
      onOpenChange(false)

      // Notify parent of success
      onSuccess?.()

      // If single file and successful, navigate to the document detail page
      if (files.length === 1 && response.successful_uploads === 1 && response.results[0]?.document_id) {
        router.push(`/documents/${response.results[0].document_id}`)
      }

    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to upload documents')
    } finally {
      setLoading(false)
    }
  }

  const handleClose = (open: boolean) => {
    if (!loading) {
      setFiles([])
      setError(null)
      onOpenChange(open)
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle>Upload Documents</DialogTitle>
          <DialogDescription>
            Upload PDF, JPG, or PNG documents for processing and data extraction.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="files">Documents</Label>
            <Input
              id="files"
              type="file"
              accept=".pdf,.jpg,.jpeg,.png"
              multiple
              onChange={handleFileChange}
              disabled={loading}
              className="cursor-pointer"
            />
            <p className="text-sm text-gray-500">
              Select one or more files. Maximum file size: 10MB each
            </p>
            {files.length > 0 && (
              <div className="text-sm text-gray-600">
                {files.length} file{files.length !== 1 ? 's' : ''} selected
              </div>
            )}
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
              disabled={loading || files.length === 0}
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