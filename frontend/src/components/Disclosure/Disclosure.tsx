import { AnimatePresence, motion } from 'motion/react'
import { useId, useState, type ReactNode } from 'react'
import styles from './Disclosure.module.css'

interface Props {
  title: string
  hint?: string
  defaultOpen?: boolean
  children: ReactNode
}

export function Disclosure({ title, hint, defaultOpen = false, children }: Props) {
  const [open, setOpen] = useState(defaultOpen)
  const panelId = useId()
  return (
    <div className={styles.item} data-open={open}>
      <h3 className={styles.heading}>
        <button
          type="button"
          className={styles.trigger}
          aria-expanded={open}
          aria-controls={panelId}
          onClick={() => setOpen((v) => !v)}
        >
          <span className={styles.title}>{title}</span>
          {hint ? <span className={styles.hint}>{hint}</span> : null}
          <span className={styles.chevron} aria-hidden="true" />
        </button>
      </h3>
      <AnimatePresence initial={false}>
        {open ? (
          <motion.div
            id={panelId}
            role="region"
            aria-label={title}
            className={styles.panel}
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
          >
            <div className={styles.inner}>{children}</div>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  )
}
