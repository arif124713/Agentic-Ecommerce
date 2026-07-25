import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import {
  addCartItem,
  applyCoupon,
  clearCart,
  getCart,
  removeCartItem,
  removeCoupon,
  updateCartItem,
} from '@/services/cart'
import { getApiErrorMessage } from '@/services/apiClient'

const CART_KEY = ['cart']

export function useCart() {
  return useQuery({
    queryKey: CART_KEY,
    queryFn: getCart,
    staleTime: 0,
  })
}

export function useAddToCart() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ variantId, quantity }: { variantId: number; quantity: number }) =>
      addCartItem(variantId, quantity),
    onSuccess: (cart) => {
      queryClient.setQueryData(CART_KEY, cart)
      toast.success('Added to cart')
    },
    onError: (error) => toast.error(getApiErrorMessage(error)),
  })
}

export function useUpdateCartItem() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ itemId, quantity }: { itemId: number; quantity: number }) => updateCartItem(itemId, quantity),
    onSuccess: (cart) => queryClient.setQueryData(CART_KEY, cart),
    onError: (error) => toast.error(getApiErrorMessage(error)),
  })
}

export function useRemoveCartItem() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (itemId: number) => removeCartItem(itemId),
    onSuccess: (cart) => queryClient.setQueryData(CART_KEY, cart),
    onError: (error) => toast.error(getApiErrorMessage(error)),
  })
}

export function useClearCart() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: clearCart,
    onSuccess: (cart) => queryClient.setQueryData(CART_KEY, cart),
  })
}

export function useApplyCoupon() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (code: string) => applyCoupon(code),
    onSuccess: (cart) => {
      queryClient.setQueryData(CART_KEY, cart)
      toast.success(`Coupon ${cart.coupon_code} applied`)
    },
    onError: (error) => toast.error(getApiErrorMessage(error)),
  })
}

export function useRemoveCoupon() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: removeCoupon,
    onSuccess: (cart) => queryClient.setQueryData(CART_KEY, cart),
  })
}
