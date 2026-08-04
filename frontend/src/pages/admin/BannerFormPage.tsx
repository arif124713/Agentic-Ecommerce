import { useEffect } from 'react'
import { useLocation, useNavigate, useParams } from 'react-router'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { createBanner, deleteBanner, getBanner, updateBanner } from '@/services/admin/cms'
import { Input } from '@/components/ui/Input'
import { Checkbox } from '@/components/ui/Checkbox'
import { Button } from '@/components/ui/Button'
import { FormAlert } from '@/components/ui/FormAlert'
import { Skeleton } from '@/components/feedback/Skeleton'
import { getApiErrorMessage } from '@/services/apiClient'
import { SeoHead } from '@/components/seo/SeoHead'

const schema = z.object({
  placement: z.string().min(1, 'Placement is required').max(40),
  title: z.string().min(1, 'Title is required').max(255),
  image_url: z.string().min(1, 'Image URL is required').max(512),
  link_url: z.string().optional(),
  sort_order: z.coerce.number().int().default(0),
  is_active: z.boolean().optional(),
})

type FormInput = z.input<typeof schema>
type FormValues = z.output<typeof schema>

export function BannerFormPage() {
  const { id } = useParams()
  const isNew = !id || id === 'new'
  const bannerId = isNew ? null : Number(id)
  const navigate = useNavigate()
  const location = useLocation()
  const queryClient = useQueryClient()

  const bannerQuery = useQuery({
    queryKey: ['admin', 'cms', 'banners', bannerId],
    queryFn: () => getBanner(bannerId!),
    enabled: bannerId !== null,
  })

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<FormInput, unknown, FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { placement: 'home_promo', sort_order: 0, is_active: true },
  })

  useEffect(() => {
    if (bannerQuery.data) {
      const b = bannerQuery.data
      reset({
        placement: b.placement,
        title: b.title,
        image_url: b.image_url,
        link_url: b.link_url ?? '',
        sort_order: b.sort_order,
        is_active: b.is_active,
      })
    }
  }, [bannerQuery.data, reset])

  const saveMutation = useMutation({
    mutationFn: (values: FormValues) => {
      const payload = {
        placement: values.placement,
        title: values.title,
        image_url: values.image_url,
        link_url: values.link_url || null,
        sort_order: values.sort_order,
        is_active: values.is_active ?? true,
      }
      return isNew ? createBanner(payload) : updateBanner(bannerId!, payload)
    },
    onSuccess: (banner) => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'cms', 'banners'] })
      if (isNew) navigate(`/admin/cms/banners/${banner.id}`, { replace: true })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: () => deleteBanner(bannerId!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'cms', 'banners'] })
      navigate('/admin/cms/banners')
    },
  })

  if (!isNew && bannerQuery.isLoading) {
    return <Skeleton className="h-72 w-full" />
  }

  return (
    <div className="max-w-lg">
      <SeoHead
        title={isNew ? 'New Banner' : 'Edit Banner'}
        description="Create or edit a promotional banner for the BlackCart storefront."
        path={location.pathname}
        noindex
      />
      <h1 className="text-2xl font-semibold tracking-tight">{isNew ? 'New banner' : bannerQuery.data?.title}</h1>

      <form onSubmit={handleSubmit((values) => saveMutation.mutate(values))} noValidate className="mt-6 flex flex-col gap-5">
        {saveMutation.isError ? <FormAlert>{getApiErrorMessage(saveMutation.error)}</FormAlert> : null}
        {saveMutation.isSuccess ? <FormAlert tone="success">Saved.</FormAlert> : null}

        <Input
          label="Placement"
          hint="e.g. home_promo"
          required
          error={errors.placement?.message}
          {...register('placement')}
        />
        <Input label="Title" required error={errors.title?.message} {...register('title')} />
        <Input label="Image URL" required error={errors.image_url?.message} {...register('image_url')} />
        <Input label="Link URL (optional)" error={errors.link_url?.message} {...register('link_url')} />
        <Input label="Sort order" type="number" error={errors.sort_order?.message} {...register('sort_order')} />
        <Checkbox label="Active" {...register('is_active')} />

        <div className="flex items-center gap-3">
          <Button type="submit" loading={saveMutation.isPending}>
            {isNew ? 'Create banner' : 'Save changes'}
          </Button>
          {!isNew ? (
            <Button type="button" variant="destructive" loading={deleteMutation.isPending} onClick={() => deleteMutation.mutate()}>
              Delete
            </Button>
          ) : null}
        </div>
      </form>
    </div>
  )
}
