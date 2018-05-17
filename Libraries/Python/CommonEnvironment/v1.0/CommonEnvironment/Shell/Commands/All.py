# ----------------------------------------------------------------------
# |  
# |  All.py
# |  
# |  David Brownell <db@DavidBrownell.com>
# |      2018-05-11 07:54:08
# |  
# ----------------------------------------------------------------------
# |  
# |  Copyright David Brownell 2018.
# |  Distributed under the Boost Software License, Version 1.0.
# |  (See accompanying file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
# |  
# ----------------------------------------------------------------------
"""Contains all Commands"""

import os
import sys

from CommonEnvironment.Shell.Commands import *

# ----------------------------------------------------------------------
_script_fullpath = os.path.abspath(__file__) if "python" in sys.executable.lower() else sys.executable
_script_dir, _script_name = os.path.split(_script_fullpath)
# ----------------------------------------------------------------------

ALL_COMMANDS                                = [ Comment,
                                                Message,
                                                Call,
                                                Execute,
                                                SymbolicLink,
                                                Set,
                                                Path,
                                                Augment,
                                                AugmentPath,
                                                Exit,
                                                ExitOnError,
                                                Raw,
                                                EchoOff,
                                                CommandPrompt,
                                                Delete,
                                                Copy,
                                                Move,
                                              ]