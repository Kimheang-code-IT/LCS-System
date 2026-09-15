<script setup lang="ts">
import { freightReportPath, getFreightReport } from '~/config/freight-reports'

definePageMeta({
  titleKey: 'freight.nav.reports',
})

const route = useRoute()
const slug = String(route.params.slug || '')
const report = getFreightReport(slug)
await navigateTo(freightReportPath(report), { replace: true })
</script>
