# Frontend

Single file (`index.html`), no build step at runtime. Styles come from `tailwind.css`, built from the classes used in `index.html`, so the demo works without internet.

Rebuild after adding new Tailwind classes:

```bash
npx tailwindcss@3.4.19 -i <(printf '@tailwind base;\n@tailwind components;\n@tailwind utilities;\n') --content index.html -o tailwind.css --minify
```
