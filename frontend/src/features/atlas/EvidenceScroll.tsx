import { useEffect, useId, useRef, useState, type ReactNode } from 'react'
import type { ArtId } from './elementArt'
import { ScrollArt } from './elementArt'
import styles from './EvidenceScroll.module.css'

interface ButtonProps {
  art: ArtId
  label: string
  open: boolean
  /** True when an element was chosen and its scroll has not been opened yet. */
  unread: boolean
  controls: string
  onToggle: () => void
}

/** Bottom-right scroll. Its colour and glyph follow the selected element; it opens the evidence over the map. */
export function ScrollButton({ art, label, open, unread, controls, onToggle }: ButtonProps) {
  return (
    <button
      type="button"
      className={styles.scrollButton}
      aria-expanded={open}
      aria-controls={controls}
      data-element={art}
      data-unread={unread}
      onClick={onToggle}
      data-testid="evidence-scroll"
    >
      <span className={styles.scrollArt} key={art}>
        <ScrollArt id={art} />
      </span>
      <span className={styles.scrollLabel}>{label}</span>
    </button>
  )
}

export interface ScrollTab {
  id: string
  label: string
  content: ReactNode
}

interface OverlayProps {
  id: string
  title: string
  art: ArtId
  tabs: ScrollTab[]
  onClose: () => void
}

/** The opened scroll: a panel over the map with tabs (evidence, legend). The map underneath never moves. */
export function ScrollOverlay({ id, title, art, tabs, onClose }: OverlayProps) {
  const [tab, setTab] = useState(tabs[0]?.id ?? '')
  const headingRef = useRef<HTMLHeadingElement>(null)
  const base = useId()
  const activeTab = tabs.find((t) => t.id === tab) ?? tabs[0]

  useEffect(() => {
    headingRef.current?.focus()
  }, [])
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <section id={id} className={styles.overlay} aria-labelledby={`${base}-title`} data-element={art} data-testid="evidence-widget">
      <header className={styles.overlayHeader}>
        <h2 id={`${base}-title`} className={styles.overlayTitle} tabIndex={-1} ref={headingRef}>
          {title}
        </h2>
        <button type="button" className={styles.close} onClick={onClose} aria-label="Close scroll" data-testid="close-scroll">
          ×
        </button>
      </header>
      {tabs.length > 1 ? (
        <div role="tablist" aria-label="Scroll sections" className={styles.tabs}>
          {tabs.map((t) => (
            <button
              key={t.id}
              type="button"
              role="tab"
              id={`${base}-tab-${t.id}`}
              aria-selected={t.id === activeTab?.id}
              aria-controls={`${base}-panel`}
              className={styles.tab}
              onClick={() => setTab(t.id)}
              data-testid={`scroll-tab-${t.id}`}
            >
              {t.label}
            </button>
          ))}
        </div>
      ) : null}
      <div
        id={`${base}-panel`}
        role={tabs.length > 1 ? 'tabpanel' : undefined}
        aria-labelledby={tabs.length > 1 ? `${base}-tab-${activeTab?.id}` : undefined}
        className={styles.body}
        data-testid={`scroll-panel-${activeTab?.id}`}
      >
        {activeTab?.content}
      </div>
    </section>
  )
}
