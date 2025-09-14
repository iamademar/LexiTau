'use client'

import dynamic from 'next/dynamic'
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"

// Dynamically import Assistant with SSR disabled
const Assistant = dynamic(() => import('@/components/assistant/Assistant').then(mod => ({ default: mod.Assistant })), {
  ssr: false,
  loading: () => (
    <div className="flex items-center justify-center h-[400px]">
      <div className="text-center space-y-2">
        <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin mx-auto"></div>
        <p className="text-sm text-muted-foreground">Loading Assistant...</p>
      </div>
    </div>
  )
})

export default function Home() {
  return (
    <div className="min-h-screen p-8 sm:p-12">
      <div className="max-w-7xl mx-auto">
        <header className="mb-12 text-center">
          <h1 className="text-4xl font-bold mb-4">LexiTau Assistant</h1>
          <p className="text-lg text-muted-foreground">AI-powered document analysis and chat interface</p>
        </header>
        
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* Assistant Card */}
          <div className="bg-card rounded-lg border shadow-sm h-[600px]">
            <Assistant />
          </div>

          {/* Sample Form Card */}
          <div className="bg-card rounded-lg border p-6 shadow-sm">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-2xl font-semibold">Sample Form</h2>
              <div className="text-sm text-muted-foreground">Coming soon</div>
            </div>
            <div className="space-y-4">
              <p className="text-muted-foreground">
                Demonstration of form components with validation and error handling.
              </p>
              <div className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="email">Email</Label>
                  <Input 
                    id="email" 
                    type="email" 
                    placeholder="Enter your email"
                    disabled
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="message">Message</Label>
                  <Input 
                    id="message" 
                    placeholder="Your message here"
                    disabled
                  />
                </div>
                <div className="flex gap-2">
                  <Button variant="default" disabled>Submit</Button>
                  <Button variant="ghost" disabled>Reset</Button>
                </div>
              </div>
              <div className="mt-6 p-4 bg-muted/50 rounded-md">
                <p className="text-sm text-muted-foreground">
                  Form components will be fully functional in the next iteration with validation and error handling.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
