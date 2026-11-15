import type { PctChangeStatus } from '../api/types'

/**
 * Three different reasons a value can be absent. They mean different things to
 * a reader, so the UI never collapses them into one placeholder and never
 * shows any of them as zero.
 *
 * - missing_measurement: the satellite record has no valid observation here.
 * - not_assessed:        a statistic that the analysis deliberately did not compute.
 * - unavailable:         a figure that cannot be shown (withheld, or not provided).
 */
export type Absence = 'missing_measurement' | 'not_assessed' | 'unavailable'

export const ABSENCE_LABEL: Record<Absence, string> = {
  missing_measurement: 'No valid measurement',
  not_assessed: 'Not assessed',
  unavailable: 'Unavailable',
}

export const ABSENCE_EXPLANATION: Record<Absence, string> = {
  missing_measurement: 'The satellite record has no valid observation for this value. It is not zero.',
  not_assessed: 'The analysis did not compute this statistic. It is not zero and not a negative result.',
  unavailable: 'This figure cannot be shown here. It is not zero.',
}

export const PCT_STATUS_REASON: Record<Exclude<PctChangeStatus, 'computed'>, string> = {
  withheld_nonpositive_baseline: 'The baseline is not above zero, so a percentage would mislead.',
  withheld_missing_data: 'Data needed for the percentage is missing.',
  withheld_no_remaining_months: 'No months remain after the coverage exclusion.',
}

export function pctStatusReason(status: PctChangeStatus): string | null {
  return status === 'computed' ? null : PCT_STATUS_REASON[status]
}
