# ----------------------------------------------------------------------
# |  
# |  __init__.py
# |  
# |  David Brownell <db@DavidBrownell.com>
# |      2018-04-20 19:28:09
# |  
# ----------------------------------------------------------------------
# |  
# |  Copyright David Brownell 2018.
# |  Distributed under the Boost Software License, Version 1.0.
# |  (See accompanying file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
# |  
# ----------------------------------------------------------------------
"""Contains types and methods that are fundamental"""

import datetime
import os
import sys
import time

from collections import OrderedDict
from contextlib import contextmanager

import six

# ----------------------------------------------------------------------
_script_fullpath = os.path.abspath(__file__) if "python" in sys.executable.lower() else sys.executable
_script_dir, _script_name = os.path.split(_script_fullpath)
# ----------------------------------------------------------------------

# ----------------------------------------------------------------------
# |  
# |  Public Types
# |  
# ----------------------------------------------------------------------
class Nonlocals(object):
    """
    Python 2.7 compatible replacement for the nonlocal keyword.

    Example:
        nonlocals = Nonlocals(x=10, y=20)

        def Foo():
            nonlocals.x = 30
            nonlocals.y = 40

        Foo()

        # nonlocals.x == 30
        # nonlocals.y == 40
    """

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

# ----------------------------------------------------------------------
# |  
# |  Public Methods
# |  
# ----------------------------------------------------------------------
def Describe( item,                         # str, dict, iterable, obj
              output_stream=sys.stdout,
            ):
    """Writes information about the item to the provided stream."""

    # ----------------------------------------------------------------------
    def OutputDict(item, indentation_str):
        if not item:
            output_stream.write("-- empty dict --\n")
            return

        if hasattr(item, "_asdict"):
            item = item._asdict()

        keys = OrderedDict([ (key, key if isinstance(key, six.string_types) else str(key)) for key in item.keys() ])

        max_length = 0
        for key in six.itervalues(keys):
            max_length = max(max_length, len(key))

        item_indentation_str = indentation_str + (' ' * (max_length + len(" : ")))
        
        for index, (key, key_name) in enumerate(six.iteritems(keys)):
            output_stream.write("{0}{1:<{2}} : ".format( indentation_str if index else '',
                                                         key_name,
                                                         max_length,
                                                       ))

            Impl(item[key], item_indentation_str)

    # ----------------------------------------------------------------------
    def OutputList(item, indentation_str):
        if not item:
            output_stream.write("-- empty list --\n")
            return

        item_indentation_str = indentation_str + (' ' * 5)

        for index, i in enumerate(item):
            output_stream.write("{0}{1:<5}".format( indentation_str if index else '',
                                                    "{})".format(index),
                                                  ))
            Impl(i, item_indentation_str)

    # ----------------------------------------------------------------------
    def Impl(item, indentation_str):
        if isinstance(item, six.string_types):
            output_stream.write("{}\n".format(item))
        elif isinstance(item, dict):
            OutputDict(item, indentation_str)
        elif isinstance(item, list):
            OutputList(item, indentation_str)
        else:
            # ----------------------------------------------------------------------
            def Display():
                try:
                    # Is the item iterable?
                    potential_attribute_name = next(item(item))

                    # Is the item dict-like?
                    try:
                        ignore_me = item[potential_attribute_name]
                        OutputDict(item, indentation_str)
                    except TypeError:
                        # No, it isn't
                        OutputList(item, indentation_str)

                    return True

                except (TypeError, IndexError, StopIteration):
                    # Not iterable
                    return False

            # ----------------------------------------------------------------------

            if not Display():
                content = str(item).strip()

                if "<class" not in content:
                    content += "{}{}".format( '\n' if content.count('\n') > 1 else ' ',
                                              type(item),
                                            )

                output_stream.write("{}\n".format(('\n{}'.format(indentation_str)).join(content.split('\n'))))

    # ----------------------------------------------------------------------

    Impl(item, '')
    output_stream.write('\n\n')

# ----------------------------------------------------------------------
def ObjectToDict(obj):
    """Converts an object into a dict."""

    keys = [ k for k in dir(obj) if not k.startswith("__") ]
    return { k : getattr(obj, k) for k in keys }

# ----------------------------------------------------------------------
def ObjectStrImpl( obj, 
                   include_methods=False,
                   include_private=True,
                 ):
    """\
    Implementation of an object's __str__ method.

    Example:
        def __str__(self):
            return CommonEnvironment.ObjStrImpl(self)
    """

    d = ObjectToDict(obj)

    if not include_methods or not include_private:
        for k in list(six.iterkeys(d)):
            if not include_methods and callable(d[k]):
                del d[k]
            elif not include_private and k.startswith('_'):
                del d[k]

    sink = six.moves.StringIO()
    Describe(d, sink)

    return "{}\n{}\n".format(type(obj), sink.getvalue().rstrip())
