import sharp from 'sharp'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const root = join(dirname(fileURLToPath(import.meta.url)), '..')
const logoPath = join(root, 'public', 'logo.png')
const outPath = join(root, 'public', 'og-image.png')

const WIDTH = 1200
const HEIGHT = 630
const LOGO_MAX_HEIGHT = 300

const background = Buffer.from(`<svg width="${WIDTH}" height="${HEIGHT}" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#fce8e4"/>
      <stop offset="45%" stop-color="#ffffff"/>
      <stop offset="100%" stop-color="#f5f0ee"/>
    </linearGradient>
  </defs>
  <rect width="100%" height="100%" fill="url(#bg)"/>
</svg>`)

const logo = await sharp(logoPath)
  .resize({ height: LOGO_MAX_HEIGHT, fit: 'inside' })
  .png()
  .toBuffer()

const { width = 0, height = 0 } = await sharp(logo).metadata()

await sharp(background)
  .composite([{
    input: logo,
    left: Math.round((WIDTH - width) / 2),
    top: Math.round((HEIGHT - height) / 2),
  }])
  .png()
  .toFile(outPath)

console.log(`Wrote ${outPath} (${WIDTH}x${HEIGHT})`)
