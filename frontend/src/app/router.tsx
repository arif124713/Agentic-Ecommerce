import { lazy } from 'react'
import { createBrowserRouter } from 'react-router'
import { RootLayout } from '@/layouts/RootLayout'
import { AdminLayout } from '@/layouts/AdminLayout'
import { ProtectedRoute } from '@/components/auth/ProtectedRoute'

// Every page is its own chunk, loaded only when its route is actually visited — the whole
// point of this file's rewrite (see done.MD): before this, all ~37 pages (admin, checkout,
// every auth screen, ...) shipped in one 659 KB bundle regardless of which route a visitor
// landed on. RootLayout/AdminLayout wrap their <Outlet /> in a single <Suspense>, so pages
// don't each need their own boundary here.
const HomePage = lazy(() => import('@/pages/home/HomePage').then((m) => ({ default: m.HomePage })))
const CatalogPage = lazy(() => import('@/pages/catalog/CatalogPage').then((m) => ({ default: m.CatalogPage })))
const ProductPage = lazy(() => import('@/pages/product/ProductPage').then((m) => ({ default: m.ProductPage })))
const CmsPage = lazy(() => import('@/pages/cms/CmsPage').then((m) => ({ default: m.CmsPage })))
const LoginPage = lazy(() => import('@/pages/auth/LoginPage').then((m) => ({ default: m.LoginPage })))
const RegisterPage = lazy(() => import('@/pages/auth/RegisterPage').then((m) => ({ default: m.RegisterPage })))
const ForgotPasswordPage = lazy(() =>
  import('@/pages/auth/ForgotPasswordPage').then((m) => ({ default: m.ForgotPasswordPage })),
)
const ResetPasswordPage = lazy(() =>
  import('@/pages/auth/ResetPasswordPage').then((m) => ({ default: m.ResetPasswordPage })),
)
const VerifyEmailPage = lazy(() =>
  import('@/pages/auth/VerifyEmailPage').then((m) => ({ default: m.VerifyEmailPage })),
)
const AccountPage = lazy(() => import('@/pages/account/AccountPage').then((m) => ({ default: m.AccountPage })))
const WishlistPage = lazy(() => import('@/pages/account/WishlistPage').then((m) => ({ default: m.WishlistPage })))
const SupportPage = lazy(() => import('@/pages/account/SupportPage').then((m) => ({ default: m.SupportPage })))
const TicketDetailPage = lazy(() =>
  import('@/pages/account/TicketDetailPage').then((m) => ({ default: m.TicketDetailPage })),
)
const CartPage = lazy(() => import('@/pages/cart/CartPage').then((m) => ({ default: m.CartPage })))
const CheckoutPage = lazy(() => import('@/pages/checkout/CheckoutPage').then((m) => ({ default: m.CheckoutPage })))
const OrderConfirmationPage = lazy(() =>
  import('@/pages/orders/OrderConfirmationPage').then((m) => ({ default: m.OrderConfirmationPage })),
)
const OrderHistoryPage = lazy(() =>
  import('@/pages/orders/OrderHistoryPage').then((m) => ({ default: m.OrderHistoryPage })),
)
const OrderDetailPage = lazy(() =>
  import('@/pages/orders/OrderDetailPage').then((m) => ({ default: m.OrderDetailPage })),
)

const DashboardPage = lazy(() => import('@/pages/admin/DashboardPage').then((m) => ({ default: m.DashboardPage })))
const ProductsListPage = lazy(() =>
  import('@/pages/admin/ProductsListPage').then((m) => ({ default: m.ProductsListPage })),
)
const ProductFormPage = lazy(() =>
  import('@/pages/admin/ProductFormPage').then((m) => ({ default: m.ProductFormPage })),
)
const AdminOrdersListPage = lazy(() =>
  import('@/pages/admin/OrdersListPage').then((m) => ({ default: m.OrdersListPage })),
)
const AdminOrderDetailPage = lazy(() =>
  import('@/pages/admin/OrderDetailPage').then((m) => ({ default: m.OrderDetailPage })),
)
const UsersListPage = lazy(() => import('@/pages/admin/UsersListPage').then((m) => ({ default: m.UsersListPage })))
const UserDetailPage = lazy(() =>
  import('@/pages/admin/UserDetailPage').then((m) => ({ default: m.UserDetailPage })),
)
const CouponsListPage = lazy(() =>
  import('@/pages/admin/CouponsListPage').then((m) => ({ default: m.CouponsListPage })),
)
const CouponFormPage = lazy(() =>
  import('@/pages/admin/CouponFormPage').then((m) => ({ default: m.CouponFormPage })),
)
const ReviewsQueuePage = lazy(() =>
  import('@/pages/admin/ReviewsQueuePage').then((m) => ({ default: m.ReviewsQueuePage })),
)
const CmsPagesListPage = lazy(() =>
  import('@/pages/admin/CmsPagesListPage').then((m) => ({ default: m.CmsPagesListPage })),
)
const CmsPageFormPage = lazy(() =>
  import('@/pages/admin/CmsPageFormPage').then((m) => ({ default: m.CmsPageFormPage })),
)
const BannersListPage = lazy(() =>
  import('@/pages/admin/BannersListPage').then((m) => ({ default: m.BannersListPage })),
)
const BannerFormPage = lazy(() =>
  import('@/pages/admin/BannerFormPage').then((m) => ({ default: m.BannerFormPage })),
)
const SupportQueuePage = lazy(() =>
  import('@/pages/admin/SupportQueuePage').then((m) => ({ default: m.SupportQueuePage })),
)
const AdminTicketDetailPage = lazy(() =>
  import('@/pages/admin/AdminTicketDetailPage').then((m) => ({ default: m.AdminTicketDetailPage })),
)
const AuditLogsPage = lazy(() => import('@/pages/admin/AuditLogsPage').then((m) => ({ default: m.AuditLogsPage })))
const FeatureFlagsPage = lazy(() =>
  import('@/pages/admin/FeatureFlagsPage').then((m) => ({ default: m.FeatureFlagsPage })),
)
const ApiKeysPage = lazy(() => import('@/pages/admin/ApiKeysPage').then((m) => ({ default: m.ApiKeysPage })))
const InsightsChatPage = lazy(() =>
  import('@/pages/admin/InsightsChatPage').then((m) => ({ default: m.InsightsChatPage })),
)

