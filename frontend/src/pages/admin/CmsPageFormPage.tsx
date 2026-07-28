import { useEffect } from 'react'
import { useNavigate, useParams } from 'react-router'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { createPage, deletePage, getPage, restorePage, updatePage } from '@/services/admin/cms'
import { Input } from '@/components/ui/Input'
import { Button } from '@/components/ui/Button'
import { FormAlert } from '@/components/ui/FormAlert'
import { Skeleton } from '@/components/feedback/Skeleton'
import { getApiErrorMessage } from '@/services/apiClient'

const schema = z.object({
  slug: z
    .string()
    .min(1, 'Slug is required')
    .max(255)
    .regex(/^[a-z0-9]+(?:-[a-z0-9]+)*$/, 'Lowercase letters, numbers, and hyphens only'),
  title: z.string().min(1, 'Title is required').max(255),
  body: z.string().min(1, 'Body is required'),
  status: z.enum(['draft', 'published']),
  seo_title: z.string().optional(),
  seo_description: z.string().optional(),
})

type FormValues = z.infer<typeof schema>

export function CmsPageFormPage() {
  const { id } = useParams()
  const isNew = !id || id === 'new'
  const pageId = isNew ? null : Number(id)
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const pageQuery = useQuery({
    queryKey: ['admin', 'cms', 'pages', pageId],
    queryFn: () => getPage(pageId!),
    enabled: pageId !== null,
  })

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { status: 'draft' },
  })

  useEffect(() => {
    if (pageQuery.data) {
      const p = pageQuery.data
      reset({
        slug: p.slug,
        title: p.title,
        body: p.body,
        status: p.status,
        seo_title: p.seo_title ?? '',
        seo_description: p.seo_description ?? '',
      })
    }
  }, [pageQuery.data, reset])

  const saveMutation = useMutation({
    mutationFn: (values: FormValues) => {
      const payload = {
        slug: values.slug,
        title: values.title,
        body: values.body,
        status: values.status,
        seo_title: values.seo_title || null,
        seo_description: values.seo_description || null,
      }
      return isNew ? createPage(payload) : updatePage(pageId!, payload)
    },
    onSuccess: (page) => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'cms', 'pages'] })
      if (isNew) navigate(`/admin/cms/pages/${page.id}`, { replace: true })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: () => deletePage(pageId!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'cms', 'pages'] })
      queryClient.invalidateQueries({ queryKey: ['admin', 'cms', 'pages', pageId] })
    },
  })

  const restoreMutation = useMutation({
    mutationFn: () => restorePage(pageId!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'cms', 'pages'] })
      queryClient.invalidateQueries({ queryKey: ['admin', 'cms', 'pages', pageId] })
    },
  })

  if (!isNew && pageQuery.isLoading) {
    return <Skeleton className="h-96 w-full" />
  }

  return (
    <div className="max-w-2xl">
      <h1 className="text-2xl font-semibold tracking-tight">{isNew ? 'New page' : pageQuery.data?.title}</h1>

      {!isNew && pageQuery.data?.is_deleted ? (
        <div className="mt-4">
          <FormAlert>
            This page is deleted and not publicly reachable.{' '}
            <button
              type="button"
              onClick={() => restoreMutation.mutate()}
              className="font-medium underline"
              disabled={restoreMutation.isPending}
            >
              Restore it
            </button>
          </FormAlert>
        </div>
      ) : null}

      <form onSubmit={handleSubmit((values) => saveMutation.mutate(values))} noValidate className="mt-6 flex flex-col gap-5">
        {saveMutation.isError ? <FormAlert>{getApiErrorMessage(saveMutation.error)}</FormAlert> : null}
        {saveMutation.isSuccess ? <FormAlert tone="success">Saved.</FormAlert> : null}

        <Input label="Slug" hint="Visible at /pages/{slug}" required error={errors.slug?.message} {...register('slug')} />
        <Input label="Title" required error={errors.title?.message} {...register('title')} />

        <div className="flex flex-col gap-1.5">
          <label htmlFor="body" className="text-sm font-medium text-text">
            Body <span className="text-text-tertiary">(HTML)</span>
          </label>
          <textarea
            id="body"
            rows={10}
            className="w-full rounded-(--radius-md) border border-border bg-surface-sunken px-3 py-2 font-mono text-sm text-text placeholder:text-text-tertiary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring"
            {...register('body')}
          />
          {errors.body ? <p className="text-xs text-danger">{errors.body.message}</p> : null}
        </div>

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
            <option value="published">Published</option>
          </select>
        </div>

        <Input label="SEO title (optional)" {...register('seo_title')} />
        <Input label="SEO description (optional)" {...register('seo_description')} />

        <div className="flex items-center gap-3">
          <Button type="submit" loading={saveMutation.isPending}>
            {isNew ? 'Create page' : 'Save changes'}
          </Button>
          {!isNew && !pageQuery.data?.is_deleted ? (
            <Button type="button" variant="destructive" loading={deleteMutation.isPending} onClick={() => deleteMutation.mutate()}>
              Delete
            </Button>
          ) : null}
        </div>
      </form>
    </div>
  )
}
