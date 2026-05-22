---
name: typescript-strict-mode
description: Generate TypeScript with strict mode + explicit types everywhere
source: github:ts-experts/skills
score: 0.78
---

# Strict TypeScript

When writing TypeScript, always:

- `tsconfig.json` includes `"strict": true` (covers strictNullChecks, noImplicitAny, etc.)
- Explicit return types on all exported functions
- No `any`. Use `unknown` + narrowing instead.
- No `as` casts unless absolutely necessary (prefer type guards)
- Use `readonly` for arrays and objects that shouldn't mutate

Example:

```typescript
function process(input: unknown): readonly string[] {
  if (!Array.isArray(input)) {
    throw new TypeError('expected array');
  }
  return input.filter((x): x is string => typeof x === 'string');
}
```
