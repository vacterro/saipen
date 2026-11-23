# Bounded cleanup fixture — T-1831

WHAT CHANGED: `RunFamilyLeavesNothingTests.run_small` now supplies a private
source containing the unchanged real hermetic-environment test module, current
runtime package, and explicit read-only Git-object payload. It no longer copies
the operator's entire live repository. Every original assertion is retained.

WHY IT WAS EXPENSIVE: each of its two three-test invocations copied ~1.32 GiB of
live state and paid its Windows cleanup cost. Instrumentation observed copies
of 50.437 / 52.813 s and cleanup of 12.485 / 14.75 s. Test subprocess execution
was only 0.203 / 0.219 s. The cleanup contract never required that live data.

MEASURED SAVINGS: same machine, same Python, same real Windows acceptance module,
same 21 controls: 136.656 s -> 6.578 s, about 20.8x / 95.2% lower module wall
time. The intended fixture input changes; test assertions and the embedded
three-test probe do not. This is not an identical-byte copy benchmark and is
not presented as measured savings for the full canonical family or operator
implementation time. Raw records: `../T-1829-cost-collapse/before-cleanup.json`
and `../T-1829-cost-collapse/after-cleanup.json`.

REGRESSION EVIDENCE: the independent new test rejects the original live-root
input before a costly run, checks private source location, exact unchanged
probe bytes and required readonly payload, then passes after the fix. The real
21-test module passes before and after, including unreported leak rejection,
live/foreign-owner protection, readonly deletion and Windows held directories.

REMAINING RISK: this removes unnecessary fixture data only. Other production
and test sandboxes still copy their required durable state. Linux execution
is not claimed on this Windows host. Full stable-generation acceptance is owed.

NEXT ACTION: add compatible-environment evidence identity and canonical
single-flight coordination using the existing OS FileWriterLock.
