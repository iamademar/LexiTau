'use client'

import { useState } from 'react'
import { DocumentsList } from '@/components/DocumentsList'
import { DocumentUploadForm } from '@/components/DocumentUploadForm'
import { SidebarTrigger } from "@/components/ui/sidebar"
import { Separator } from "@/components/ui/separator"
import { Breadcrumb, BreadcrumbItem, BreadcrumbLink, BreadcrumbList, BreadcrumbPage, BreadcrumbSeparator } from "@/components/ui/breadcrumb"

export default function DocumentsPage() {
  const [uploadFormOpen, setUploadFormOpen] = useState(false)
  const [refreshTrigger, setRefreshTrigger] = useState(0)

  const handleUploadDocument = () => {
    setUploadFormOpen(true)
  }

  const handleUploadSuccess = () => {
    setRefreshTrigger(prev => prev + 1)
  }

  const handleUploadFormClose = (open: boolean) => {
    setUploadFormOpen(open)
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
                Documents
              </BreadcrumbPage>
            </BreadcrumbItem>
          </BreadcrumbList>
        </Breadcrumb>
      </header>
      <div className="container mx-auto p-6 max-w-6xl">
        <DocumentsList
          onUploadDocument={handleUploadDocument}
          refreshTrigger={refreshTrigger}
        />

        <DocumentUploadForm
          open={uploadFormOpen}
          onOpenChange={handleUploadFormClose}
          onSuccess={handleUploadSuccess}
        />
      </div>
    </>
  )
}