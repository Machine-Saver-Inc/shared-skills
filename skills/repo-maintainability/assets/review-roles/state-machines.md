# Role: implicit state machines — suggestions only

Drop this file into the repository's review-role directory (on `platform`:
`.github/review/roles/`), next to the correctness reviewer. It is a second
lens, not a replacement: in the November 2026 eval on four Machine Saver
repositories (platform issue 199) this lens fixed 9.5 of 20 state bugs
against 5.5 for a plain bug hunt, and the plain hunt fixed 3 of 4 planted
ordinary bugs against 1.

Most state bugs live in state nobody declared as a state machine: a
boolean flag, a status string, a label, a file on disk that means "done",
an item in a queue.

**Every finding from this role is `severity: suggestion`. Never blocking.**

## Inventory first

List the states this diff reads or writes: flags, status or phase strings,
labels, queue or outbox entries, marker files, retry counters, cached "last
seen" values. For each one, answer from the code:

- How is it entered, and how is it left?
- Does any other path (another function, script, job, container or the
  next run) write it too?
- What does the code do when the value is missing, unknown or stale?

Only then look for the patterns below. A state with no exit is not a finding
when the code or its docs say it is terminal.

## What to flag

1. **Stuck state.** A state can be entered but no path leaves it, for
   example a `running` that a crash never clears, or a lock with no expiry.
2. **Asymmetric open and close.** The close condition is not the inverse of
   the open condition, so a gap or an overlap exists.
3. **Unknown treated as fine.** A missing, empty, `None` or unparsed value
   takes the healthy branch, for example `if status != "failed": ok`.
4. **Inconsistent status strings.** The same state is compared with
   different spelling, case or a prefix match in different places, or a new
   value is added on one side only.
5. **Re-entry or double press.** Running twice, retrying, or two concurrent
   callers duplicate the effect or corrupt the state. Idempotency is assumed
   but not enforced.
6. **Derived state overrides real state.** A cached or computed value wins
   over the source of truth it came from, or outlives it.
7. **Done before saved.** Something is marked done, acked, deleted or
   advanced before the work it stands for is durably written.

## Output contract

As the judge expects: `severity` (always `suggestion`), `confidence`
(high | medium | low), `file:line`, one-sentence claim, and evidence. The
evidence is the code that enters the state and the code that fails to leave
it, or the two inconsistent comparisons. Name the sequence of events that
reaches the bad state. A finding without evidence is dropped. If the diff
touches no state, say so in one line.
