---
name: Protocol feature or extension proposal
about: Propose new normative behavior, a new phase, or a new extensions/ example
title: ""
labels: enhancement
assignees: ""
---

**The Litmus Test (SPEC.md)**
Answer all three -- if the answer is "no" to at least two, this is likely
out of scope for Core/RFC (though it may still fit as a project-level
`extensions/` example):
1. Does it make the transition between agents more reliable?
2. Does it make the behavior of different models more uniform?
3. Does it reduce the probability of context loss?

**Proposal**
What you want to add or change, concretely -- exact wording if you have
it, or a description precise enough to turn into wording.

**Where it belongs**
- [ ] `saipen/RFC.md` (Core or Maintenance, normative)
- [ ] A `saipen/phases/*.md` file
- [ ] A new `extensions/` example (project-attached, opt-in)
- [ ] Tooling (`bootstrap/`, `tests/`)

**Alternatives considered**
What existing mechanism this might already be covered by, and why it
isn't sufficient.
