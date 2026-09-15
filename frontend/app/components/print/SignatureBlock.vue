<script setup lang="ts">
export type PrintSignatureSlot = {
  caption: string
  name?: string
  stampUrl?: string
  signatureUrl?: string
}

withDefaults(defineProps<{
  slots: PrintSignatureSlot[]
  lines?: boolean
}>(), { lines: true })
</script>

<template>
  <div
    class="signature-grid grid gap-6 text-center text-[10px] text-black"
    :style="{ gridTemplateColumns: `repeat(${Math.max(slots.length || 1, 1)}, minmax(0, 1fr))` }"
  >
    <div v-for="slot in slots" :key="slot.caption" class="signature-slot">
      <p class="font-semibold whitespace-pre-line leading-snug">{{ slot.caption }}</p>
      <div class="signature-slot__body">
        <img
          v-if="slot.stampUrl"
          :src="slot.stampUrl"
          alt=""
          class="signature-slot__stamp"
        >
        <img
          v-if="slot.signatureUrl"
          :src="slot.signatureUrl"
          alt=""
          class="signature-slot__sign"
        >
        <div
          v-if="lines && !slot.stampUrl && !slot.signatureUrl"
          class="signature-slot__line"
          aria-hidden="true"
        />
      </div>
      <p v-if="slot.name" class="text-gray-700">{{ slot.name }}</p>
    </div>
  </div>
</template>

<style scoped>
.signature-slot__body {
  position: relative;
  margin: 8px auto 0;
  min-height: 22mm;
  width: 52mm;
}

.signature-slot__stamp,
.signature-slot__sign {
  position: absolute;
  left: 50%;
  top: 50%;
  max-height: 20mm;
  max-width: 48mm;
  transform: translate(-50%, -50%);
  object-fit: contain;
}

.signature-slot__sign {
  z-index: 1;
}

.signature-slot__line {
  position: absolute;
  bottom: 0;
  left: 50%;
  width: 42mm;
  border-bottom: 1px solid #000;
  transform: translateX(-50%);
}
</style>
