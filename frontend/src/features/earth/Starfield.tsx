import { useEffect, useRef } from 'react'

/** A small seeded generator, so the sky is the same sky on every visit. */
function mulberry32(seed: number) {
  let a = seed
  return () => {
    a |= 0
    a = (a + 0x6d2b79f5) | 0
    let t = Math.imul(a ^ (a >>> 15), 1 | a)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

/** Still stars behind the Earth. Drawn once per size; nothing here moves, so the Earth is the only thing that does. */
export function Starfield({ className }: { className?: string }) {
  const ref = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = ref.current
    if (!canvas) return
    const draw = () => {
      const ratio = Math.min(window.devicePixelRatio || 1, 2)
      const w = canvas.clientWidth
      const h = canvas.clientHeight
      canvas.width = Math.round(w * ratio)
      canvas.height = Math.round(h * ratio)
      const ctx = canvas.getContext('2d')
      if (!ctx) return
      ctx.setTransform(ratio, 0, 0, ratio, 0, 0)
      ctx.clearRect(0, 0, w, h)
      const random = mulberry32(20220224)
      const count = Math.round((w * h) / 2600)
      for (let i = 0; i < count; i += 1) {
        const x = random() * w
        const y = random() * h
        const magnitude = random()
        const radius = magnitude > 0.985 ? 1.5 : magnitude > 0.9 ? 1 : 0.6
        const warm = random() > 0.75
        ctx.globalAlpha = 0.25 + magnitude * 0.7
        ctx.fillStyle = warm ? '#ffe9c4' : '#dfe9ff'
        ctx.beginPath()
        ctx.arc(x, y, radius, 0, Math.PI * 2)
        ctx.fill()
      }
      ctx.globalAlpha = 1
    }
    draw()
    const observer = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(draw)
    observer?.observe(canvas)
    return () => observer?.disconnect()
  }, [])

  return <canvas ref={ref} className={className} aria-hidden="true" />
}
