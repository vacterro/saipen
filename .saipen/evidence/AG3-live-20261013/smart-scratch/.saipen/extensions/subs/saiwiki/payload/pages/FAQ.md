# FAQ

**Q: Will it delete my files?**
A: Only known junk patterns inside the configured roots and system target
folders. The CLI deletes only with `--delete`; the GUI asks first. Everything
else is refused by the safety layers (see Safety page).

**Q: Why is nothing deleted when I run the CLI?**
A: The CLI is dry-run by default. Add `--delete`.

**Q: The exe created `cleaner_config.json` in a temp folder once.**
A: Older versions used the unpack dir; since v2.2.0 config and logs live next
to the exe (`BASE_DIR`). Re-run once to refresh.

**Q: A portable root I configured is never cleaned.**
A: Roots are only swept when they exist at run time (a disconnected drive is
skipped silently). Also check the log for "Portable root rejected" —
nested, duplicate, or protected paths are refused.

**Q: Why was my custom rule dropped?**
A: The rule path must be absolute and not protected. Check the run log for
"Custom rule dropped" warnings (invalid or blacklisted path).

**Q: Can I schedule it?**
A: Yes: `--install-task --time HH:MM` installs a daily silent full-clean task
with highest privileges.

**Q: Does it need admin?**
A: System targets benefit from admin (Windows Update Cache, Recycle Bin);
portable roots on non-system drives work without admin.

**Q: Where are the logs?**
A: `logs\clean_YYYYMMDD_HHMMSS.log` next to the script/exe.

**Q: How do I preview what would be cleaned?**
A: `python _SMART_VAC_CLEANER.py --cli --all` (dry-run preview), or
`--status` for sizes per target.

**Q: Can I clean on a schedule without a task?**
A: Yes — GUI has `auto_clean_interval_hours` in config (0 = off).

**Q: How do I change the GUI language?**
A: Set `"lang": "ru"`, `"et"`, or `"ded"` in `cleaner_config.json` and restart the GUI.
Missing strings fall back to English.
