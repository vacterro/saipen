import importlib.util, json, os, shutil, sys, tempfile, unittest

SUBJECT = os.path.join("tools", "saipen.py")  # sandbox-relative subject path

def _load_subject():
    spec = importlib.util.spec_from_file_location("saipen", SUBJECT)
    sys.path.insert(0, "tools")
    module = importlib.util.module_from_spec(spec)
    sys.modules["saipen"] = module
    spec.loader.exec_module(module)
    return module

class LazyEntrypointChain(unittest.TestCase):
    def test_mutation_chain_reaches_engine(self):
        # Materialize the one extension file the home fingerprint requires.
        ext_src = os.path.join("tools", "regression_t2089",
                               "home_extensions", "subs", "PROTOCOL.md")
        os.makedirs(os.path.join("extensions", "subs"), exist_ok=True)
        shutil.copyfile(ext_src, os.path.join("extensions", "subs", "PROTOCOL.md"))
        module = _load_subject()
        # The lazy name must be a CALLABLE global; PEP 562 module __getattr__
        # never fires for function-internal LOAD_GLOBAL, so the pre-fix
        # variant raises NameError from inside main() on a mutation route.
        self.assertTrue(callable(getattr(module, "checkpoint")))
        fix = tempfile.mkdtemp(prefix="t2089-oracle-")
        proj = os.path.join(fix, "proj")
        os.makedirs(os.path.join(proj, ".saipen"))
        with open(os.path.join(proj, ".saipen", "BOARD.md"), "w", encoding="utf-8") as fh:
            fh.write("## DOING\n- [/] T-9001 [P2] probe | verify: probe | owner: saipen-cli | claim_time: 2026-11-18T00:00:00Z\n## TODO\n## DONE\n## BLOCKED\n## PARKED\n")
        with open(os.path.join(proj, ".saipen", "LOG.md"), "w", encoding="utf-8") as fh:
            fh.write("- 01.01.26 00:00 [E-1] [agent: saipen-cli] [op: probe-00000000000000000000000000000000] RUN: fixture base event\n")
        # The engine resolves protocol docs from the installed home; the
        # sandbox is a project tree, so name the REPO's protocol home (kept
        # OUTSIDE the sandbox contract; the oracle only READS it).
        os.environ.setdefault(
            "SAIPEN_HOME",
            "C:/Users/vac34/AppData/Local/saipen/scheduled-source",
        )
        with open(os.path.join(proj, ".saipen", "STATE.md"), "w", encoding="utf-8") as fh:
            fh.write('---\nphase: BUILD\ntask: T-9001\nnext_action: "RUN: probe"\nblocker: none\n'
                     "transition_from: SCOUT\nsaipen_version: 8\nschema_version: 3\nlast_event: 1\n"
                     "style_contract: ded-069a4c52\n"
                     'saipen_home: "' + os.path.abspath(os.curdir).replace(os.sep, "/") + '"\n'
                     'agent: saipen-cli\nmode: full\nupdated: "2026-11-18T00:00:00Z"\n---\n')
        import io, contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            try:
                rc = module.main(["checkpoint", "RUN", "oracle probe",
                                  "--project-root", proj, "--json"])
            except SystemExit as exc:
                rc = exc.code
        sys.stderr.write(buf.getvalue()[:200])
        self.assertEqual(rc, 0)

if __name__ == "__main__":
    unittest.main()
