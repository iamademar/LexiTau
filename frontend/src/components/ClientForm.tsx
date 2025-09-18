'use client'

import { useState, useEffect } from 'react'
import { createClient, type Client, type ClientCreate } from '@/lib/api/clients'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'

interface ClientFormProps {
  client?: Client | null
  open: boolean
  onOpenChange: (open: boolean) => void
  onSuccess?: () => void
}

export function ClientForm({ client, open, onOpenChange, onSuccess }: ClientFormProps) {
  const [formData, setFormData] = useState({
    name: '',
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const isEdit = !!client

  useEffect(() => {
    if (client) {
      setFormData({
        name: client.name,
      })
    } else {
      setFormData({
        name: '',
      })
    }
    setError(null)
  }, [client, open])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    if (!formData.name.trim()) {
      setError('Name is required')
      return
    }

    if (isEdit) {
      setError('Editing clients is not supported yet.')
      return
    }

    try {
      setLoading(true)
      setError(null)

      const payload: ClientCreate = { name: formData.name.trim() }

      await createClient(payload)

      onOpenChange(false)
      onSuccess?.()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save client')
    } finally {
      setLoading(false)
    }
  }

  const handleInputChange = (field: keyof typeof formData) => (
    e: React.ChangeEvent<HTMLInputElement>
  ) => {
    setFormData(prev => ({
      ...prev,
      [field]: e.target.value
    }))
    if (error) setError(null)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle>
            {isEdit ? 'Edit Client' : 'Create New Client'}
          </DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <div className="text-red-600 text-sm p-3 border border-red-200 rounded-md bg-red-50">
              {error}
            </div>
          )}

          <div className="space-y-2">
            <Label htmlFor="name">Name *</Label>
            <Input
              id="name"
              value={formData.name}
              onChange={handleInputChange('name')}
              placeholder="Enter client name"
              required
            />
          </div>


          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={loading}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={loading}>
              {loading ? 'Saving...' : isEdit ? 'Update' : 'Create'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}