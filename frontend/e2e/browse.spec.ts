import { test, expect } from '@playwright/test'

test.describe('Browsing', () => {
  test('home page loads with real product data', async ({ page }) => {
    await page.goto('/')
    await expect(page).toHaveTitle(/BlackCart/)
    await expect(page.getByRole('heading', { name: /fashion that speaks/i })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Trending now' })).toBeVisible()
    // At least one real product card should have rendered from the live catalogue.
    await expect(page.locator('img[alt]').first()).toBeVisible()
  })

  test('can navigate from home -> category (PLP) -> product (PDP)', async ({ page }) => {
    await page.goto('/')
    const categoryLink = page.getByRole('navigation', { name: 'Primary' }).getByRole('link').first()
    const categoryName = await categoryLink.textContent()
    await categoryLink.click()

    await expect(page).toHaveURL(/\/c\//)
    if (categoryName) {
      // level: 1 — plenty of product-title <h3>s on the page also happen to contain the category
      // name (e.g. "Men"), so an unscoped heading query would match dozens of unrelated elements.
      await expect(page.getByRole('heading', { level: 1, name: new RegExp(categoryName, 'i') })).toBeVisible()
    }

    // Click the first product card's title link to reach the PDP.
    const firstProductLink = page.locator('a[href^="/p/"]').first()
    await expect(firstProductLink).toBeVisible()
    await firstProductLink.click()

    await expect(page).toHaveURL(/\/p\//)
    await expect(page.getByRole('button', { name: /add to cart|out of stock/i })).toBeVisible()
  })
})
