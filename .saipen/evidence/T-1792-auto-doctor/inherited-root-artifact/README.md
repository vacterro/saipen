# Preserved inherited root artifact

The untracked root file `{receipt.get('timestamp_utc')})` was empty. A real
T-1412 validator fixture failed because the runtime home checks its root file
set even when validating a consumer project (the separate T-1749 defect).

Its exact zero bytes are preserved as `root-fragment.txt`; SHA256:
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
No content was deleted. Restore by moving this file to the original root name
above. Its writer is unknown; the filename alone does not attribute a host.

Evidence: E-15698 and the failed
`tools.test_t1412_conformance_truth.ValidateSurfaceTests.test_validate_refreshes_stale_fail_to_current_pass`.
This housekeeping removes the incidental fixture obstruction; T-1749 still
owns the validator's incorrect treatment of a consumer's runtime home.
