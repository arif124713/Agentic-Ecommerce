import { createBrowserRouter } from 'react-router'
import { RootLayout } from '@/layouts/RootLayout'
import { AdminLayout } from '@/layouts/AdminLayout'
import { HomePage } from '@/pages/home/HomePage'
import { CatalogPage } from '@/pages/catalog/CatalogPage'
import { ProductPage } from '@/pages/product/ProductPage'
import { LoginPage } from '@/pages/auth/LoginPage'
import { RegisterPage } from '@/pages/auth/RegisterPage'
import { ForgotPasswordPage } from '@/pages/auth/ForgotPasswordPage'
import { ResetPasswordPage } from '@/pages/auth/ResetPasswordPage'
import { VerifyEmailPage } from '@/pages/auth/VerifyEmailPage'
import { AccountPage } from '@/pages/account/AccountPage'
import { WishlistPage } from '@/pages/account/WishlistPage'
import { SupportPage } from '@/pages/account/SupportPage'
import { TicketDetailPage } from '@/pages/account/TicketDetailPage'
import { CmsPage } from '@/pages/cms/CmsPage'
import { CartPage } from '@/pages/cart/CartPage'
import { CheckoutPage } from '@/pages/checkout/CheckoutPage'
import { OrderConfirmationPage } from '@/pages/orders/OrderConfirmationPage'
import { OrderHistoryPage } from '@/pages/orders/OrderHistoryPage'
import { OrderDetailPage } from '@/pages/orders/OrderDetailPage'
import { ProtectedRoute } from '@/components/auth/ProtectedRoute'
import { DashboardPage } from '@/pages/admin/DashboardPage'
import { ProductsListPage } from '@/pages/admin/ProductsListPage'
import { ProductFormPage } from '@/pages/admin/ProductFormPage'
import { OrdersListPage as AdminOrdersListPage } from '@/pages/admin/OrdersListPage'
import { OrderDetailPage as AdminOrderDetailPage } from '@/pages/admin/OrderDetailPage'
import { UsersListPage } from '@/pages/admin/UsersListPage'
import { UserDetailPage } from '@/pages/admin/UserDetailPage'
import { CouponsListPage } from '@/pages/admin/CouponsListPage'
import { CouponFormPage } from '@/pages/admin/CouponFormPage'
import { ReviewsQueuePage } from '@/pages/admin/ReviewsQueuePage'
import { CmsPagesListPage } from '@/pages/admin/CmsPagesListPage'
import { CmsPageFormPage } from '@/pages/admin/CmsPageFormPage'
import { BannersListPage } from '@/pages/admin/BannersListPage'
import { BannerFormPage } from '@/pages/admin/BannerFormPage'
import { SupportQueuePage } from '@/pages/admin/SupportQueuePage'
import { AdminTicketDetailPage } from '@/pages/admin/AdminTicketDetailPage'

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
    ],
  },
])
