import { Suspense } from 'react'
import { Outlet } from 'react-router'
import { Header } from '@/components/layout/Header'
import { Footer } from '@/components/layout/Footer'
import { CartDrawer } from '@/components/cart/CartDrawer'
import { PageLoader } from '@/components/feedback/PageLoader'

export function RootLayout() {
  return (
    <div className="flex min-h-dvh flex-col bg-bg text-text">
      <Header />
      <main id="main-content" className="flex-1">
        <Suspense fallback={<PageLoader />}>
          <Outlet />
        </Suspense>
      </main>
      <Footer />
      <CartDrawer />
    </div>
  )
}
