import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { addVariant, deleteVariant, updateVariant } from '@/services/admin/catalog'
import { Button } from '@/components/ui/Button'
import { cn } from '@/lib/cn'
import type { AdminVariant, VariantInput } from '@/types/admin'

interface VariantsEditorProps {
  productId: number
  variants: AdminVariant[]
}

function emptyDraft(): VariantInput {
  return { sku: '', size: '', color: '', color_hex: '', mrp: '0', price: '0', stock: 0, low_stock_threshold: 5, is_active: true }
}

function VariantRow({ productId, variant }: { productId: number; variant: AdminVariant }) {
  const queryClient = useQueryClient()
  const [draft, setDraft] = useState<VariantInput>({
    sku: variant.sku,
    size: variant.size ?? '',
    color: variant.color ?? '',
    color_hex: variant.color_hex ?? '',
    mrp: variant.mrp,
    price: variant.price,
    stock: variant.stock,
    low_stock_threshold: variant.low_stock_threshold,
    is_active: variant.is_active,
  })
  const [dirty, setDirty] = useState(false)

  const saveMutation = useMutation({
    mutationFn: () => updateVariant(variant.id, draft),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'products', productId] })
      setDirty(false)
    },
  })
  const deleteMutation = useMutation({
    mutationFn: () => deleteVariant(variant.id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['admin', 'products', productId] }),
  })

  const update = <K extends keyof VariantInput>(key: K, value: VariantInput[K]) => {
    setDraft((d) => ({ ...d, [key]: value }))
    setDirty(true)
  }

  const cellClass = 'h-9 w-full rounded-(--radius-sm) border border-border bg-surface-sunken px-2 text-sm text-text'

  return (
    <tr className={cn(!variant.is_active && 'opacity-60')}>
      <td className="py-1.5 pr-2">
        <input className={cellClass} value={draft.sku} onChange={(e) => update('sku', e.target.value)} />
      </td>
      <td className="py-1.5 pr-2">
        <input className={cn(cellClass, 'w-16')} value={draft.size ?? ''} onChange={(e) => update('size', e.target.value)} />
      </td>
      <td className="py-1.5 pr-2">
        <input className={cn(cellClass, 'w-20')} value={draft.color ?? ''} onChange={(e) => update('color', e.target.value)} />
      </td>
      <td className="py-1.5 pr-2">
        <input
          type="number"
          step="0.01"
          className={cn(cellClass, 'w-24')}
          value={draft.mrp}
          onChange={(e) => update('mrp', e.target.value)}
        />
      </td>
      <td className="py-1.5 pr-2">
        <input
          type="number"
          step="0.01"
          className={cn(cellClass, 'w-24')}
          value={draft.price}
          onChange={(e) => update('price', e.target.value)}
        />
      </td>
      <td className="py-1.5 pr-2">
        <input
          type="number"
          className={cn(cellClass, 'w-20')}
          value={draft.stock}
          onChange={(e) => update('stock', Number(e.target.value))}
        />
      </td>
      <td className="py-1.5 pr-2">
        <input
          type="number"
          className={cn(cellClass, 'w-16')}
          value={draft.low_stock_threshold}
          onChange={(e) => update('low_stock_threshold', Number(e.target.value))}
        />
      </td>
      <td className="py-1.5 pr-2 text-center">
        <input type="checkbox" checked={draft.is_active} onChange={(e) => update('is_active', e.target.checked)} className="h-4 w-4 accent-white" />
      </td>
      <td className="py-1.5 pr-2">
        <div className="flex gap-1.5">
          <Button size="sm" variant="secondary" disabled={!dirty} loading={saveMutation.isPending} onClick={() => saveMutation.mutate()}>
            Save
          </Button>
          <Button size="sm" variant="destructive" loading={deleteMutation.isPending} onClick={() => deleteMutation.mutate()}>
            Remove
          </Button>
        </div>
      </td>
    </tr>
  )
}

export function VariantsEditor({ productId, variants }: VariantsEditorProps) {
  const queryClient = useQueryClient()
  const [draft, setDraft] = useState<VariantInput>(emptyDraft())

  const addMutation = useMutation({
    mutationFn: () => addVariant(productId, draft),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'products', productId] })
      setDraft(emptyDraft())
    },
  })

  return (
    <div>
      <h2 className="text-xs font-medium uppercase tracking-wide text-text-tertiary">Variants</h2>

      <div className="mt-4 overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="text-xs uppercase tracking-wide text-text-tertiary">
              <th className="pb-2 pr-2 font-medium">SKU</th>
              <th className="pb-2 pr-2 font-medium">Size</th>
              <th className="pb-2 pr-2 font-medium">Colour</th>
              <th className="pb-2 pr-2 font-medium">MRP</th>
              <th className="pb-2 pr-2 font-medium">Price</th>
              <th className="pb-2 pr-2 font-medium">Stock</th>
              <th className="pb-2 pr-2 font-medium">Threshold</th>
              <th className="pb-2 pr-2 font-medium">Active</th>
              <th className="pb-2 pr-2 font-medium" />
            </tr>
          </thead>
          <tbody>
            {variants.map((v) => (
              <VariantRow key={v.id} productId={productId} variant={v} />
            ))}
          </tbody>
        </table>
      </div>

      <div className="mt-6 rounded-(--radius-md) border border-border p-4">
        <h3 className="text-xs font-medium uppercase tracking-wide text-text-tertiary">Add variant</h3>
        <div className="mt-3 grid grid-cols-2 gap-3 md:grid-cols-4">
          <input
            placeholder="SKU"
            value={draft.sku}
            onChange={(e) => setDraft((d) => ({ ...d, sku: e.target.value }))}
            className="h-10 rounded-(--radius-sm) border border-border bg-surface-sunken px-2 text-sm text-text"
          />
          <input
            placeholder="Size"
            value={draft.size ?? ''}
            onChange={(e) => setDraft((d) => ({ ...d, size: e.target.value }))}
            className="h-10 rounded-(--radius-sm) border border-border bg-surface-sunken px-2 text-sm text-text"
          />
          <input
            placeholder="Colour"
            value={draft.color ?? ''}
            onChange={(e) => setDraft((d) => ({ ...d, color: e.target.value }))}
            className="h-10 rounded-(--radius-sm) border border-border bg-surface-sunken px-2 text-sm text-text"
          />
          <input
            type="number"
            placeholder="Stock"
            value={draft.stock}
            onChange={(e) => setDraft((d) => ({ ...d, stock: Number(e.target.value) }))}
            className="h-10 rounded-(--radius-sm) border border-border bg-surface-sunken px-2 text-sm text-text"
          />
          <input
            type="number"
            step="0.01"
            placeholder="MRP"
            value={draft.mrp}
            onChange={(e) => setDraft((d) => ({ ...d, mrp: e.target.value }))}
            className="h-10 rounded-(--radius-sm) border border-border bg-surface-sunken px-2 text-sm text-text"
          />
          <input
            type="number"
            step="0.01"
            placeholder="Price"
            value={draft.price}
            onChange={(e) => setDraft((d) => ({ ...d, price: e.target.value }))}
            className="h-10 rounded-(--radius-sm) border border-border bg-surface-sunken px-2 text-sm text-text"
          />
        </div>
        <Button
          size="sm"
          className="mt-3"
          disabled={!draft.sku.trim()}
          loading={addMutation.isPending}
          onClick={() => addMutation.mutate()}
        >
          Add variant
        </Button>
      </div>
    </div>
  )
}
