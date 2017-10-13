# This code can be put in any Python module, it does not require IPython
# itself to be running already.  It only creates the magics subclass but
# doesn't instantiate it yet.
# from __future__ import print_function
import pickle
from IPython.core.magic import (Magics, magics_class, line_magic,
                                cell_magic, line_cell_magic)

from types import ModuleType
import six
import subprocess
import uuid
import os
import time

from .util import rsync_cp
from . import fs_tracker
from . import model

# The class MUST call this class decorator at creation time


@magics_class
class StudioMagics(Magics):

    @cell_magic
    def cmagic(self, line, cell):
        "my cell magic"
        return line, cell

    @line_cell_magic
    def studio_run(self, line, cell=None):
        script_text = []
        pickleable_ns = {}

        for varname, var in six.iteritems(self.shell.user_ns):
            if not varname.startswith('__'):
                if isinstance(var, ModuleType) and \
                   var.__name__ != 'studio.magics':
                    script_text.append(
                        'import {} as {}'.format(var.__name__, varname)
                    )

                else:
                    try:
                        pickle.dumps(var)
                        pickleable_ns[varname] = var
                    except BaseException:
                        pass

        script_text.append(cell)
        script_text = '\n'.join(script_text)
        with open('run_magic.py.stub') as f:
            script_stub = f.read()

        script = script_stub.format(script=script_text)

        experiment_key = str(uuid.uuid4())
        workspace_new = fs_tracker.get_artifact_cache(
            'workspace', experiment_key)

        rsync_cp('.', workspace_new)
        with open(os.path.join(workspace_new, '_script.py'), 'w') as f:
            f.write(script)

        ns_path = fs_tracker.get_artifact_cache('_ns', experiment_key)

        with open(ns_path, 'w') as f:
            f.write(pickle.dumps(pickleable_ns))

        runner_args = line.split(' ')
        runner_args.append('--capture={}:_ns'.format(ns_path))
        runner_args.append('--force-git')
        runner_args.append('--experiment=' + experiment_key)
        p = subprocess.Popen(['studio', 'run'] +
                             runner_args +
                             ['_script.py'],
                             stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT,
                             cwd=workspace_new,
                             close_fds=True)

        with model.get_db_provider() as db:
            while True:
                experiment = db.get_experiment(experiment_key)
                if experiment is not None and \
                        experiment.status == 'finished':
                    break

                time.sleep(10)

            new_ns_path = db.get_artifact(experiment.artifacts['_ns'])

        with open(new_ns_path) as f:
            new_ns = pickle.loads(f.read())

        self.shell.user_ns.update(new_ns)
        studiorun_out, _ = p.communicate()
        print studiorun_out


ip = get_ipython()
ip.register_magics(StudioMagics)
