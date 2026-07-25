import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { addWishlistItem, getWishlistSlugs, removeWishlistItem } from '@/services/discovery'
import { getApiErrorMessage } from '@/services/apiClient'
import { useCurrentUser } from './useAuth'

const WISHLIST_SLUGS_KEY = ['wishlist', 'slugs']

export function useWishlistSlugs() {
  const { data: user } = useCurrentUser()
  return useQuery({
    queryKey: WISHLIST_SLUGS_KEY,
    queryFn: getWishlistSlugs,
    enabled: Boolean(user),
    staleTime: 60 * 1000,
  })
}

export function useToggleWishlist() {
  const queryClient = useQueryClient()
  const slugsQuery = useWishlistSlugs()

  return useMutation({
    mutationFn: (productSlug: string) => {
      const isWishlisted = slugsQuery.data?.includes(productSlug) ?? false
      return isWishlisted ? removeWishlistItem(productSlug) : addWishlistItem(productSlug)
    },
    onMutate: async (productSlug) => {
      await queryClient.cancelQueries({ queryKey: WISHLIST_SLUGS_KEY })
      const previous = queryClient.getQueryData<string[]>(WISHLIST_SLUGS_KEY) ?? []
      const isWishlisted = previous.includes(productSlug)
      queryClient.setQueryData(
        WISHLIST_SLUGS_KEY,
        isWishlisted ? previous.filter((s) => s !== productSlug) : [...previous, productSlug],
      )
      return { previous }
    },
    onError: (error, _slug, context) => {
      if (context) queryClient.setQueryData(WISHLIST_SLUGS_KEY, context.previous)
      toast.error(getApiErrorMessage(error))
    },
    onSuccess: (wishlist) => {
      queryClient.setQueryData(
        WISHLIST_SLUGS_KEY,
        wishlist.items.map((i) => i.product.slug),
      )
    },
  })
}
