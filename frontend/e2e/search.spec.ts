import { test, expect } from '@playwright/test'

test.describe('Search', () => {
  test('searching a common term navigates to results with matching products', async ({ page }) => {
    await page.goto('/')
    await page.getByRole('button', { name: 'Search' }).click()

    const input = page.getByRole('combobox', { name: 'Search products' })
    await expect(input).toBeFocused()
    await input.fill('shirt')
    await input.press('Enter')

    await expect(page).toHaveURL(/\/search\?q=shirt/)
    // The real backend (Algolia in production, MySQL fallback in dev) should return real matches
    // for a generic term this heavily-menswear catalogue is full of.
    await expect(page.locator('a[href^="/p/"]').first()).toBeVisible()
  })

  test('autocomplete suggests real products while typing', async ({ page }) => {
    await page.goto('/')
    await page.getByRole('button', { name: 'Search' }).click()
    await page.getByRole('combobox', { name: 'Search products' }).fill('shirt')

    const listbox = page.getByRole('listbox', { name: 'Search suggestions' })
    await expect(listbox).toBeVisible()
    await expect(listbox.getByRole('option').first()).toBeVisible()
  })
})
