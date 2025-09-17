'use client'

import { useState } from 'react'
import { ClientsList } from '@/components/ClientsList'
import { ClientForm } from '@/components/ClientForm'
import { type Client } from '@/lib/api/clients'
import { SidebarTrigger } from "@/components/ui/sidebar"
import { Separator } from "@/components/ui/separator"
import { Breadcrumb, BreadcrumbItem, BreadcrumbLink, BreadcrumbList, BreadcrumbPage, BreadcrumbSeparator } from "@/components/ui/breadcrumb"

export default function ClientsPage() {
  const [formOpen, setFormOpen] = useState(false)
  const [editingClient, setEditingClient] = useState<Client | null>(null)
  const [refreshTrigger, setRefreshTrigger] = useState(0)

  const handleCreateClient = () => {
    setEditingClient(null)
    setFormOpen(true)
  }

  const handleEditClient = (client: Client) => {
    setEditingClient(client)
    setFormOpen(true)
  }

  const handleFormSuccess = () => {
    setRefreshTrigger(prev => prev + 1)
  }

  const handleFormClose = (open: boolean) => {
    setFormOpen(open)
    if (!open) {
      setEditingClient(null)
    }
  }

  return (
    <>
      <header className="flex h-16 shrink-0 items-center gap-2 border-b px-4">
        <SidebarTrigger />
        <Separator orientation="vertical" className="mr-2 h-4" />
        <Breadcrumb>
          <BreadcrumbList>
            <BreadcrumbItem className="hidden md:block">
              <BreadcrumbLink href="#">
                LexExtract
              </BreadcrumbLink>
            </BreadcrumbItem>
            <BreadcrumbSeparator className="hidden md:block" />
            <BreadcrumbItem>
              <BreadcrumbPage>
                Clients
              </BreadcrumbPage>
            </BreadcrumbItem>
          </BreadcrumbList>
        </Breadcrumb>
      </header>
      <div className="container mx-auto p-6 max-w-6xl">
        <ClientsList
          onCreateClient={handleCreateClient}
          onEditClient={handleEditClient}
          refreshTrigger={refreshTrigger}
        />

        <ClientForm
          client={editingClient}
          open={formOpen}
          onOpenChange={handleFormClose}
          onSuccess={handleFormSuccess}
        />
      </div>
    </>
  )
}