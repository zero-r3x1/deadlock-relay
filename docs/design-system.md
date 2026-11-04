# Deadlock Relay — UI/UX Pro Max redesign

Native Qt Widgets / Windows desktop. The UI/UX Pro Max skill was consulted using `network monitoring dashboard dark --design-system --density 8` and `dark mode contrast --domain ux`.

The initial gaming query returned a 3D product showcase, unsuitable for this utility. The narrower network query returned dark operational surfaces, slate colors, green actions, and status indicators. Those parts fit this application. Landing-page CTAs and glass effects were not adopted. Qt is not one of the skill's supported implementation stacks; Qt styling is implemented directly.

- Background: #0f172a; panels: #182235; fields: #101a2b.
- Foreground: #f1f5f9; secondary: #aab9cd; action: #86efac with dark text.
- Warning: #fcd68a. Status always has text, not color alone.
- Segoe UI with Cyrillic, 14px body, 13px supporting text, 28px page heading.
- 8px spacing rhythm, 16px panel corners, 10px controls. No blur or continuous animation.
- One dominant relay table. Compact preset selection above, persistent action bar below.
- Pending selection and actual firewall state are separate. No invented live telemetry.
- Keyboard focus: visible green outline; navigation and presets expose checked state.
- Native desktop layout tested at 1080×900 and 1320×930. At narrow widths presets use two columns.

Verification uses native Qt screenshots and the existing UI tests, not a browser.
