import { expect, test } from './support/fixtures'
import { apiSend, signIn } from './support/api'

/**
 * Role matrix: a read-only account sees no create control and cannot deep-link
 * into a create form or an administration page. The account is created through
 * the API and disabled afterwards so the run leaves no usable credential.
 */
const PASSWORD = 'Passw0rd!'

test('a viewer cannot create records or open administration pages', async ({ page, browser }) => {
  const stamp = Date.now()
  const username = `e2e.viewer.${stamp}@lcs-e2e.com`

  const created = await apiSend(page.context(), 'post', '/api/v1/users', {
    username,
    email: username,
    displayName: `E2E Viewer ${stamp}`,
    password: PASSWORD,
    roleCode: 'VIEWER',
  })
  expect(created.ok(), await created.text()).toBe(true)
  const userId = (await created.json()).data.id

  const viewerContext = await browser.newContext()
  const viewer = await viewerContext.newPage()
  try {
    await signIn(viewer, username, PASSWORD)

    // A permitted list page renders without any create affordance.
    await viewer.goto('/master-data/business-parties')
    await expect(viewer.getByRole('heading', { level: 1 })).toContainText('Business Parties')
    await expect(viewer.getByRole('link', { name: /^New\b/ })).toHaveCount(0)
    await expect(viewer.getByRole('button', { name: /^New\b/ })).toHaveCount(0)

    // A deep link into the create form is redirected away.
    await viewer.goto('/master-data/business-parties/new')
    await expect(viewer).not.toHaveURL(/\/master-data\/business-parties\/new/)

    // User administration is not a viewer page either.
    await viewer.goto('/administration/users')
    await expect(viewer).not.toHaveURL(/\/administration\/users$/)
  }
  finally {
    await viewerContext.close()
    // Disable rather than delete: the account may own audit rows.
    await apiSend(page.context(), 'patch', `/api/v1/users/${userId}`, { status: 'DISABLED' })
  }
})
