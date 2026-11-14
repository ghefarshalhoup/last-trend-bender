import { useId } from 'react'
import { BASELINES, type BaselineOption } from '../../adapters/baselines'
import { yearsRangeLabel } from '../../adapters/format'
import type { Comparison } from '../../api/types'
import styles from './BaselineSelector.module.css'

interface Props {
  value: BaselineOption
  onChange: (option: BaselineOption) => void
  comparisons: Record<string, Comparison>
}

export function BaselineSelector({ value, onChange, comparisons }: Props) {
  const name = useId()
  return (
    <fieldset className={styles.set}>
      <legend className={styles.legend}>Compare 2022 with</legend>
      <div className={styles.options}>
        {BASELINES.map((option) => {
          const years = comparisons[option.id]?.baseline_years_requested ?? []
          const checked = option.id === value.id
          return (
            <label key={option.id} className={styles.option} data-checked={checked}>
              <input
                type="radio"
                name={name}
                value={option.id}
                checked={checked}
                onChange={() => onChange(option)}
                className={styles.input}
              />
              <span className={styles.years}>{yearsRangeLabel(years)}</span>
              <span className={styles.role}>{option.role} baseline</span>
            </label>
          )
        })}
      </div>
    </fieldset>
  )
}
