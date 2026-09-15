<script setup lang="ts">
import { defaultReportPathForUser } from '~/utils/freight/report-access'

definePageMeta({
  titleKey: 'freight.nav.reports',
})

const auth = useAuthStore()
const target = defaultReportPathForUser(key => auth.canAccessPage(key))
await navigateTo(target, { replace: true })
</script>
