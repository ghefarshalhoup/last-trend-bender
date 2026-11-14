import { useId } from 'react'
import type { AtlasSelection, ControlOption, LayerActions, LayerControls } from './layers/types'
import styles from './LayerControlsBar.module.css'

interface Props {
  controls: LayerControls
  selection: AtlasSelection
  actions: LayerActions
}

function OptionText({ option }: { option: ControlOption }) {
  return (
    <>
      <span className={styles.name}>{option.label}</span>
      {option.detail || option.warning ? (
        <span className={styles.detail}>
          {option.detail}
          {option.warning ? (
            <span className={styles.warn}>
              {' '}
              <span aria-hidden="true">▲</span>
              <span className="sr-only"> {option.warning}</span>
            </span>
          ) : null}
        </span>
      ) : null}
    </>
  )
}

/** Time and comparison controls. Generic: it renders whichever groups the active layer supports. */
export function LayerControlsBar({ controls, selection, actions }: Props) {
  const radioName = useId()
  const { windows, periods, comparisons } = controls
  if (!windows && !periods && !comparisons) return null
  return (
    <div className={styles.bar} data-testid="layer-controls">
      {windows ? (
        <div role="group" aria-label={windows.label} className={styles.group}>
          <span className={styles.groupLabel}>{windows.label}</span>
          <div className={styles.options}>
            {windows.options.map((option) => (
              <button
                key={option.id}
                type="button"
                className={styles.option}
                aria-pressed={selection.window === option.id}
                onClick={() => actions.selectWindow(option.id)}
                data-testid={`window-${option.id}`}
              >
                <OptionText option={option} />
              </button>
            ))}
          </div>
        </div>
      ) : null}
      {periods ? (
        <div role="group" aria-label={periods.label} className={styles.group}>
          <span className={styles.groupLabel}>{periods.label}</span>
          <div className={styles.options}>
            {periods.wholePeriodLabel ? (
              <button type="button" className={styles.option} aria-pressed={selection.period === null} onClick={() => actions.selectPeriod(null)} data-testid="period-all">
                <span className={styles.name}>{periods.wholePeriodLabel}</span>
                <span className={styles.detail}>whole season</span>
              </button>
            ) : null}
            {periods.options.map((option) => (
              <button
                key={option.id}
                type="button"
                className={styles.option}
                aria-pressed={selection.period === option.id}
                data-warning={Boolean(option.warning)}
                onClick={() => actions.selectPeriod(option.id)}
                data-testid={`period-${option.id}`}
              >
                <OptionText option={option} />
              </button>
            ))}
          </div>
        </div>
      ) : null}
      {comparisons ? (
        <fieldset className={styles.group}>
          <legend className={styles.groupLabel}>{comparisons.label}</legend>
          <div className={styles.options}>
            {comparisons.options.map((option) => (
              <label key={option.id} className={styles.option} data-checked={selection.comparison === option.id} data-testid={`comparison-${option.id}`}>
                <input
                  type="radio"
                  className="sr-only"
                  name={radioName}
                  checked={selection.comparison === option.id}
                  onChange={() => actions.selectComparison(option.id)}
                />
                <OptionText option={option} />
              </label>
            ))}
          </div>
        </fieldset>
      ) : null}
    </div>
  )
}
