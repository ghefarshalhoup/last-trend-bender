import type { MonthRow } from '../../adapters/months'
import styles from './MonthPicker.module.css'

interface Props {
  rows: MonthRow[]
  selectedMonth: number | null
  onSelect: (calendarMonth: number) => void
}

/** Native toggle buttons: Tab + Enter/Space for keyboard, 48px targets for touch. */
export function MonthPicker({ rows, selectedMonth, onSelect }: Props) {
  return (
    <div role="group" aria-label="Choose a month to inspect" className={styles.row}>
      {rows.map((row) => {
        const selected = row.calendarMonth === selectedMonth
        return (
          <button
            key={row.calendarMonth}
            type="button"
            aria-pressed={selected}
            className={styles.month}
            data-selected={selected}
            data-low={row.target.lowCoverage}
            data-testid={`month-${row.calendarMonth}`}
            onClick={() => onSelect(row.calendarMonth)}
          >
            <span className={styles.name}>{row.long}</span>
            <span className={styles.days}>
              {row.target.validDays}/{row.target.calendarDays} days
              {row.target.lowCoverage ? (
                <>
                  {' '}
                  <span aria-hidden="true">▲</span>
                  <span className="sr-only"> low coverage</span>
                </>
              ) : null}
            </span>
          </button>
        )
      })}
    </div>
  )
}
