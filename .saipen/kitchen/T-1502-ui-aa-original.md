# T-1502: the operator's original UI.md antialiasing strengthening (pre-compaction)

Uncommitted working-tree text of saipen/UI.md as found on 2026-09-24 04:07,
before T-1502 compacted it to fit the 300 KiB human_markdown_total budget
(SRC-115). Kept verbatim so the compaction can be reviewed or reverted.

## Iron law 1 addition

   **Antialiasing is OFF, always, on every machine -- no exceptions.** Blur is
   antialiasing, and antialiasing is a FAIL. Every glyph pixel is exactly the
   text colour or exactly the background colour: no grey, no coloured
   (ClearType) fringe, no half-pixel edge. This holds **no matter what the
   user's computer is set to**: ClearType on, "Smooth edges of screen fonts"
   on, a browser or driver forcing smoothing, any display scale. The user's
   system preference does not apply to a saipen interface; the interface
   overrides it for its own text, and never changes the system setting
   itself. "It is crisp on my machine" proves nothing -- a clean machine with
   every smoothing option on is the case that counts. A stylesheet that only
   names Verdana does not satisfy this law: most toolkits cannot switch
   smoothing off from a stylesheet, and their default follows the system.
   The switch lives in the renderer's per-font setting (see *Non-antialiased
   text, on any machine* under Typography rules) and the proof is a pixel
   check, never the code's own claim.

## Typography section

### Non-antialiased text, on any machine

Iron law 1 is the rule most often shipped broken: every modern toolkit
follows the system smoothing setting by default, and a stylesheet that names
the font looks like it handled fonts. The only reliable place is the
renderer's **per-font** switch, because it is the one thing the system
setting cannot override. Set it in code, at startup, before the first widget
or dialog exists:

- **Qt (PyQt / PySide):** QSS has no antialiasing property. Application font
  `QFont("Verdana")`, `setPixelSize(11)`,
  `setStyleStrategy(QFont.StyleStrategy.NoAntialias)`, `app.setFont(font)`.
  QSS then sets family and size only; it keeps the strategy. Include the
  early-exit dialogs ("already running", dependency errors) -- they are
  screens too. Works with both the GDI and DirectWrite engines.
- **WinForms / GDI:** every font created with `NONANTIALIASED_QUALITY`
  (LOGFONT `lfQuality`), and `Graphics.TextRenderingHint =
  TextRenderingHint.SingleBitPerPixelGridFit` in every custom paint path.
  Never `ClearTypeGridFit`, `AntiAlias` or `SystemDefault` -- the last one
  hands the decision back to the user's setting.
- **Web / HTML:** the base CSS above, `!important`, on `*`. CSS alone is not
  enough on Windows browsers, which follow ClearType and ignore
  `font-smoothing`. For a guarantee, serve a pixel-grid webfont (Verdana's
  hinted bitmap at the exact size, glyph edges on whole pixels) at its native
  pixel size, so there is no partial pixel left to smooth.
- **Anything else:** find the renderer's own per-font antialias switch and
  turn it off. If the platform genuinely has none, tell the user so in plain
  words instead of shipping smoothed text and calling it done.

**Scaling must not re-blur it.** Crisp glyphs are lost again the moment the
window is stretched as a bitmap:

- Desktop apps declare DPI awareness (Per-Monitor V2). A DPI-unaware window
  is bitmap-scaled by Windows at 125/150% and turns to mush whatever the font
  settings say.
- Scale only by whole numbers (100%, 200%). At fractional scales round to a
  whole factor (Qt: `HighDpiScaleFactorRoundingPolicy.Round`) rather than
  interpolate. Icons and images scale nearest-neighbour
  (`image-rendering: pixelated`), never smoothed.
- Borders and bevels stay whole pixels; a 2px bevel that renders as 2.5 is a
  blur too.

**Proof, not belief.** Test on the worst case: system smoothing ON
(ClearType + "Smooth edges of screen fonts"). Render the real screen
(offscreen is fine, but with the real platform font engine -- an offscreen
engine with no fonts proves nothing) and count the distinct colours. Aliased
text adds no colours beyond the tokens in use: a Golden Default screen lands
at roughly twenty. Smoothed text adds hundreds of in-between shades. A
regression test must pin the per-font setting (e.g. every widget's font
carries `NoAntialias`) and must fail when the setting is removed.

## Checklist lines (replacing "- Verdana renders non-antialiased.")

- Verdana renders non-antialiased: a zoomed screenshot shows no grey or
  coloured fringe on any glyph, and the distinct-colour count stays at the
  token count (see *Non-antialiased text, on any machine*), tested with
  system smoothing (ClearType) ON.
- No platform default leaks through: scrollbar tracks, focus rectangles,
  checker/dither patterns and stock toolkit colours (pure yellow, red,
  white) are all token-painted or gone.
