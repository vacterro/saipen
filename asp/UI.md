# asp UI вЂ” Dark Golden Win95 (mandatory for all UI work)

Applies to every interface: web, app, panel, dialog, HTML report, TUI.
This file is self-sufficient. (Author's machine keeps an extended spec at
`_ref\vintage\SKILL.md` вЂ” read it only if it exists; never required.)

## Iron laws

1. **Verdana, non-antialiased, everywhere, `!important`.** No subpixel
   smoothing. Sizes only 10/11/12/14/16px.
2. **Zero:** border-radius, box-shadow, gradients, blur, transparency
   effects, animations, transitions. All state changes instant.
3. **Depth = 2px bevels only.** Raised: light top-left, dark bottom-right.
   Sunken (pressed, inputs): inverted.
4. **Ultra-compact:** fits 640Г—480. Padding 1-2px tight, 4px groups, 8px
   sections, 12-16px window margins only. Elements share borders.
5. **Colors from tokens only.** No rogue hex.

## Tokens + base CSS (paste into every asp UI)

```css
:root {
  --background:#1A0F05; --backgroundSoft:#1E1408; --surface:#2A1C0A;
  --surfaceRaised:#362812; --surfaceAlt:#3A2A15;
  --borderDark:#0E0803; --borderHighlight:#C0A060; --borderMuted:#4A3820;
  --textPrimary:#D4B87A; --textSecondary:#B09558; --textMuted:#7A6838;
  --accentTeal:#008080; --accentTealDeep:#004C4C;
  --success:#4A7A20; --warning:#7A7A20; --danger:#7A2020;
  --selection:#362812; --compareBack:#0F0A04;
}
* {
  font-family: Verdana, "Microsoft Sans Serif", sans-serif !important;
  -webkit-font-smoothing: none !important;
  -moz-osx-font-smoothing: unset !important;
  font-smooth: never !important;
  text-rendering: optimizeSpeed !important;
  border-radius: 0 !important;
  transition: none !important; animation: none !important;
  box-shadow: none !important; text-shadow: none !important;
  box-sizing: border-box; margin: 0;
}
body { background: var(--background); color: var(--textPrimary);
       font-size: 12px; }
.raised, button { border: 2px solid;
  border-color: var(--borderHighlight) var(--borderDark)
                var(--borderDark) var(--borderHighlight);
  background: var(--surfaceRaised); }
.sunken, input, select, textarea { border: 2px solid;
  border-color: var(--borderDark) var(--borderHighlight)
                var(--borderHighlight) var(--borderDark);
  background: var(--surface); }
button { padding: 2px 4px; min-width: 24px; min-height: 20px;
  color: var(--textPrimary); cursor: pointer; }
button:hover { background: var(--surfaceAlt); }
button:active { border-color: var(--borderDark) var(--borderHighlight)
  var(--borderHighlight) var(--borderDark); background: var(--surface);
  transform: translate(1px,1px); }
button:focus-visible { outline: 1px dotted var(--textPrimary);
  outline-offset: -4px; }
input, select, textarea { height: 20px; padding: 1px 3px;
  background: var(--compareBack); color: var(--textPrimary); }
```

Non-web UI (Qt, WinForms, TUI, C4D, AHK): map same tokens вЂ” Verdana 9-12pt,
ClearType/antialiasing OFF where the API allows, flat colors + light/dark 2px
edge pairs, no animation timers.

## Component rules

- Buttons pressed = sunken + 1px label shift. Loading = static `...`, never
  a spinner.
- Inputs always sunken; focus swaps highlight to `--textPrimary`; visible
  label mandatory вЂ” placeholder is never the label.
- Tabs: active sunken, inactive raised, 0 gap between.
- Title bars 20px `--surface`; dialog bodies `--surfaceRaised`, в‰¤2px padding.
- Tables: rows 16-18px, headers raised, selected row `--selection` sunken.
- Logs/data values on `--compareBack`.
- Errors stay loud `--danger`, specific message + fix instruction, never
  "Something went wrong". Buttons say verb+object ("Save file", never "OK").

## Accessibility floor (compactness never excuses)

WCAG AA contrast; visible focus (1px dotted) on every control; full keyboard
reach; targets в‰Ґ24px primary / 16px secondary.

## QA before DONE

No rounded corner, no animation frame, Verdana renders non-aliased, fits
640Г—480 without horizontal scroll, every hex traces to a token. LOG line:
`RUN: UI check <component> -> PASS/FAIL <detail>`.
