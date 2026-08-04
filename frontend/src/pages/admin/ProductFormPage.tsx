import { useEffect, useState } from 'react'
import { useLocation, useNavigate, useParams } from 'react-router'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  createAdminProduct,
  deleteAdminProduct,
  getAdminProduct,
  listBrandOptions,
  listCategoryOptions,
  restoreAdminProduct,
  updateAdminProduct,
} from '@/services/admin/catalog'
import { Input } from '@/components/ui/Input'
import { Checkbox } from '@/components/ui/Checkbox'
import { Button } from '@/components/ui/Button'
import { FormAlert } from '@/components/ui/FormAlert'
import { Skeleton } from '@/components/feedback/Skeleton'
import { getApiErrorMessage } from '@/services/apiClient'
import { VariantsEditor } from '@/components/admin/VariantsEditor'
import { SeoHead } from '@/components/seo/SeoHead'

const schema = z.object({
  title: z.string().min(1, 'Title is required').max(255),
  subtitle: z.string().max(255).optional(),
  description: z.string().optional(),
  brand_id: z.coerce.number().int().positive('Select a brand'),
  category_id: z.coerce.number().int().positive('Select a category'),
  gender: z.string().optional(),
  material: z.string().max(120).optional(),
  base_color: z.string().max(40).optional(),
  currency: z.string().min(3).max(3),
  mrp: z.coerce.number().positive('MRP must be greater than 0'),
  price: z.coerce.number().positive('Price must be greater than 0'),
  status: z.enum(['draft', 'active', 'archived']),
  is_featured: z.boolean().optional(),
  is_trending: z.boolean().optional(),
  is_new_arrival: z.boolean().optional(),
  thumbnail_url: z.string().optional(),
  seo_title: z.string().max(255).optional(),
  seo_description: z.string().max(255).optional(),
})

// z.coerce.number() makes the schema's input type (raw <input> strings) differ from its output
// type (numbers) — useForm needs both: TFieldValues for the raw form state, TTransformedValues
// for what handleSubmit's callback actually receives after the resolver runs.
type FormInput = z.input<typeof schema>
type FormValues = z.output<typeof schema>

