# ----------------------------------------------------------------------
# |  
# |  PyCoverageTestExecutor.py
# |  
# |  David Brownell <db@DavidBrownell.com>
# |      2018-05-24 21:27:31
# |  
# ----------------------------------------------------------------------
# |  
# |  Copyright David Brownell 2018.
# |  Distributed under the Boost Software License, Version 1.0.
# |  (See accompanying file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
# |  
# ----------------------------------------------------------------------
"""Contains the TestExecutor object"""

import datetime
import os
import re
import sys
import textwrap
import time

from collections import OrderedDict
from xml.etree import ElementTree as ET

from CommonEnvironment.CallOnExit import CallOnExit
from CommonEnvironment import FileSystem
from CommonEnvironment.Interface import staticderived
from CommonEnvironment import Process
from CommonEnvironment.Shell.All import CurrentShell

from CommonEnvironment.TestExecutorImpl import TestExecutorImpl

# ----------------------------------------------------------------------
_script_fullpath = os.path.abspath(__file__) if "python" in sys.executable.lower() else sys.executable
_script_dir, _script_name = os.path.split(_script_fullpath)
# ----------------------------------------------------------------------

sys.path.insert(0, _script_dir)
with CallOnExit(lambda: sys.path.pop(0)):
    from StandardTestExecutor import TestExecutor as StandardTestExecutor

# ----------------------------------------------------------------------
@staticderived
class TestExecutor(TestExecutorImpl):
    """
    Extracts code coverage information from python files. Coverage includes and
    excludes are extracted from comments embedded in the source.

    Available comments are:

        # code_coverage: disable

        # code_coverage: include = <Relative or full path to Python File #1>
        # code_coverage: include = <Relative or full path to Python File #2>
        # ...
        # code_coverage: include = <Relative or full path to Python File #N>

        # code_coverage: exclude = <Relative or full path to Python File #1>
        # code_coverage: exclude = <Relative or full path to Python File #2>
        # ...
        # code_coverage: exclude = <Relative or full path to Python File #N>

    Note that if no values are extracted from the source, the code will make
    A best-guess to find the production code when the executed filename ends
    with _*Test.py
    """

    # ----------------------------------------------------------------------
    # |  Public Properties
    Name                                    = "PyCoverage"
    Description                             = "Extracts code coverage information for Python source code using coverage.py."

    # ----------------------------------------------------------------------
    # |  Public Methods
    @staticmethod
    def IsSupportedCompiler(compiler):
        # Supports any compiler that supports python; use this file as a test subject.
        return compiler.IsSupported(_script_fullpath if os.path.splitext(_script_name)[1] == ".py" else "{}.py".format(os.path.splitext(_script_fullpath)[0]))

    # ----------------------------------------------------------------------
    @classmethod
    def Execute( cls,
                 compiler,
                 context,
                 command_line,
                 includes=None,
                 excludes=None,
                 verbose=False,
               ):
        assert command_line

        includes = includes or []
        excludes = excludes or []

        # Get the name of the script to execute
        if command_line.lower().startswith("python"):
            filename = command_line[len("python"):].replace('"', '').strip()
            assert os.path.isfile(filename), filename
        else:
            filename = command_line

        # Attempt to extract include and exclude information from the source
        disable_code_coverage = False

        if not disable_code_coverage and not includes and not includes:
            regex = re.compile(textwrap.dedent(
                       r"""(?#
                        Header              )^.*?#\s*(?#
                        Label               )code_coverage\s*:\s*(?#
                        Action              )(?P<action>\S+)(?#
                        +Optional           )(?:(?#
                            Assignment      )\s*=\s*(?#
                            +Quote          )(?P<quote>")?(?#
                            Name            )(?P<name>.+?)(?#
                            -Quote          )(?P=quote)?(?#
                        -Optional           ))?(?#
                        Suffix              )\s*$(?#
                        )"""))

            for index, line in enumerate(open(filename).readlines()):
                match = regex.match(line)
                if not match:
                    continue

                action = match.group("action").lower()

                if action == "disable":
                    disable_code_coverage = True

                elif action in [ "include", "exclude", ]:
                    referenced_filename = match.group("name")
                    referenced_filename = os.path.abspath(os.path.join(os.path.dirname(filename), referenced_filename))

                    if not os.path.isfile(referenced_filename):
                        raise Exception("'{}', referenced on line {}, is not a valid filename".format(referenced_filename, index + 1))

                    if action == "include":
                        includes.append(referenced_filename)
                    elif action == "exclude":
                        excludes.append(referenced_filename)
                    else:
                        assert False, action

                else:
                    raise Exception("'{}' is not a supported action".format(action))

        if disable_code_coverage:
            return StandardTestExecutor.Execute( compiler,
                                                 context,
                                                 'python "{}"'.format(filename),
                                               )

        # Attempt to determine include and exclude information based on the original filename
        if not disable_code_coverage and not includes and not excludes:
            sut_filename = compiler.TestToItemName(filename)

            # Import by python fullpath
            dirname, basename = os.path.split(sut_filename)
            
            stack = [ basename, ]

            while True:
                potential_filename = os.path.join(dirname, "__init__.py")
                if not os.path.isfile(potential_filename):
                    break

                potential_dirname, basename = os.path.split(dirname)

                stack.append(basename)

                if potential_dirname == dirname:
                    break

                dirname = potential_dirname

            stack.reverse()

            includes.append("*/{}".format('/'.join(stack)))
        
        # Run the process and calculate code coverage
        temp_filename = CurrentShell.CreateTempFilename(".py")

        with open(temp_filename, 'w') as f:
            f.write(textwrap.dedent(
                """\
                from coverage.cmdline import main

                main()
                """))

        with CallOnExit(lambda: FileSystem.RemoveFile(temp_filename)):
            command_line_template = 'python "{}" "{{}}"'.format(temp_filename)

            # Run the process
            start_time = time.time()

            command_line = '{} {} {} {}'.format( command_line_template.format("run"),
                                                 '"--include={}"'.format(','.join(includes)) if includes else '',
                                                 '"--omit={}"'.format(','.join(excludes)) if excludes else '',
                                                 filename,
                                               )

            test_result, test_output = Process.Execute(command_line)
            test_time = str(datetime.timedelta(seconds=(time.time() - start_time)))

            # Get the coverage info
            start_time = time.time()

            xml_temp_filename = CurrentShell.CreateTempFilename(".xml")

            command_line = '{} -o "{}"'.format( command_line_template.format("xml"),
                                                xml_temp_filename,
                                              )

            coverage_result, coverage_output = Process.Execute(command_line)
            coverage_time = str(datetime.timedelta(seconds=(time.time() - start_time)))
            coverage_data_filename = xml_temp_filename

        # Get the percentage info
        if not os.path.isfile(coverage_data_filename):
            if coverage_result == 0:
                coverage_result = -1

            coverage_data_filename = None

        if coverage_result != 0:
            percentage = None
            percentages = None
        else:
            root = ET.fromstring(open(coverage_data_filename).read())

            percentage = float(root.attrib["line-rate"]) * 100
            
            percentages = OrderedDict()

            for package in root.findall("packages/package"):
                for class_ in package.findall("classes/class"):
                    percentages[class_.attrib["filename"]] = float(class_.attrib["line-rate"]) * 100

        return cls.ExecuteResult( test_result,
                                  test_output,
                                  test_time,
                                  coverage_result,
                                  coverage_output,
                                  coverage_time,
                                  coverage_data_filename,
                                  percentage,
                                  percentages,
                                )
