# Notes for Claude

- **Dates are Denver time.** The container clock is UTC, which runs 6–7 hours
  ahead of Denver, so after ~6pm MT the system date is already "tomorrow."
  Before saying what today is (which /40 day is up, what posts tonight,
  "posted late"), run `TZ=America/Denver date` and use that.
  The site itself already counts days in America/Denver (`40/index.html`).
