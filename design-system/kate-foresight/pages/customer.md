# Customer app (overrides MASTER)
- Responsive, no phone frame. Desktop >= 1024px: two columns (main 2/3: priority moment + allocation; side 1/3: upcoming preview + plans summary). Mobile: single column, full width, bottom nav optional.
- Sections: Overview, Timeline, My plans, My data (top nav on desktop, bottom nav on mobile; `aria-current="page"`).
- One priority moment first: title (h2), date or amount, one-sentence why-now, one primary action, secondary "Why?" link. Other moments in a compact list below ("Also coming up").
- Why: side panel on desktop (right, 420px), full-screen dialog on mobile; focus trapped, Esc closes, focus returns to the opener; plain reasons first, "Technical details" disclosure second.
- Allocation chart: one horizontal stacked bar with direct labels and a legend table under it; recomputed from the API after every goal change.
