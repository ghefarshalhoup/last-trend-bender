import { useEffect, useId } from 'react'
import { AvatarMark } from '../../components/Avatar/AvatarMark'
import styles from './AvatarPanel.module.css'

export interface Insight {
  key: string
  title: string
  text: string
  focused: boolean
  onShow?: () => void
}
export interface InsightGroup {
  label: string | null
  items: Insight[]
}

interface Props {
  accent?: string
  /** A short line beside the portrait: instructions before Investigate, or a notice. */
  speech: string | null
  groups: InsightGroup[]
  open: boolean
  onToggle: () => void
  action?: { label: string; onClick: () => void }
}

/**
 * The guide as a portrait. Folded, it takes little room; a badge counts the insights ready.
 * Opened, it lists one insight per open card, built only from that card's own fields.
 */
export function AvatarPanel({ accent, speech, groups, open, onToggle, action }: Props) {
  const panelId = useId()
  const count = groups.reduce((n, g) => n + g.items.length, 0)
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onToggle()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onToggle])

  return (
    <div className={styles.wrap} data-open={open}>
      {open ? (
        <section id={panelId} className={styles.panel} aria-label="What the cards say" data-testid="avatar-panel">
          <header className={styles.head}>
            <h2 className={styles.title}>What the cards say</h2>
            {action ? (
              <button type="button" className={styles.action} onClick={action.onClick} data-testid="guide-action">{action.label}</button>
            ) : null}
            <button type="button" className={styles.close} onClick={onToggle} aria-label="Close insights" data-testid="avatar-close">×</button>
          </header>
          {count === 0 ? (
            <p className={styles.empty}>Open a variable and I will read its card for you.</p>
          ) : (
            groups.map((g) => (
              <div key={g.label ?? 'one'} className={styles.group}>
                {g.label ? <h3 className={styles.groupLabel}>{g.label}</h3> : null}
                <ul className={styles.list}>
                  {g.items.map((it) => (
                    <li key={it.key} className={styles.item} data-focused={it.focused} data-testid={`insight-${it.key}`}>
                      <strong>{it.title}</strong>
                      <p>{it.text}</p>
                    </li>
                  ))}
                </ul>
              </div>
            ))
          )}
          <p className={styles.note}>Each insight reads one card. It reports the test, never a cause.</p>
        </section>
      ) : null}
      <div className={styles.row}>
        <button
          type="button"
          className={styles.portrait}
          aria-expanded={open}
          aria-controls={open ? panelId : undefined}
          onClick={onToggle}
          data-testid="avatar-button"
          data-tour="avatar"
        >
          <AvatarMark size={56} accent={accent} />
          {count > 0 ? <span className={styles.badge} key={count} data-testid="avatar-badge">{count}</span> : null}
          <span className="sr-only">{open ? 'Hide insights' : `Show insights (${count})`}</span>
        </button>
        {speech && !open ? (
          <p className={styles.speech} aria-live="polite" data-testid="guide-bubble">{speech}</p>
        ) : null}
      </div>
    </div>
  )
}
