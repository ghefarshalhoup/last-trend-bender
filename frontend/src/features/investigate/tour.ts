import { driver, type DriveStep } from 'driver.js'
import 'driver.js/dist/driver.css'
import './tour.css'

type Phase = 'choose' | 'investigate'

interface Stop {
  target: string
  title: string
  text: string
}

/** One stop per control, in reading order. Targets are `data-tour` attributes, never screen positions. */
const STOPS: Record<Phase, Stop[]> = {
  choose: [
    { target: 'map', title: 'Study areas', text: 'Choose a study area on the map. Point at a marker to see its true boundary.' },
    { target: 'period', title: 'Tested period', text: 'Choose the time interval used to test the trend. The dates are shown on each button.' },
    { target: 'compare', title: 'Compare', text: 'Optionally show the same variables for Kraków or Prague, two cities outside the war.' },
    { target: 'investigate', title: 'Investigate', text: 'Open the evidence for the place and period you chose.' },
    { target: 'elements', title: 'Four elements', text: 'Choose Air, Fire, Earth or Water to list its variables.' },
    { target: 'avatar', title: 'Your guide', text: 'The guide gives instructions here. After you investigate, press the portrait for one plain-language note per open card.' },
    { target: 'field-guide', title: 'Field guide', text: 'What each variable measures, and how to read the cards and their verdicts.' },
  ],
  investigate: [
    { target: 'variables', title: 'Variables', text: 'Pick up to three variables of the chosen element. Each opens as a card.' },
    { target: 'cards', title: 'Cards', text: 'Each card shows the monthly record, the trend test and the 2022 change. Press i to turn it over.' },
    { target: 'period', title: 'Tested period', text: 'Switch the period the trend is tested on. The dates are shown on each button.' },
    { target: 'compare', title: 'Compare', text: 'Show the same variables for Kraków or Prague beside your place.' },
    { target: 'elements', title: 'Four elements', text: 'Switch element to list other variables. Open cards stay.' },
    { target: 'avatar', title: 'Your guide', text: 'Press the portrait for one plain-language note per open card. It reports the test, never a cause.' },
    { target: 'field-guide', title: 'Field guide', text: 'What each variable measures, and how to read the cards and their verdicts.' },
  ],
}

const visible = (el: Element | null): el is HTMLElement => {
  if (!(el instanceof HTMLElement)) return false
  const r = el.getBoundingClientRect()
  return r.width > 0 && r.height > 0 && getComputedStyle(el).visibility !== 'hidden'
}

/**
 * Explains the controls on the current screen. It only highlights: it never changes a selection,
 * presses Investigate or loads data. Stops whose target is not on screen are skipped.
 */
export function startTour(phase: Phase): void {
  const steps: DriveStep[] = STOPS[phase].flatMap((s) => {
    const el = document.querySelector(`[data-tour="${s.target}"]`)
    return visible(el) ? [{ element: el, popover: { title: s.title, description: s.text } }] : []
  })
  if (!steps.length) return
  const tour = driver({
    steps,
    showProgress: true,
    progressText: '{{current}} of {{total}}',
    nextBtnText: 'Next',
    prevBtnText: 'Back',
    doneBtnText: 'Close',
    allowClose: true,
    allowKeyboardControl: true,
    overlayColor: '#2b2117',
    overlayOpacity: 0.45,
    stagePadding: 6,
    stageRadius: 10,
    popoverClass: 'trend-tour',
  })
  tour.drive()
}
