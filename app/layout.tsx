import './globals.css'
import type { Metadata } from 'next'
import { Inter } from 'next/font/google'

const inter = Inter({ subsets: ['latin'] })

export const metadata: Metadata = {
  title: 'LuxeLink Dashboard',
  description: 'High-end vehicle search agent dashboard',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body className={inter.className}>
        <nav className="border-b border-luxe-gold/20 bg-luxe-black/50 backdrop-blur-md sticky top-0 z-50">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex justify-between h-16 items-center">
              <div className="flex items-center">
                <span className="text-2xl font-bold bg-gradient-to-r from-luxe-gold to-yellow-200 bg-clip-text text-transparent">
                  LuxeLink
                </span>
              </div>
              <div className="hidden md:block">
                <div className="ml-10 flex items-baseline space-x-4">
                  <a href="#" className="text-luxe-gold px-3 py-2 rounded-md text-sm font-medium">Dashboard</a>
                  <a href="#" className="text-gray-300 hover:text-luxe-gold px-3 py-2 rounded-md text-sm font-medium transition-colors">Agents</a>
                  <a href="#" className="text-gray-300 hover:text-luxe-gold px-3 py-2 rounded-md text-sm font-medium transition-colors">Settings</a>
                </div>
              </div>
            </div>
          </div>
        </nav>
        <main>{children}</main>
      </body>
    </html>
  )
}
