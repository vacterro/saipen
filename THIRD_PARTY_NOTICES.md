# Third-Party Notices

SAIPEN is designed around its own protocol. This file records third-party
material that SAIPEN references, adapts, or may in future adapt, so that
attribution is never erased.

## Prime Agent (research reference)

- Project: Prime Agent
- Repository: https://github.com/PrimeIntellect-ai/prime-agent
- License: MIT
- Copyright (c) 2025 Mario Zechner
- Pinned upstream commit studied: `a18809e00ea30638584d87b3afea7285a9d7296c`
  (2026-08-07)

SAIPEN v9 is a design study of Prime Agent's resident-execution runtime
mechanics, selectively ported under SAIPEN governance. As of the v9 research
wave, NO code has been copied or adapted from Prime Agent into this
repository. The full decision record is in
`.saipen/KNOWLEDGE/PRIME_AGENT_EXTRACTION.md`, and the machine-readable
provenance map is `saipen/runtime/UPSTREAM.json`.

Any future copied or adapted unit MUST:

1. be recorded in `saipen/runtime/UPSTREAM.json` with mode
   `copied`/`modified`/`reimplemented`/`inspired`, upstream commit, upstream
   path, local path, and license;
2. preserve the MIT copyright notice in this file;
3. keep the difference from upstream documented in the v9 design so a future
   maintainer does not "fix" SAIPEN back toward upstream and reopen a
   deliberately closed hole.

Code that is merely conceptually similar and independently implemented is not
attributed to Prime Agent; copied code is never claimed as independently
authored.

## MIT License (for any future copied material)

The MIT License applies to any material copied from Prime Agent:

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