export function ProductFormPage() {
  const { id } = useParams()
  const isNew = !id || id === 'new'
  const productId = isNew ? null : Number(id)
  const navigate = useNavigate()
  const location = useLocation()
  const queryClient = useQueryClient()

  const brandsQuery = useQuery({ queryKey: ['admin', 'brand-options'], queryFn: listBrandOptions })
  const categoriesQuery = useQuery({ queryKey: ['admin', 'category-options'], queryFn: listCategoryOptions })
  const productQuery = useQuery({
    queryKey: ['admin', 'products', productId],
    queryFn: () => getAdminProduct(productId!),
    enabled: productId !== null,
  })

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<FormInput, unknown, FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { currency: 'INR', status: 'draft' },
  })

  useEffect(() => {
    if (productQuery.data) {
      const p = productQuery.data
      reset({
        title: p.title,
        subtitle: p.subtitle ?? '',
        description: p.description ?? '',
        brand_id: p.brand_id,
        category_id: p.category_id,
        gender: p.gender ?? '',
        material: p.material ?? '',
        base_color: p.base_color ?? '',
        currency: p.currency,
        mrp: Number(p.mrp),
        price: Number(p.price),
        status: p.status as FormValues['status'],
        is_featured: p.is_featured,
        is_trending: p.is_trending,
        is_new_arrival: p.is_new_arrival,
        thumbnail_url: p.thumbnail_url ?? '',
        seo_title: p.seo_title ?? '',
        seo_description: p.seo_description ?? '',
      })
    }
  }, [productQuery.data, reset])

  const saveMutation = useMutation({
    mutationFn: (values: FormValues) => {
      const payload = {
        ...values,
        subtitle: values.subtitle || null,
        description: values.description || null,
        gender: values.gender || null,
        material: values.material || null,
        base_color: values.base_color || null,
        thumbnail_url: values.thumbnail_url || null,
        seo_title: values.seo_title || null,
        seo_description: values.seo_description || null,
        is_featured: values.is_featured ?? false,
        is_trending: values.is_trending ?? false,
        is_new_arrival: values.is_new_arrival ?? false,
        mrp: String(values.mrp),
        price: String(values.price),
      }
      return isNew ? createAdminProduct(payload) : updateAdminProduct(productId!, payload)
    },
    onSuccess: (product) => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'products'] })
      if (isNew) navigate(`/admin/products/${product.id}`, { replace: true })
    },
  })

  const [confirmDelete, setConfirmDelete] = useState(false)
  const deleteMutation = useMutation({
    mutationFn: () => deleteAdminProduct(productId!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'products'] })
      navigate('/admin/products')
    },
  })
  const restoreMutation = useMutation({
    mutationFn: () => restoreAdminProduct(productId!),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['admin', 'products', productId] }),
  })

  if (!isNew && productQuery.isLoading) {
    return <Skeleton className="h-96 w-full" />
  }
  if (!isNew && productQuery.isError) {
    return <FormAlert>{getApiErrorMessage(productQuery.error)}</FormAlert>
  }

  return (
    <div className="max-w-3xl">
      <SeoHead
        title={isNew ? 'New Product' : 'Edit Product'}
        description="Create or edit a product listing in the BlackCart catalogue."
        path={location.pathname}
        noindex
      />
      <h1 className="text-2xl font-semibold tracking-tight">{isNew ? 'New product' : productQuery.data?.title}</h1>

      {productQuery.data?.is_deleted ? (
        <div className="mt-4">
          <FormAlert tone="info">
            This product is deleted and hidden from the storefront.{' '}
            <button
              type="button"
              onClick={() => restoreMutation.mutate()}
              disabled={restoreMutation.isPending}
              className="font-medium underline"
            >
              Restore it
            </button>
          </FormAlert>
        </div>
      ) : null}

      <form onSubmit={handleSubmit((values) => saveMutation.mutate(values))} noValidate className="mt-6 flex flex-col gap-5">
        {saveMutation.isError ? <FormAlert>{getApiErrorMessage(saveMutation.error)}</FormAlert> : null}
        {saveMutation.isSuccess ? <FormAlert tone="success">Saved.</FormAlert> : null}

        <Input label="Title" required error={errors.title?.message} {...register('title')} />
        <Input label="Subtitle" error={errors.subtitle?.message} {...register('subtitle')} />

        <div>
          <label htmlFor="description" className="text-sm font-medium text-text">
            Description
          </label>
          <textarea
            id="description"
            rows={4}
            className="mt-1.5 w-full rounded-(--radius-md) border border-border bg-surface-sunken p-3 text-sm text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring"
            {...register('description')}
          />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div className="flex flex-col gap-1.5">
            <label htmlFor="brand_id" className="text-sm font-medium text-text">
              Brand <span className="text-danger">*</span>
            </label>
            <select
              id="brand_id"
              className="h-11 rounded-(--radius-md) border border-border bg-surface-sunken px-3 text-sm text-text"
              {...register('brand_id')}
            >
              <option value="">Select brand</option>
              {(brandsQuery.data ?? []).map((b) => (
                <option key={b.id} value={b.id}>
                  {b.name}
                </option>
              ))}
            </select>
            {errors.brand_id ? <p className="text-xs text-danger">{errors.brand_id.message}</p> : null}
          </div>
          <div className="flex flex-col gap-1.5">
            <label htmlFor="category_id" className="text-sm font-medium text-text">
              Category <span className="text-danger">*</span>
            </label>
            <select
              id="category_id"
              className="h-11 rounded-(--radius-md) border border-border bg-surface-sunken px-3 text-sm text-text"
              {...register('category_id')}
            >
              <option value="">Select category</option>
              {(categoriesQuery.data ?? []).map((c) => (
                <option key={c.id} value={c.id}>
                  {'  '.repeat(c.depth)}
                  {c.name}
                </option>
              ))}
            </select>
            {errors.category_id ? <p className="text-xs text-danger">{errors.category_id.message}</p> : null}
          </div>
        </div>

        <div className="grid grid-cols-3 gap-4">
          <Input label="Gender" error={errors.gender?.message} {...register('gender')} />
          <Input label="Material" error={errors.material?.message} {...register('material')} />
          <Input label="Base colour" error={errors.base_color?.message} {...register('base_color')} />
        </div>

        <div className="grid grid-cols-3 gap-4">
          <Input label="MRP" type="number" step="0.01" required error={errors.mrp?.message} {...register('mrp')} />
          <Input label="Price" type="number" step="0.01" required error={errors.price?.message} {...register('price')} />
          <div className="flex flex-col gap-1.5">
            <label htmlFor="status" className="text-sm font-medium text-text">
              Status
            </label>
            <select
              id="status"
              className="h-11 rounded-(--radius-md) border border-border bg-surface-sunken px-3 text-sm text-text"
              {...register('status')}
            >
              <option value="draft">Draft</option>
              <option value="active">Active</option>
              <option value="archived">Archived</option>
            </select>
          </div>
        </div>

        <Input label="Thumbnail URL" error={errors.thumbnail_url?.message} {...register('thumbnail_url')} />

        <div className="flex flex-wrap gap-6">
          <Checkbox label="Featured" {...register('is_featured')} />
          <Checkbox label="Trending" {...register('is_trending')} />
          <Checkbox label="New arrival" {...register('is_new_arrival')} />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <Input label="SEO title" error={errors.seo_title?.message} {...register('seo_title')} />
          <Input label="SEO description" error={errors.seo_description?.message} {...register('seo_description')} />
        </div>

        <div className="flex items-center gap-3">
          <Button type="submit" loading={saveMutation.isPending}>
            {isNew ? 'Create product' : 'Save changes'}
          </Button>

          {!isNew && productQuery.data && !productQuery.data.is_deleted ? (
            confirmDelete ? (
              <>
                <Button type="button" variant="destructive" loading={deleteMutation.isPending} onClick={() => deleteMutation.mutate()}>
                  Confirm delete
                </Button>
                <Button type="button" variant="ghost" onClick={() => setConfirmDelete(false)}>
                  Cancel
                </Button>
              </>
            ) : (
              <Button type="button" variant="destructive" onClick={() => setConfirmDelete(true)}>
                Delete product
              </Button>
            )
          ) : null}
        </div>
      </form>

      {!isNew && productId !== null && productQuery.data ? (
        <div className="mt-10 border-t border-border pt-8">
          <VariantsEditor productId={productId} variants={productQuery.data.variants} />
        </div>
      ) : null}
    </div>
  )
}
