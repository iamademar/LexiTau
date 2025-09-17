'use client'

import { useState, useEffect } from 'react'
import { createClient, updateClient, type Client, type ClientCreate, type ClientUpdate } from '@/lib/api/clients'
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
    contact_name: '',
    contact_email: '',
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const isEdit = !!client

  useEffect(() => {
    if (client) {
      setFormData({
        name: client.name,
        contact_name: client.contact_name || '',
        contact_email: client.contact_email || '',
      })
    } else {
      setFormData({
        name: '',
        contact_name: '',
        contact_email: '',
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

    try {
      setLoading(true)
      setError(null)

      const payload = {
        name: formData.name.trim(),
        contact_name: formData.contact_name.trim() || null,
        contact_email: formData.contact_email.trim() || null,
      }

      if (isEdit && client) {
        await updateClient(client.id, payload as ClientUpdate)
      } else {
        await createClient(payload as ClientCreate)
      }

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

          <div className="space-y-2">
            <Label htmlFor="contact_name">Contact Name</Label>
            <Input
              id="contact_name"
              value={formData.contact_name}
              onChange={handleInputChange('contact_name')}
              placeholder="Enter contact name"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="contact_email">Contact Email</Label>
            <Input
              id="contact_email"
              type="email"
              value={formData.contact_email}
              onChange={handleInputChange('contact_email')}
              placeholder="Enter contact email"
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