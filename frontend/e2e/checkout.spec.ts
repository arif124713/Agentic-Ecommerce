import { test, expect } from '@playwright/test'

function uniqueEmail() {
  return `e2e-checkout-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@example.com`
}

const PASSWORD = 'Str0ng!Passw0rd'

test('full journey: register -> browse -> add to cart -> checkout (COD) -> order confirmation', async ({ page }) => {
  const email = uniqueEmail()

  await page.goto('/auth/register')
  await page.locator('input[name="first_name"]').fill('E2E')
  await page.locator('input[name="email"]').fill(email)
  await page.locator('input[name="password"]').fill(PASSWORD)
  await page.locator('input[name="confirm_password"]').fill(PASSWORD)
  await page.getByLabel(/agree to the/i).check()
  await page.getByRole('button', { name: 'Create account' }).click()
  await expect(page).toHaveURL(/\/auth\/verify/)

  await page.goto('/auth/login')
  await page.locator('input[name="email"]').fill(email)
  await page.locator('input[name="password"]').fill(PASSWORD)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page).toHaveURL(/\/account/)

  // Browse to a real product and add it to the cart, selecting a size/colour if the product has
  // variants (a single-variant product's "Add to cart" is already enabled with nothing to pick).
  await page.goto('/search?q=shirt')
  await page.locator('a[href^="/p/"]').first().click()
  await expect(page).toHaveURL(/\/p\//)

  // isVisible() has no wait/retry semantics (unlike expect().toBeVisible()) — waitFor actually
  // polls, which matters here since the PDP's variant data loads via its own async query.
  const sizeFieldset = page.locator('fieldset', { has: page.getByText(/^Size/) })
  const hasSize = await sizeFieldset
    .waitFor({ state: 'visible', timeout: 3000 })
    .then(() => true)
    .catch(() => false)
  if (hasSize) await sizeFieldset.getByRole('button').first().click()

  const colourFieldset = page.locator('fieldset', { has: page.getByText(/^Colour/) })
  const hasColour = await colourFieldset
    .waitFor({ state: 'visible', timeout: 1000 })
    .then(() => true)
    .catch(() => false)
  if (hasColour) await colourFieldset.getByRole('button').first().click()

  await page.getByRole('button', { name: 'Add to cart' }).click()
  await expect(page.getByRole('dialog', { name: 'Shopping cart' })).toBeVisible()
  await page.getByRole('link', { name: 'Checkout' }).click()

  await expect(page).toHaveURL(/\/checkout/)
  await expect(page.getByRole('heading', { name: 'Checkout' })).toBeVisible()

  // First-time checkout: no saved address yet, so the address form is already open.
  await page.getByLabel('Full name').fill('E2E Test User')
  await page.getByLabel('Phone').fill('01700000000')
  await page.getByLabel('Street address').fill('123 Test Street')
  await page.getByLabel('City').fill('Dhaka')
  await page.getByLabel('Division').fill('Dhaka')
  await page.getByRole('button', { name: 'Save address' }).click()

  // Cash on delivery avoids needing the card-number simulator field for this journey.
  await page.getByRole('radio', { name: /cash on delivery/i }).check()

  await page.getByLabel(/agree to the terms of service/i).check()
  await page.getByRole('button', { name: 'Place order' }).click()

  await expect(page).toHaveURL(/\/order\/confirmation\//, { timeout: 15_000 })
  await expect(page.getByText(/order/i).first()).toBeVisible()
})
