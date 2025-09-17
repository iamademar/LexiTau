'use client'

import { useState } from 'react'
import { type Transaction } from '@/lib/api/statements'
import { 
  Table, 
  TableBody, 
  TableCell, 
  TableHead, 
  TableHeader, 
  TableRow 
} from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Search, ArrowUpDown, Download } from 'lucide-react'

interface TransactionsTableProps {
  transactions: Transaction[]
}

export function TransactionsTable({ transactions }: TransactionsTableProps) {
  const [searchTerm, setSearchTerm] = useState('')
  const [sortConfig, setSortConfig] = useState<{
    key: keyof Transaction
    direction: 'asc' | 'desc'
  } | null>(null)

  // Filter transactions based on search term
  const filteredTransactions = transactions.filter(transaction =>
    transaction.payee.toLowerCase().includes(searchTerm.toLowerCase()) ||
    transaction.type.toLowerCase().includes(searchTerm.toLowerCase()) ||
    transaction.currency.toLowerCase().includes(searchTerm.toLowerCase())
  )

  // Sort transactions
  const sortedTransactions = [...filteredTransactions].sort((a, b) => {
    if (!sortConfig) return 0

    const aValue = a[sortConfig.key]
    const bValue = b[sortConfig.key]

    if (aValue === null || aValue === undefined) return 1
    if (bValue === null || bValue === undefined) return -1

    if (aValue < bValue) {
      return sortConfig.direction === 'asc' ? -1 : 1
    }
    if (aValue > bValue) {
      return sortConfig.direction === 'asc' ? 1 : -1
    }
    return 0
  })

  const handleSort = (key: keyof Transaction) => {
    setSortConfig(current => ({
      key,
      direction: current?.key === key && current?.direction === 'asc' ? 'desc' : 'asc'
    }))
  }

  const formatCurrency = (amount: number, currency: string = 'GBP') => {
    return new Intl.NumberFormat('en-GB', {
      style: 'currency',
      currency: currency,
      minimumFractionDigits: 2
    }).format(amount)
  }

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-GB', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric'
    })
  }

  const getTransactionTypeVariant = (type: string) => {
    const normalizedType = type.toLowerCase()
    if (normalizedType.includes('credit') || normalizedType.includes('deposit') || normalizedType.includes('in')) {
      return 'success'
    }
    if (normalizedType.includes('debit') || normalizedType.includes('withdrawal') || normalizedType.includes('out')) {
      return 'destructive'
    }
    return 'secondary'
  }

  const exportToCSV = () => {
    const headers = ['Date', 'Payee', 'Amount', 'Type', 'Balance', 'Currency']
    const csvContent = [
      headers.join(','),
      ...sortedTransactions.map(t => [
        formatDate(t.date),
        `"${t.payee.replace(/"/g, '""')}"`, // Escape quotes in payee
        t.amount,
        `"${t.type.replace(/"/g, '""')}"`,
        t.balance || '',
        t.currency
      ].join(','))
    ].join('\n')

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
    const link = document.createElement('a')
    const url = URL.createObjectURL(blob)
    link.setAttribute('href', url)
    link.setAttribute('download', `transactions-${new Date().toISOString().split('T')[0]}.csv`)
    link.style.visibility = 'hidden'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  }

  if (transactions.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500">
        <p>No transactions found in this statement.</p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Search and Export Controls */}
      <div className="flex justify-between items-center">
        <div className="relative w-64">
          <Search className="absolute left-2 top-2.5 h-4 w-4 text-gray-400" />
          <Input
            placeholder="Search transactions..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="pl-8"
          />
        </div>
        <Button onClick={exportToCSV} variant="outline" size="sm">
          <Download className="mr-2 h-4 w-4" />
          Export CSV
        </Button>
      </div>

      {/* Results Summary */}
      <div className="text-sm text-gray-600">
        Showing {sortedTransactions.length} of {transactions.length} transactions
        {searchTerm && ` matching "${searchTerm}"`}
      </div>

      {/* Transactions Table */}
      <div className="border rounded-lg overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>
                <Button variant="ghost" onClick={() => handleSort('date')} className="h-auto p-0 font-semibold">
                  Date
                  <ArrowUpDown className="ml-2 h-4 w-4" />
                </Button>
              </TableHead>
              <TableHead>
                <Button variant="ghost" onClick={() => handleSort('payee')} className="h-auto p-0 font-semibold">
                  Payee
                  <ArrowUpDown className="ml-2 h-4 w-4" />
                </Button>
              </TableHead>
              <TableHead className="text-right">
                <Button variant="ghost" onClick={() => handleSort('amount')} className="h-auto p-0 font-semibold">
                  Amount
                  <ArrowUpDown className="ml-2 h-4 w-4" />
                </Button>
              </TableHead>
              <TableHead>
                <Button variant="ghost" onClick={() => handleSort('type')} className="h-auto p-0 font-semibold">
                  Type
                  <ArrowUpDown className="ml-2 h-4 w-4" />
                </Button>
              </TableHead>
              <TableHead className="text-right">
                <Button variant="ghost" onClick={() => handleSort('balance')} className="h-auto p-0 font-semibold">
                  Balance
                  <ArrowUpDown className="ml-2 h-4 w-4" />
                </Button>
              </TableHead>
              <TableHead>Currency</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {sortedTransactions.map((transaction) => (
              <TableRow key={transaction.id}>
                <TableCell className="font-medium">
                  {formatDate(transaction.date)}
                </TableCell>
                <TableCell className="max-w-xs">
                  <div className="truncate" title={transaction.payee}>
                    {transaction.payee}
                  </div>
                </TableCell>
                <TableCell className="text-right font-mono">
                  <span className={transaction.amount >= 0 ? 'text-green-600' : 'text-red-600'}>
                    {formatCurrency(transaction.amount, transaction.currency)}
                  </span>
                </TableCell>
                <TableCell>
                  <Badge variant={getTransactionTypeVariant(transaction.type)}>
                    {transaction.type}
                  </Badge>
                </TableCell>
                <TableCell className="text-right font-mono">
                  {transaction.balance !== null && transaction.balance !== undefined
                    ? formatCurrency(transaction.balance, transaction.currency)
                    : '-'
                  }
                </TableCell>
                <TableCell>
                  <Badge variant="outline">{transaction.currency}</Badge>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {/* Summary Statistics */}
      {sortedTransactions.length > 0 && (
        <div className="bg-gray-50 p-4 rounded-lg">
          <h4 className="font-semibold text-sm text-gray-700 mb-2">Summary</h4>
          <div className="grid grid-cols-3 gap-4 text-sm">
            <div>
              <span className="text-gray-600">Total Credits:</span>
              <div className="font-mono text-green-600">
                {formatCurrency(
                  sortedTransactions
                    .filter(t => t.amount > 0)
                    .reduce((sum, t) => sum + t.amount, 0),
                  sortedTransactions[0]?.currency || 'GBP'
                )}
              </div>
            </div>
            <div>
              <span className="text-gray-600">Total Debits:</span>
              <div className="font-mono text-red-600">
                {formatCurrency(
                  sortedTransactions
                    .filter(t => t.amount < 0)
                    .reduce((sum, t) => sum + Math.abs(t.amount), 0),
                  sortedTransactions[0]?.currency || 'GBP'
                )}
              </div>
            </div>
            <div>
              <span className="text-gray-600">Net Amount:</span>
              <div className="font-mono">
                {formatCurrency(
                  sortedTransactions.reduce((sum, t) => sum + t.amount, 0),
                  sortedTransactions[0]?.currency || 'GBP'
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}