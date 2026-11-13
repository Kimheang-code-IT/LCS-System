import { expect, test } from './support/fixtures'
import { apiSend } from './support/api'

/**
 * The create-user form must always offer a create action — not a hidden button
 * and not "Save changes" — and it must save the account once the fields are
 * valid. The account is disabled afterwards through the API.
 */
test('creating a user shows a create button and saves the account', async ({ page }) => {
  const stamp = Date.now().toString().slice(-7)
  const username = `e2e.ui.${stamp}`

  await page.goto('/administration/users/new')

  // The action is visible before anything is typed (it used to be hidden until
  // the password passed the strength policy).
  const createButton = page.getByRole('button', { name: /^(Create|Create user)$/ })
  await expect(createButton).toBeVisible()
  await expect(page.getByRole('button', { name: 'Save changes' })).toHaveCount(0)

  // An empty submit is refused by the form, not by a missing button.
  await createButton.click()
  await expect(page.getByText('Username is required.')).toBeVisible()
  await expect(page).toHaveURL(/\/administration\/users\/new\/?$/)

  await page.getByRole('textbox', { name: 'Username*' }).fill(username)
  await page.getByRole('textbox', { name: 'Display Name*' }).fill(`E2E UI ${stamp}`)
  await page.getByRole('textbox', { name: 'Email*' }).fill(`${username}@lcs-e2e.com`)
  await page.getByRole('textbox', { name: 'Password' }).fill('Passw0rd!')
  await page.getByRole('button', { name: /^Assigned Role/ }).click()
  await page.getByRole('option', { name: /Viewer/ }).first().click()

  await createButton.click()
  // Creating a user reveals the initial password once; the page leaves only
  // after the administrator closes that dialog.
  await expect(page.getByRole('dialog')).toBeVisible()
  await page.getByRole('dialog').getByRole('button', { name: /^Close$/ }).last().click()
  await expect(page).toHaveURL(/\/administration\/users$/)

  const users = await page.context().request.get('/api/v1/users?page_size=200')
  const body = await users.json()
  const rows = (Array.isArray(body.data) ? body.data : body.data.items) as Array<{ id: string, username: string }>
  const created = rows.find(row => row.username === username)
  expect(created, username).toBeTruthy()
  await apiSend(page.context(), 'patch', `/api/v1/users/${created!.id}`, { status: 'DISABLED' })
})
