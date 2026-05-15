# Multilanguage support

Per D20, the integration ships with English + French support. Adding a new language is intentionally easy.

## Where strings live

Integration: `custom_components/morning_brief/translations/<lang>.json` (config-flow titles, options-flow labels, subentry forms, service descriptions, selector options).

Card: `src/i18n/<lang>.json` (header, alerts, verdict, weather, footer, severities, stale reasons, editor fields).

Rules (R13): every key added to one language file MUST exist in every other language file. CI validates parity.

## Adding a new language

### Step 1 -- Backend

1. Copy `translations/en.json` to `translations/<your-lang>.json`.
2. Translate each value.
3. Add the language code to `const.SUPPORTED_LANGUAGES`.
4. Run the parity check.

### Step 2 -- Frontend

1. Copy `src/i18n/en.json` to `src/i18n/<your-lang>.json`.
2. Translate.
3. Import in `src/i18n/index.ts` and add to the `MESSAGES` map.
4. Add the language code to `SUPPORTED_LANGUAGES` in `src/constants.ts`.
5. Run `npm run typecheck` + `npm run lint` + `npm run build`.

### Step 3 -- Open a PR

Both repos. Include a note about the language code (ISO 639-1) and any peculiarities of the language that affected translation choices.

## Fallback behaviour

If `hass.config.language` resolves to a code we do not ship a JSON for, the integration silently falls back to English (D20). Same for the card (G11 -- `hass.language` may also be null).

## What is NOT translated

User-defined labels (field names, category names) are stored as-is in the instance language. Changing the instance language does NOT retranslate them. The user re-edits if they want them in the new language.

The English prompt templates in `prompts/*.txt` are also not translated -- the model is told what language to reply in via a Jinja variable, but the system instructions stay in English (D20).
