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
import base64

# The class MUST call this class decorator at creation time
@magics_class
class StudioMagics(Magics):

    @cell_magic
    def cmagic(self, line, cell):
        "my cell magic"
        return line, cell

    @line_cell_magic
    def studio_run(self, line, cell=None):
        print("Full access to the main IPython object:", self.shell)
        print("Variables in the user namespace:", self.shell.user_ns)

        #print('pickle.dumps of namespace is' + pickle.dumps(self.shell.user_ns))

        script_text = ['import pickle', 'import base64']

        for varname, var in six.iteritems(self.shell.user_ns):
            if not varname.startswith('__'):
                if isinstance(var, ModuleType) and \
                   var.__name__ != 'studio.magics':
                        script_text.append(
                            'import {} as {}'.format(var.__name__, varname)
                        )

                else:
                    try:
                        data = base64.b64encode(pickle.dumps(var))
                        script_text.append(
                            '{} = pickle.loads(base64.b64decode("{}"))'
                            .format(varname, data))

                    except BaseException:
                        pass

        script_text.append(cell)

        print '\n'.join(script_text)
        p = subprocess.Popen([
            'python','-c', '\n'.join(script_text)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT)

        print p.communicate()

        if cell is None:
            print("Called as line magic")
            return line
        else:
            print("Called as cell magic")
            return line, cell


ip = get_ipython()
ip.register_magics(StudioMagics)