export const router = createBrowserRouter([
  {
    element: <RootLayout />,
    children: [
      { path: '/', element: <HomePage /> },
      { path: '/c/:categorySlug', element: <CatalogPage /> },
      { path: '/search', element: <CatalogPage /> },
      { path: '/p/:productSlug', element: <ProductPage /> },
      { path: '/pages/:slug', element: <CmsPage /> },
      { path: '/auth/login', element: <LoginPage /> },
      { path: '/auth/register', element: <RegisterPage /> },
      { path: '/auth/forgot', element: <ForgotPasswordPage /> },
      { path: '/auth/reset/:token', element: <ResetPasswordPage /> },
      { path: '/auth/verify', element: <VerifyEmailPage /> },
      { path: '/auth/verify/:token', element: <VerifyEmailPage /> },
      {
        path: '/account',
        element: (
          <ProtectedRoute>
            <AccountPage />
          </ProtectedRoute>
        ),
      },
      {
        path: '/account/wishlist',
        element: (
          <ProtectedRoute>
            <WishlistPage />
          </ProtectedRoute>
        ),
      },
      {
        path: '/account/support',
        element: (
          <ProtectedRoute>
            <SupportPage />
          </ProtectedRoute>
        ),
      },
      {
        path: '/account/support/:publicId',
        element: (
          <ProtectedRoute>
            <TicketDetailPage />
          </ProtectedRoute>
        ),
      },
      { path: '/cart', element: <CartPage /> },
      {
        path: '/checkout',
        element: (
          <ProtectedRoute>
            <CheckoutPage />
          </ProtectedRoute>
        ),
      },
      {
        path: '/order/confirmation/:orderNumber',
        element: (
          <ProtectedRoute>
            <OrderConfirmationPage />
          </ProtectedRoute>
        ),
      },
      {
        path: '/account/orders',
        element: (
          <ProtectedRoute>
            <OrderHistoryPage />
          </ProtectedRoute>
        ),
      },
      {
        path: '/account/orders/:orderNumber',
        element: (
          <ProtectedRoute>
            <OrderDetailPage />
          </ProtectedRoute>
        ),
      },
    ],
  },
  {
    path: '/admin',
    element: <AdminLayout />,
    children: [
      { index: true, element: <DashboardPage /> },
      { path: 'products', element: <ProductsListPage /> },
      { path: 'products/new', element: <ProductFormPage /> },
      { path: 'products/:id', element: <ProductFormPage /> },
      { path: 'orders', element: <AdminOrdersListPage /> },
      { path: 'orders/:orderNumber', element: <AdminOrderDetailPage /> },
      { path: 'users', element: <UsersListPage /> },
      { path: 'users/:publicId', element: <UserDetailPage /> },
      { path: 'coupons', element: <CouponsListPage /> },
      { path: 'coupons/new', element: <CouponFormPage /> },
      { path: 'coupons/:id', element: <CouponFormPage /> },
      { path: 'reviews', element: <ReviewsQueuePage /> },
      { path: 'cms/pages', element: <CmsPagesListPage /> },
      { path: 'cms/pages/new', element: <CmsPageFormPage /> },
      { path: 'cms/pages/:id', element: <CmsPageFormPage /> },
      { path: 'cms/banners', element: <BannersListPage /> },
      { path: 'cms/banners/new', element: <BannerFormPage /> },
      { path: 'cms/banners/:id', element: <BannerFormPage /> },
      { path: 'support', element: <SupportQueuePage /> },
      { path: 'support/:publicId', element: <AdminTicketDetailPage /> },
      { path: 'audit-logs', element: <AuditLogsPage /> },
      { path: 'feature-flags', element: <FeatureFlagsPage /> },
      { path: 'api-keys', element: <ApiKeysPage /> },
      { path: 'ask', element: <InsightsChatPage /> },
    ],
  },
])
