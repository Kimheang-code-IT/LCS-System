import { expect, test } from './support/fixtures'

/**
 * Telegram diagnostics stay on the administrator settings screen: the
 * update-consumer status line and its inactive warning render there for
 * admins, while normal pages (the user profile connection card) only show a
 * short, non-technical hint.
 */
test('admin telegram settings show worker diagnostics', async ({ page }) => {
  await page.goto('/administration/system-settings')
  await page.getByRole('tab', { name: /telegram/i }).click()
  // Raw technical diagnostics remain available to administrators.
  await expect(page.getByText(/polling|webhook|worker/i).first()).toBeVisible({ timeout: 10_000 })
})

test('profile telegram connection hint is user-facing, not technical', async ({ page }) => {
  await page.goto('/profile')
  // Only verified for holders of telegram.chatbot.use; skip otherwise.
  const heading = page.getByRole('heading', { name: /telegram/i })
  if (!(await heading.count())) return
  // The env-var text (TELEGRAM_UPDATE_MODE, TELEGRAM_PUBLIC_APP_URL) must not
  // appear anywhere on a normal user page.
  const body = await page.locator('body').innerText()
  expect(body).not.toMatch(/TELEGRAM_UPDATE_MODE|TELEGRAM_PUBLIC_APP_URL/)
})
