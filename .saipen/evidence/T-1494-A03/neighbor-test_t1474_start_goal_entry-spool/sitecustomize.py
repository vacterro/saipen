import os
import subprocess

if os.name == 'nt' and os.environ.get('SAIPEN_CANONICAL_TEST_CHILD') == '1':
    _original_init = subprocess.Popen.__init__
    def _quiet_init(self, *args, **kwargs):
        flags = int(kwargs.get('creationflags', 0))
        flags &= ~getattr(subprocess, 'CREATE_NEW_CONSOLE', 0)
        kwargs['creationflags'] = flags | getattr(subprocess, 'CREATE_NO_WINDOW', 0)
        startup = kwargs.get('startupinfo') or subprocess.STARTUPINFO()
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startup.wShowWindow = subprocess.SW_HIDE
        kwargs['startupinfo'] = startup
        return _original_init(self, *args, **kwargs)
    subprocess.Popen.__init__ = _quiet_init
