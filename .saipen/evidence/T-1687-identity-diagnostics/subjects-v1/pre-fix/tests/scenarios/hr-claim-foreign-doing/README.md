expect: pass

Hostile-regression P0: a foreign-owned ## DOING with observer STATE.task: none
is VALID multi-agent state -- the observer must not be forced to mirror a
stranger's claim in STATE. The ONE claim_status classifier lets route_next and
fast_check permit this shape (it routes non-mutating) while still failing closed
on half/invalid claims.
