import type { ReactNode } from 'react'
import styles from './DecorativeFrame.module.css'

/** Restrained parchment border. Pure decoration: nothing meaningful lives in it. */
export function DecorativeFrame({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={`${styles.frame} ${className ?? ''}`}>
      <span className={`${styles.corner} ${styles.tl}`} aria-hidden="true" />
      <span className={`${styles.corner} ${styles.tr}`} aria-hidden="true" />
      <span className={`${styles.corner} ${styles.bl}`} aria-hidden="true" />
      <span className={`${styles.corner} ${styles.br}`} aria-hidden="true" />
      {children}
    </div>
  )
}
