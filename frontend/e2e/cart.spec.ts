import { test, expect, type Page } from '@playwright/test'

/** Quick-adds the first product card on the current page, handling the optional size-picker step
 * (a single-size/single-variant product adds immediately; a multi-size product shows a picker). */
async function quickAddFirstProduct(page: Page) {
  const card = page.locator('.group.relative').first()
  await card.hover()
  await card.getByRole('button', { name: 'Quick add' }).click()

  // The size picker only appears after an async product-detail fetch resolves — isVisible() has
  // no wait semantics (unlike expect().toBeVisible()) and would just check "right now" before
  // that fetch finishes, so this uses waitFor (which does poll) to give it a real chance to appear.
  const sizeGroup = page.getByRole('group', { name: 'Choose a size to add to cart' })
  const appeared = await sizeGroup
    .waitFor({ state: 'visible', timeout: 3000 })
    .then(() => true)
    .catch(() => false)
  if (appeared) {
    await sizeGroup.getByRole('button').first().click()
  }
}

test.describe('Cart', () => {
  test('quick-add opens the cart drawer with the added item', async ({ page }) => {
    await page.goto('/')
    await quickAddFirstProduct(page)

    const drawer = page.getByRole('dialog', { name: 'Shopping cart' })
    await expect(drawer).toBeVisible()
    await expect(drawer.getByText(/^Cart \(\d+\)$/)).toBeVisible()
  })

  test('cart drawer: Escape closes it and returns focus to whatever opened it', async ({ page }) => {
    // Opened via the header's cart button directly (it opens regardless of whether the cart has
    // items — an empty-state message renders inside) so the "focus returns to the trigger"
    // assertion is unambiguous, and isolated from quick-add's own open/close sequence.
    await page.goto('/')
    const cartButton = page.getByRole('button', { name: /^Cart/ })
    await cartButton.click()
    await expect(page.getByRole('dialog', { name: 'Shopping cart' })).toBeVisible()

    await page.keyboard.press('Escape')
    await expect(page.getByRole('dialog', { name: 'Shopping cart' })).toBeHidden()
    await expect(cartButton).toBeFocused()
  })

  test('cart page: update quantity and remove item', async ({ page }) => {
    await page.goto('/')
    await quickAddFirstProduct(page)
    await page.keyboard.press('Escape')

    await page.goto('/cart')
    const main = page.locator('#main-content')
    await expect(main.getByRole('heading', { name: 'Your cart' })).toBeVisible()

    // Scoped to <main>, not the whole page — the header's cart drawer stays mounted (just hidden)
    // and renders the same item/quantity text, which would otherwise match too.
    await main.getByRole('button', { name: 'Increase quantity' }).click()
    await expect(main.getByText('2', { exact: true })).toBeVisible()

    await main.getByRole('button', { name: 'Remove item' }).click()
    await expect(main.getByText('Your cart is empty')).toBeVisible({ timeout: 5000 })
  })
})
