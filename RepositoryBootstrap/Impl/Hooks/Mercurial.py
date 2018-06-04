# ----------------------------------------------------------------------
# |  
# |  Mercurial.py
# |  
# |  David Brownell <db@DavidBrownell.com>
# |      2018-05-04 13:37:56
# |  
# ----------------------------------------------------------------------
# |  
# |  Copyright David Brownell 2018.
# |  Distributed under the Boost Software License, Version 1.0.
# |  (See accompanying file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
# |  
# ----------------------------------------------------------------------
"""Hook functionality for Mercurial"""

import datetime
import json
import os
import sys
import textwrap
import time

# ----------------------------------------------------------------------
_script_fullpath = os.path.abspath(__file__) if "python" in sys.executable.lower() else sys.executable
_script_dir, _script_name = os.path.split(_script_fullpath)
# ----------------------------------------------------------------------

try:
    import mercurial 

    mercurial.demandimport.disable()
except:
    pass

sys.path.insert(0, os.path.dirname(__file__))
import HookImpl
sys.path.pop(0)

# ----------------------------------------------------------------------
# |  
# |  Public Methods
# |  
# ----------------------------------------------------------------------
def PreTxnCommit(ui, repo, node, parent1, parent2, *args, **kwargs):
    """Called prior to a commit being finalized"""

    is_debug = _IsDebug(ui)

    if is_debug:
        ui.write(textwrap.dedent(
            """\
            # ----------------------------------------------------------------------
            PreTxnCommit

            Repo root:                      {}
            node:                           {}
            parent 1:                       {}
            parent 2:                       {}
            args:                           {}
            kwargs:                         {}

            # ----------------------------------------------------------------------
            """).format( repo.root, 
                         node,
                         parent1,
                         parent2,
                         args,
                         kwargs,
                       ))

    return HookImpl.Invoke( _GetRepoRoot(),
                            ui,
                            "Commit",
                            _GetChangeInfo(repo, repo[node]),
                            is_debug,
                          )

# ----------------------------------------------------------------------
def PreOutgoing(ui, repo, source, *args, **kwargs):
    """Called prior to the beginning of a push"""

    # Only process pushes
    if source != "push":
        return 0

    is_debug = _IsDebug(ui)

    if is_debug:
        ui.write(textwrap.dedent(
            """\
            # ----------------------------------------------------------------------
            PreOutgoing

            Repo root:                      {}
            args:                           {}
            kwargs:                         {}

            # ----------------------------------------------------------------------
            """).format( repo.root,
                         args,
                         kwargs,
                       ))

    data = {}

    if "url" in kwargs:
        data["url"] = kwargs["url"]

    return HookImpl.Invoke( _GetRepoRoot(),
                            ui,
                            "Push",
                            data,
                            is_debug,
                          )

# ----------------------------------------------------------------------
def PreTxnChangeGroup(ui, repo, source, node, node_last=None, *args, **kwargs):
    """Called after a pull has been downloaded but before it has been applied locally"""

    if source != "serve":
        return 0

    is_debug = _IsDebug(ui)

    if is_debug:
        ui.write(textwrap.dedent(
            """\
            # ----------------------------------------------------------------------
            PreTxnChangeGroup

            Repo root:                      {}
            node:                           {}
            node_last:                      {}
            args:                           {}
            kwargs:                         {}

            # ----------------------------------------------------------------------
            """).format( repo.root,
                         node,
                         node_last,
                         args,
                         kwargs,
                       ))

    changes = []
    queue = [ node, ]
    visited = set()

    while queue:
        node = queue.pop()
        ctx = repo[node]

        changes.append(_GetChangeInfo(repo, ctx))
        visited.add(node)

        for child in ctx.children():
            if child not in visited:
                queue.append(child)

    changes.sort(key=lambda c: c["date"])

    return HookImpl.Invoke( _GetRepoRoot(),
                            ui,
                            "Pull",
                            { "changes" : changes,
                            },
                            is_debug,
                          )

# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
def _IsDebug(ui):
    return ui.config("ui", "debug", default='').strip().lower() == "true"

# ----------------------------------------------------------------------
def _GetChangeInfo(repo, ctx):
    # ----------------------------------------------------------------------
    def TransformFilename(filename):
        return os.path.join(repo.root, filename).replace('/', os.path.sep)

    # ----------------------------------------------------------------------

    parents = ctx.parents()
    if not parents:
        parents = [ None, ]

    status = repo.status(parents[0], ctx)

    t, tz = ctx.date()
    t = time.gmtime(t - tz)
    t = datetime.datetime(*t[:6])

    return { "id" : ctx.hex(),
             "author" : ctx.user(),
             "date" : t.isoformat(),
             "description" : ctx.description(),
             "branch" : ctx.branch(),
             "added" : [ TransformFilename(filename) for filename in status.added ],
             "modified" : [ TransformFilename(filename) for filename in status.modified ],
             "removed" : [ TransformFilename(filename) for filename in status.removed ],
           }

# ----------------------------------------------------------------------
def _GetRepoRoot():
    original_repo_root = os.getcwd()

    repo_root = original_repo_root
    while True:
        if os.path.isdir(os.path.join(repo_root, ".hg")):
            return repo_root

        potential_repo_root = os.path.dirname(repo_root)
        if potential_repo_root == repo_root:
            raise Exception("No repository found in '{}' or its ancestors".format(original_repo_root))

        repo_root = potential_repo_root
