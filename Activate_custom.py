# ----------------------------------------------------------------------
# |  
# |  Activate_custom.py
# |  
# |  David Brownell <db@DavidBrownell.com>
# |      2018-05-07 08:59:57
# |  
# ----------------------------------------------------------------------
# |  
# |  Copyright David Brownell 2018.
# |  Distributed under the Boost Software License, Version 1.0.
# |  (See accompanying file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
# |  
# ----------------------------------------------------------------------
"""Functionality to further enhance Common_Enviromnet activation"""

import os
import sys

from collections import OrderedDict

import six

# ----------------------------------------------------------------------
_script_fullpath = os.path.abspath(__file__) if "python" in sys.executable.lower() else sys.executable
_script_dir, _script_name = os.path.split(_script_fullpath)
# ----------------------------------------------------------------------

sys.path.insert(0, os.getenv("DEVELOPMENT_ENVIRONMENT_FUNDAMENTAL"))
from RepositoryBootstrap.Impl import CommonEnvironmentImports
del sys.path[0]

# ----------------------------------------------------------------------
def CustomScriptExtractors(shell):
    """Returns script parsers used during activation."""

    # ----------------------------------------------------------------------
    def PythonWrapper(script_filename):
        if os.path.basename(script_filename) == "__init__.py":
            return

        return shell.Commands.Execute('python "{}" {}'.format( script_filename,
                                                                                                 shell.AllArgumentsScriptVariable,
                                                                                               ))

    # ----------------------------------------------------------------------
    def PythonDocs(script_filename):
        co = compile(open(script_filename, 'rb').read(), script_filename, "exec")

        if co and co.co_consts and isinstance(co.co_consts[0], six.string_types) and co.co_consts[0][0] != '_':
            return CommonEnvironmentImports.StringHelpers.Wrap(co.co_consts[0], 100)

    # ----------------------------------------------------------------------
    def PowershellScriptWrapper(script_filename):
        return shell.Commands.Execute('powershell -executionpolicy unrestricted "{}" {}'.format(script_filename, shell.AllArgumentsScriptVariable))

    # ----------------------------------------------------------------------
    def EnvironmentScriptWrapper(script_filename):
        return shell.Commands.Execute('"{}" {}'.format(script_filename, shell.AllArgumentsScriptVariable))

    # ----------------------------------------------------------------------

    return OrderedDict([ ( ".py", ( PythonWrapper, PythonDocs ) ),
                         ( ".ps1", PowershellScriptWrapper ),
                         ( shell.ScriptExtension, EnvironmentScriptWrapper ),
                       ])
