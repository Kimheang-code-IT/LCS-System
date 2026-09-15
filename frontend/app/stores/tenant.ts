import { defineStore } from 'pinia'
import type { AuthUser } from '~/types/auth-user'
import type { BranchSelection } from '~/types/lcs/session'
import { useLcsRepositories } from '~/repositories'
import { canSelectAllBranches } from '~/utils/lcs/permissions'

const ORG_KEY = 'lcs-active-org'
const BRANCH_KEY = 'lcs-active-branch'

type OrganizationRow = {
  id: number
  organization_code?: string
  display_name?: string
  displayName?: string
}

type BranchRow = {
  id: number
  name?: string
  organization_id?: number
  organizationId?: number
  branch_code?: string
  branchCode?: string
}

function branchOrganizationId(branch: BranchRow): number {
  return Number(branch.organization_id ?? branch.organizationId ?? 0)
}

export const useTenantStore = defineStore('tenant', () => {
  const auth = useAuthStore()

  // Initial state derives from the signed-in user so the first paint already
  // reflects the permitted scope instead of a generic "all branches" default.
  const organizationId = useState('lcs-org-id', () => auth.user?.organizationId || 1)
  const branchId = useState<BranchSelection>('lcs-branch-id', () => {
    const user = auth.user
    if (!user) return 'all'
    if (user.permissionScope === 'ORGANIZATION') return 'all'
    if (user.branchId && (user.assignedBranchIds || []).includes(user.branchId)) return user.branchId
    return user.assignedBranchIds?.[0] ?? 'all'
  })

  const organizationRows = ref<OrganizationRow[]>([])
  const branchRows = ref<BranchRow[]>([])
  const loaded = ref(false)

  const organizations = computed(() => {
    const user = auth.user
    if (!user?.organizationId) return organizationRows.value
    return organizationRows.value.filter(org => org.id === user.organizationId)
  })

  const assignedBranches = computed(() => {
    const user = auth.user
    const orgId = organizationId.value
    const allowed = new Set(user?.assignedBranchIds || [])
    return branchRows.value.filter(branch =>
      branchOrganizationId(branch) === orgId && (allowed.size === 0 || allowed.has(branch.id)),
    )
  })

  const activeOrganization = computed(() =>
    organizations.value.find(org => org.id === organizationId.value) || organizations.value[0] || null,
  )

  const activeBranch = computed(() => {
    if (branchId.value === 'all') return null
    return assignedBranches.value.find(branch => branch.id === branchId.value) || null
  })

  const allowAllBranches = computed(() => canSelectAllBranches(auth.user))

  async function loadBranches() {
    if (!auth.user) return
    try {
      const repo = useLcsRepositories().organizations
      branchRows.value = await repo.listBranches(organizationId.value)
    }
    catch {
      branchRows.value = []
    }
  }

  async function load() {
    if (loaded.value || !auth.user) return
    loaded.value = true
    try {
      const repo = useLcsRepositories().organizations
      organizationRows.value = await repo.listOrganizations()
      if (organizations.value.length && !organizations.value.some(org => org.id === organizationId.value)) {
        organizationId.value = organizations.value[0]!.id
      }
      await loadBranches()
    }
    catch {
      loaded.value = false
    }
  }

  function persist() {
    if (!import.meta.client) return
    localStorage.setItem(ORG_KEY, String(organizationId.value))
    localStorage.setItem(BRANCH_KEY, String(branchId.value))
  }

  function applyUser(user: AuthUser | null) {
    if (!user) return
    organizationId.value = user.organizationId || organizationId.value
    const allowed = user.assignedBranchIds || []
    if (user.permissionScope === 'ORGANIZATION') {
      branchId.value = 'all'
    }
    else if (user.branchId && allowed.includes(user.branchId)) {
      branchId.value = user.branchId
    }
    else if (allowed[0]) {
      branchId.value = allowed[0]
    }
    persist()
    void load()
  }

  function setOrganization(id: number) {
    if (!organizations.value.some(org => org.id === id)) return
    organizationId.value = id
    if (branchId.value !== 'all' && !assignedBranches.value.some(branch => branch.id === branchId.value)) {
      branchId.value = allowAllBranches.value ? 'all' : (assignedBranches.value[0]?.id || 'all')
    }
    persist()
    void loadBranches()
  }

  function setBranch(id: BranchSelection) {
    if (id === 'all') {
      if (!allowAllBranches.value) return
      branchId.value = 'all'
      persist()
      return
    }
    if (!assignedBranches.value.some(branch => branch.id === id)) return
    branchId.value = id
    persist()
  }

  function hydrate() {
    const user = auth.user
    if (!user) return
    if (import.meta.client) {
      const savedOrg = Number(localStorage.getItem(ORG_KEY) || user.organizationId || 1)
      const savedBranch = localStorage.getItem(BRANCH_KEY)
      organizationId.value = user.organizationId || savedOrg
      if (savedBranch === 'all' && canSelectAllBranches(user)) {
        branchId.value = 'all'
      }
      else if (savedBranch && user.assignedBranchIds?.includes(Number(savedBranch))) {
        branchId.value = Number(savedBranch)
      }
      else {
        applyUser(user)
      }
    }
    else {
      applyUser(user)
    }
    void load()
  }

  return {
    organizationId,
    branchId,
    organizations,
    assignedBranches,
    activeOrganization,
    activeBranch,
    allowAllBranches,
    load,
    applyUser,
    setOrganization,
    setBranch,
    hydrate,
  }
})
