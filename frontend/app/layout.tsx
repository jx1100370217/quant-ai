import type { Metadata, Viewport } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'

const inter = Inter({ 
  subsets: ['latin'],
  display: 'swap',
  variable: '--font-inter',
})

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  themeColor: '#0a0e17',
}

export const metadata: Metadata = {
  title: 'QuantAI - 量化交易AI系统',
  description: '基于AI多Agent的智能量化交易系统',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="zh-CN" className={`${inter.variable} dark`}>
      <head />
      <body className={`${inter.className} antialiased`}>
        {/* Loading indicator */}
        <div id="loading-indicator" className="fixed top-0 left-0 w-full h-1 bg-gradient-to-r from-cyan-500 to-blue-500 z-50 opacity-0 transition-opacity duration-300"></div>
        
        {/* Main app container */}
        <div className="min-h-screen bg-dark-900 text-white">
          {/* Background effects */}
          <div className="fixed inset-0 pointer-events-none">
            {/* Animated background gradients */}
            <div className="absolute top-0 left-1/4 w-96 h-96 bg-neon-blue/5 rounded-full blur-3xl animate-float"></div>
            <div className="absolute bottom-0 right-1/4 w-96 h-96 bg-neon-green/5 rounded-full blur-3xl animate-float" style={{ animationDelay: '1s' }}></div>
            
            {/* Grid pattern overlay */}
            <div 
              className="absolute inset-0 opacity-20"
              style={{
                backgroundImage: `
                  linear-gradient(rgba(6, 182, 212, 0.1) 1px, transparent 1px),
                  linear-gradient(90deg, rgba(6, 182, 212, 0.1) 1px, transparent 1px)
                `,
                backgroundSize: '50px 50px'
              }}
            ></div>
          </div>
          
          {/* Page content */}
          <main className="relative z-10">
            {children}
          </main>
        </div>
        
        
      </body>
    </html>
  )
}