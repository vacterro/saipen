"""Concrete analysis backends, kept OUT of the neutral engine package.

`saipen_engine/` promises producer neutrality: no module there may branch on a
producer name, and `test_audit_dogfood` enforces it (T-1947). A deployment's
actual analysis backend is the opposite kind of code -- it is named after the
producer it talks to and knows that producer's CLI, disk layout and statuses --
so it lives here and reaches the engine only through the name-free
`saipen_engine.backend_protocol.CampaignBackend` interface.

Nothing in this package is imported by the engine. The dependency points one
way: `tools/saipen.py` constructs a backend and hands it to the campaign
controller.
"""
