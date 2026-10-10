# Frontend visual system

## Direction

Mis Eventos pairs a calm, light SaaS foundation with a distinct event identity.
Electric purple carries primary actions and navigation. Pink, sunny yellow,
lavender, and turquoise are supporting accents, used selectively so forms,
event management, and registration information remain easy to scan. The
catalogue and event detail can be more expressive; authentication and management
views should favor clear hierarchy and restrained decoration.

## Tokens

Global tokens live in `frontend/src/index.css`:

| Token | Value | Use |
| --- | --- | --- |
| `--background-ivory` | `#F7F8FF` | Main page background |
| `--surface` | `#FFFFFF` | Cards and form surfaces |
| `--ink` | `#20204A` | Primary text |
| `--muted` | `#667085` | Secondary text |
| `--brand` | `#6D3BFF` | Main action and focus |
| `--accent-pink` | `#F52D91` | Decorative emphasis and error contrast |
| `--accent-pink-ink` | `#B51669` | Small pink text accents with stronger contrast |
| `--accent-yellow` | `#FFE16B` | Festive highlight |
| `--accent-lavender` | `#F0E9FF` | Soft panels and selected states |
| `--accent-turquoise` | `#21C997` | Positive availability and registration |

The same file defines semantic border, shadow, corner-radius, and motion tokens.
Keep card elevation subtle, reserve the event hero and brand artwork for the
strongest color treatment, and use solid purple for primary actions. Avoid
adding a separate end-of-file override for a component when its shared rule can
be refined in place.
Do not encode availability or registration state with color alone; always pair
the color with visible text.

## Typography and layout

Use the system sans-serif stack for controls and body copy. Large editorial
headings retain the existing Georgia serif treatment. Keep line lengths
comfortable, use generous section spacing, and avoid narrowing form controls.
The shared layout uses responsive `min()`, `max()`, and `clamp()` sizing.

## Shared components

Reusable styles are in `frontend/src/App.css` and apply across the catalogue,
event detail, create-event form, authentication, profile, and registration list:

- Primary and secondary buttons have hover, focus, and disabled states.
- Inputs, text areas, and selects share borders, radii, and visible focus rings.
- Feedback components use polite live regions for loading, empty, success, and
  error states.
- Event cards preserve the backend's event fields and use abstract brand artwork
  when the API has no event image.
- Session availability uses a star marker plus text. “Available”, “Full”,
  pending, and unknown labels only reflect the capacity endpoint's values or
  request state. The interface does not estimate “last seats”.
- Profile registration labels distinguish active and cancelled records.

Avoid adding presentation-only data or deriving availability from an event's
overall capacity; the public event API does not expose event occupancy.

## Motion and accessibility

Cards and controls use short transitions without layout-changing animations.
Global focus-visible rings remain apparent against the light surfaces. Icons
that are purely decorative are hidden from assistive technology; controls have
text labels, and feedback retains live-region semantics. Honor
`prefers-reduced-motion` by removing nonessential transitions and animations.

## Responsive behavior

The stylesheet adapts the catalogue and detail layouts at 760 px, then adjusts
navigation, cards, forms, profile registrations, and session rows at 520 px.
Authentication layouts use their existing 760 px and 640 px breakpoints. Check
at approximately 375 px, 768 px, and 1280 px when browser tooling is available;
automated CSS build checks do not replace visual viewport inspection.

Management and authentication screens use the shared form controls and solid
button variants rather than decorative gradients. Focus rings remain visible;
hover effects are short and do not change layout, while reduced-motion
preferences disable nonessential movement.

## Testing convention

Frontend tests use Node's built-in test runner. API tests stub `globalThis.fetch`
and restore it after each test. Component smoke tests use React server rendering
through the existing Vite SSR harness; they do not call the backend. Keep tests
independent of Docker, PostgreSQL, network availability, and persistent data.
There is no DOM interaction or browser viewport test harness configured today.

## Authentication imagery

The authentication story panel retains the existing Unsplash photo “A crowd of
people at a concert with confetti in the air” by Lachy Spratt, provided under
the Unsplash License:
<https://unsplash.com/photos/a-crowd-of-people-at-a-concert-with-confetti-in-the-air-2r5NvsRFd2s>.
If it cannot load, the colored panel and its readable copy remain visible.
