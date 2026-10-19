# Forest of Dean planner

Dog-friendly walks, food, towns and essentials near Forest Holidays Forest of Dean (26–30 Oct 2026).

Live: https://waterdrips.github.io/forest-of-dean-trip/

- `data.json`: every place, area, tip, packing list and photo credit. Edit this, not the page.
- `index.html`: the page (list, map, Near me, "Got X hrs" filter, closing-soon and sunset warnings, weather, bookings, sharing, notes, packing). Works offline via `sw.js`, with a "Save for offline" button for every photo. Add `?now=2026-10-27T15:30` to the URL to preview the on-the-day warnings.
- `tools/`: `geo.py` (coordinates and real drive times), `photos.py` (credited Wikimedia photos), `phones.py` (numbers from venue sites), `validate.py`, `check_links.py`.
- Built from [holiday-planner-template](https://github.com/Waterdrips/holiday-planner-template).
