# Decision for Pax: next Murder Board task

The latest pull added `CODEX_HANDOFF.md`. Its first work item is a live public-record census for Door 2. The repository rules also say to use fictional cases only and include no real people's names, real cases, or scraped real posts as evidence.

Which task should come next?

1. Build a Records prototype using only the bundled fictional cases, with no outside lookups.
2. Defer Door 2 and work on score discipline using the fictional cases.

The choice matters because live public-record searches can return information about real people, which conflicts with the repository's current scope.

## Pax's decision (2026-11-21)

**Option 1, scoped.** Build the Records prototype now, on the
bundled fictional cases, with no outside lookups. Score discipline
is second, after the prototype.

How the scope conflict resolves:

- The fictional-only rule binds case material and demos: no real
  people as case subjects, no real cases, no scraped real posts
  presented as evidence. That rule stands, unchanged.
- The prototype builds the census LOGIC against fictional
  fixtures: the source interface, the SOURCED / UNVERIFIED
  labeling, name-collision handling (shown, never merged), and
  the starter-file output. Live source adapters are separate
  slots, marked UNIMPLEMENTED, and are not wired to anything.
- Switching live lookups on is not an agent decision. It happens
  when there is a real user (a family, a nonprofit, a journalist,
  a detective) who supplies a name and asks, on Del's word. The
  tool's real-world inputs come from its users; its development
  and its demos stay fictional.

Prototype acceptance bar: given the fictional victim's name from
either bundled case, Records produces a starter file where every
item carries SOURCED or UNVERIFIED, at least one planted name
collision is shown unmerged, and no finding cites anything but a
fixture. Then stop and report; score discipline is next in line.
