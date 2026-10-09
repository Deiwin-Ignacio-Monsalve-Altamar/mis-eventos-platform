# Frontend visual direction

## Editorial Ops / Studio Green

This document is the visual source of truth for upcoming frontend work. Apply
these shared decisions consistently while preserving ticket-specific scope.

### Palette

- Main background: `#F7F8F5` (warm ivory).
- Surfaces: `#FFFFFF`.
- Primary text: `#202720` (charcoal).
- Accent: `#B7F36B` (lime green).
- Supporting green: `#E8EDE4`.
- Muted text and borders should stay neutral and maintain readable contrast.

### Type and layout

Use editorial-feeling typography with a clear heading hierarchy, generous
spacing, and restrained decoration. Prefer a refined serif treatment for large
headings paired with the system sans-serif stack for controls and body copy.

Forms should use visible labels, clear focus states, consistent buttons, and
responsive layouts. Keep related screens visually connected and avoid generic
template decoration. Feedback must remain accessible and easy to scan.

### Product application

Authentication screens establish this direction for SCRUM-15. Shared tokens
belong in `frontend/src/index.css`; reusable component styling belongs in
`frontend/src/App.css`. Later tickets can extend the system without redesigning
event screens outside their scope.

### Authentication photography

The authentication story panel uses the Unsplash photo “A crowd of people at a
concert with confetti in the air” by Lachy Spratt, provided under the Unsplash
License: <https://unsplash.com/photos/a-crowd-of-people-at-a-concert-with-confetti-in-the-air-2r5NvsRFd2s>.
The asset is loaded from the Unsplash image CDN. If it cannot load, the panel
retains its charcoal background and readable foreground copy.

Authentication routes use a two-panel desktop layout. The registration page
keeps the story panel at the viewport height and scrolls the form column
independently when needed; narrow layouts return to normal document scrolling.
