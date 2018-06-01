# ----------------------------------------------------------------------
# |  
# |  PythonActivationActivity.py
# |  
# |  David Brownell <db@DavidBrownell.com>
# |      2018-05-06 16:43:01
# |  
# ----------------------------------------------------------------------
# |  
# |  Copyright David Brownell 2018.
# |  Distributed under the Boost Software License, Version 1.0.
# |  (See accompanying file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
# |  
# ----------------------------------------------------------------------
"""Contains the PythonActivationActivity object"""

import os
import re
import shutil
import sys

from collections import OrderedDict

import inflect as inflect_mod
import six

from RepositoryBootstrap import Constants
from RepositoryBootstrap.Impl import CommonEnvironmentImports
from RepositoryBootstrap.Impl.ActivationActivity import ActivationActivity

# ----------------------------------------------------------------------
_script_fullpath = os.path.abspath(__file__) if "python" in sys.executable.lower() else sys.executable
_script_dir, _script_name = os.path.split(_script_fullpath)
# ----------------------------------------------------------------------

inflect                                     = inflect_mod.engine()

# ----------------------------------------------------------------------
EASY_INSTALL_PTH_FILENAME                   = "easy-install.pth"

SCRIPTS_DIR_NAME                            = "__scripts__"

WRAPPERS_FILENAME                           = "__wrappers__.txt"

# ----------------------------------------------------------------------
@CommonEnvironmentImports.Interface.staticderived
@CommonEnvironmentImports.Interface.clsinit
class PythonActivationActivity(ActivationActivity):
    
    # ----------------------------------------------------------------------
    # |  
    # |  Public Properties
    # |  
    # ----------------------------------------------------------------------
    Name                                    = "Python"
    DelayExecute                            = False

    # Set in __clsinit__
    LibrarySubdirs                          = None
    ScriptSubdirs                           = None

    BinSubdirs                              = None
    BinExtension                            = None

    # ----------------------------------------------------------------------
    # |  
    # |  Public Methods
    # |  
    # ----------------------------------------------------------------------
    @classmethod
    def __clsinit__(cls):
        shell = CommonEnvironmentImports.CurrentShell

        if shell.CategoryName == "Windows":
            cls.LibrarySubdirs = [ "Lib", "site-packages", ]
            cls.ScriptSubdirs = [ "Scripts", ]

            cls.BinSubdirs = None
            cls.BinExtension = ".exe"

        elif shell.CategoryName == "Linux":
            cls.LibrarySubdirs = [ "lib", "python{python_version_short}", "site-packages", ]
            cls.ScriptSubdirs = [ "bin", ]

            cls.BinSubdirs = [ "bin", ]
            cls.BinExtension = ''

        else:
            assert False, shell.CategoryName

    # ----------------------------------------------------------------------
    @classmethod
    def Setup( cls, 
               output_stream,
               verbose,
               shell,
             ):
        stats = [ 0, ] * cls.NormalizeScriptResult_NumItems

        output_stream.write("Normalizing python scripts...")
        with output_stream.DoneManager( done_suffixes=[ lambda: "{} modified".format(inflect.no("script", stats[cls.NormalizeScriptResult_Modified])),
                                                        lambda: "{} matched".format(inflect.no("script", stats[cls.NormalizeScriptResult_NoChange])),
                                                        lambda: "{} skipped".format(inflect.no("script", stats[cls.NormalizeScriptResult_NoMatch])),
                                                        
                                                      ],
                                        suffix='\n',
                                      ) as dm:
            python_dir = os.path.join(_script_dir, "..", "..", "..", Constants.TOOLS_SUBDIR, cls.Name)
            assert os.path.isdir(python_dir), python_dir

            python_versions = OrderedDict()

            for item in os.listdir(python_dir):
                fullpath = os.path.join(python_dir, item)
                if os.path.isdir(fullpath):
                    python_versions[item] = fullpath

            for index, (python_version, fullpath) in enumerate(six.iteritems(python_versions)):
                dm.stream.write("Processing '{}' ({} of {})...".format( python_version,
                                                                        index + 1,
                                                                        len(python_versions),
                                                                      ))
                with dm.stream.DoneManager( suffix='\n' if verbose else '',
                                          ) as this_dm:
                    fullpath = os.path.join(fullpath, shell.CategoryName)
                    assert os.path.isdir(fullpath), fullpath

                    # Get the script dir with its populated values
                    sub_dict = cls._CreateSubDict(python_version)

                    script_dir = os.path.join(fullpath, *[ sub_dir.format(**sub_dict) for sub_dir in cls.ScriptSubdirs ])
                    assert os.path.isdir(script_dir), script_dir

                    # Process the files
                    verbose_stream = CommonEnvironmentImports.StreamDecorator(this_dm.stream if verbose else None)

                    for item in os.listdir(script_dir):
                        if item == "__pycache__":
                            continue

                        if os.path.splitext(item)[1] in [ ".pyc", ".pyo", ]:
                            continue

                        fullpath = os.path.join(script_dir, item)
                        if not os.path.isfile(fullpath):
                            continue

                        result = cls.NormalizeScript(fullpath)
                        stats[result] += 1

                        verbose_stream.write("{0:<40} {1}\n".format( "'{}':".format(item), 
                                                                     cls.NormalizeScriptResultStrings[result],
                                                                   ))

            return dm.result

    # ----------------------------------------------------------------------
    ( NormalizeScriptResult_NoMatch,
      NormalizeScriptResult_NoChange,
      NormalizeScriptResult_Modified,

      NormalizeScriptResult_NumItems,
    ) = range(4)

    NormalizeScriptResultStrings = [ "No Match",
                                     "No Change",
                                     "Modified",
                                   ]

    _NormalizeScript_script_shebang_regex               = re.compile(r"^\s*(#!.+python.*?)$", re.MULTILINE)

    if sys.version_info[0] == 2:
        _NormalizeScript_executable_shebang_regex       = re.compile(r"(#!.+pythonw?\.exe)")
    else:
        _NormalizeScript_executable_shebang_regex       = re.compile(b"(#!.+pythonw?\.exe)")

    @classmethod
    def NormalizeScript(cls, script_filename):
        """
        Normalizes a python script so that it can be run with a generic python installation.
        
        Returns a NormalizeScriptResult_ value.
        """

        if os.path.splitext(script_filename)[1] == ".exe":
            with open(script_filename, 'rb') as f:
                content = f.read()

            content = cls._NormalizeScript_executable_shebang_regex.split(content, maxsplit=1)

            if len(content) != 3:
                return cls.NormalizeScriptResult_NoMatch

            prev_content = content[1]
            
            content[1] = b"#!python.exe"
            assert len(prev_content) >= len(content[1]), (len(prev_content), len(content[1]))
            content[1] += b' ' * (len(prev_content) - len(content[1]) - 2)
            content[1] += b'\r\n'

            if content[1] == prev_content:
                return cls.NormalizeScriptResult_NoChange

            with open(script_filename, 'wb') as f:
                f.write(b''.join(content))

        else:
            try:
                with open(script_filename) as f:
                    content = f.read()

                content = cls._NormalizeScript_script_shebang_regex.split(content, maxsplit=1)

            except UnicodeDecodeError:
                content = []

            if len(content) != 3:
                return cls.NormalizeScriptResult_NoMatch

            prev_content = content[1]
            content[1] = "#!/usr/bin/env python"

            if content[1] == prev_content:
                return cls.NormalizeScriptResult_NoChange

            with open(script_filename, 'w') as f:
                f.write(''.join(content))

        return cls.NormalizeScriptResult_Modified

    # ----------------------------------------------------------------------
    # |  
    # |  Private Methods
    # |  
    # ----------------------------------------------------------------------
    @classmethod
    def _CreateCommandsImpl( cls,
                             output_stream,
                             verbose_stream,
                             shell,
                             configuration,
                             repositories,
                             version_specs,
                             generated_dir,
                             no_python_libraries=False,
                           ):
        dest_dir = os.path.join(generated_dir, cls.Name)

        verbose_stream.write("Cleaning previous content...")
        with verbose_stream.DoneManager():
            CommonEnvironmentImports.FileSystem.RemoveTree(dest_dir)

        CommonEnvironmentImports.FileSystem.MakeDirs(dest_dir)

        actions = [ shell.Commands.AugmentPath(dest_dir),
                  ]

        # Add the binary
        bin_dir = dest_dir
        if cls.BinSubdirs:
            bin_dir = os.path.join(bin_dir, *cls.BinSubdirs)
            actions.append(shell.Commands.AugmentPath(bin_dir))

        # Add the script dir environment var
        script_dir = dest_dir
        if cls.ScriptSubdirs:
            script_dir = os.path.join(script_dir, *cls.ScriptSubdirs)
            
            actions += [ shell.Commands.Set("PYTHON_SCRIPT_DIR", script_dir),
                         shell.Commands.AugmentPath(script_dir),
                       ]

        actions.append(shell.Commands.Set("PYTHONUNBUFFERED", "1"))

        # Get the python version
        tools_dir = os.path.realpath(os.path.join(_script_dir, "..", "..", "..", Constants.TOOLS_SUBDIR, cls.Name))
        assert os.path.isdir(tools_dir), tools_dir

        tools_dir, python_version = cls.GetVersionedDirectoryEx(version_specs.Tools, tools_dir)
        assert os.path.isdir(tools_dir), tools_dir
        assert python_version

        if python_version.startswith('v'):
            python_version = python_version[1:]

        # Create a substitute dict that can be used to populate subdirs based on the python
        # version being used.
        sub_dict = cls._CreateSubDict(python_version)

        for k, v in six.iteritems(sub_dict):
            actions.append(shell.Commands.Set("DEVELOPMENT_ENVIRONMENT_{}".format(k.upper()), v))

        # Copy all of the python content that doesn't change based on libraries
        # (basically, this is everything except the library and script directories).
        nonlocals = CommonEnvironmentImports.CommonEnvironment.Nonlocals( easy_install_path_filename=None,
                                                                        )

        link_commands = []

        verbose_stream.write("Linking static content...")
        with verbose_stream.DoneManager( done_suffix=lambda: "{} found".format(inflect.no("item", len(link_commands))),
                                       ) as dm:
            # Pre-populate the dynamic content
            dynamic_subdirs = {}

            for subdirs in [ cls.LibrarySubdirs,
                             cls.ScriptSubdirs,
                           ]:
                this_dynamic_subdirs = dynamic_subdirs

                for subdir in subdirs:
                    subdir = subdir.format(**sub_dict)
                    this_dynamic_subdirs = this_dynamic_subdirs.setdefault(subdir, {})

            # ----------------------------------------------------------------------
            def TraverseTree(source, dest, dyanmic_subdirs):
                CommonEnvironmentImports.FileSystem.MakeDirs(dest)

                if os.path.isdir(source):
                    is_bin_dir = cls.BinSubdirs and source.endswith(os.path.join(*cls.BinSubdirs))
                    
                    items = os.listdir(source)

                    for item in items:
                        if item not in dyanmic_subdirs:
                            if item == EASY_INSTALL_PTH_FILENAME:
                                nonlocals.easy_install_path_filename = os.path.join(source, item)
                                continue

                            elif item == "__pycache__":
                                continue

                            elif os.path.splitext(item)[1] in [ ".pyc", ".pyo", ]:
                                continue

                            elif is_bin_dir and item.startswith("python") and shell.CategoryName == "Linux":
                                # Pip uses the python binary to determine the default install path. On Linux,
                                # pip will also resolve the symbolic link we are creating here. This means that
                                # it will install libraries relative to the Tools version of python rather than
                                # the generated version. To work around this, copy the python binaries rather
                                # than creating a link to them.
                                continue

                            link_commands.append(shell.Commands.SymbolicLink( os.path.join(dest, item), 
                                                                              os.path.join(source, item),
                                                                              remove_existing=False,
                                                                            ))

                # This is counter-intuitive, but we don't need to walk all folders as
                # the ones that aren't dynamic have already been linked. Walk the dynamic 
                # ones instead.
                for k, v in six.iteritems(dyanmic_subdirs):
                    TraverseTree(os.path.join(source, k), os.path.join(dest, k), v)

            # ----------------------------------------------------------------------

            TraverseTree(tools_dir, dest_dir, dynamic_subdirs)

            # Copy the python binaries on Linux
            if shell.CategoryName == "Linux":
                assert cls.BinSubdirs
                bin_source_dir = os.path.join(tools_dir, *cls.BinSubdirs)
                bin_dest_dir = os.path.join(dest_dir, *cls.BinSubdirs)

                for item in os.listdir(bin_source_dir):
                    if item.startswith("python"):
                        shutil.copy2( os.path.join(bin_source_dir, item),
                                      os.path.join(bin_dest_dir, item),
                                    )

        # Get the libraries
        libraries = OrderedDict()

        verbose_stream.write("Linking dynamic libraries...")
        with verbose_stream.DoneManager( done_suffix=lambda: "{} found".format(inflect.no("library", len(libraries))),
                                       ) as dm:
            python_version_dirs = [ "python2", "python3", ]
            python_version_dir = python_version_dirs[int(python_version.split('.')[0]) - 2]

            this_output_stream = dm.stream if dm.stream.IsSet else output_stream

            libraries.update(cls._GetLibraries( this_output_stream,
                                                repositories,
                                                version_specs,
                                                generated_dir,
                                                library_version_dirs={ tuple(python_version_dirs) : python_version_dir,
                                                                     },
                                              ))

            if no_python_libraries:
                for key in list(six.iterkeys(libraries)):
                    if key not in [ "CommonEnvironment",
                                    "colorama",
                                  ]:
                        del libraries[key]

            if libraries:
                library_dest_dir = os.path.join(dest_dir, *[ subdir.format(**sub_dict) for subdir in cls.LibrarySubdirs ])
                assert os.path.isdir(library_dest_dir), library_dest_dir

                for name, library_info in six.iteritems(libraries):
                    for item in os.listdir(library_info.Fullpath):
                        if item in [ SCRIPTS_DIR_NAME,
                                   ]:
                            continue

                        link_commands.append(shell.Commands.SymbolicLink( os.path.join(library_dest_dir, item), 
                                                                          os.path.join(library_info.Fullpath, item),
                                                                          remove_existing=False,
                                                                        ))

        if libraries:
            # Apply scripts
            scripts = OrderedDict()
        
            verbose_stream.write("Linking dynamic library scripts...")
            with verbose_stream.DoneManager( done_suffix=lambda: "{} found".format(inflect.no("script", len(scripts))),
                                           ) as dm:
                this_output_stream = dm.stream if dm.stream.IsSet else output_stream

                scripts.update(cls._GetLibraryScripts( this_output_stream,
                                                       libraries,
                                                       SCRIPTS_DIR_NAME,
                                                     ))
        
                if scripts:
                    script_dest_dir = os.path.join(dest_dir, *[ subdir.format(**sub_dict) for subdir in cls.ScriptSubdirs ])
                    assert os.path.isdir(script_dest_dir), script_dest_dir
        
                    for name, script_info in six.iteritems(scripts):
                        link_commands.append(shell.Commands.SymbolicLink( os.path.join(script_dest_dir, name), 
                                                                          script_info.Fullpath,
                                                                          remove_existing=False,
                                                                        ))

            # Create wrappers to make it easier to invoke python files on Windows
            if scripts and shell.CategoryName == "Windows":
                wrappers = []

                verbose_stream.write("Creating script wrappers...")
                with verbose_stream.DoneManager( done_suffix=lambda: "{} written".format(inflect.no("wrapper", len(wrappers))),
                                               ):
                    for name, script_info in six.iteritems(scripts):
                        if os.path.splitext(name)[1] != ".py":
                            continue

                        wrapper_filename = os.path.join(script_dest_dir, "{}{}".format(name, shell.ScriptExtension))
                        if not os.path.isfile(wrapper_filename):
                            wrappers.append(os.path.basename(wrapper_filename))

                            wrapper_commands = [ shell.Commands.EchoOff(),
                                                 shell.Commands.Execute('python "{}" {}'.format(os.path.join(script_dest_dir, name), shell.AllArgumentsScriptVariable)),
                                               ]

                            with open(wrapper_filename, 'w') as f:
                                f.write(shell.GenerateCommands(wrapper_commands))

                            shell.MakeFileExecutable(wrapper_filename)

                    if wrappers:
                        with open(os.path.join(script_dest_dir, WRAPPERS_FILENAME), 'w') as f:
                            f.write('\n'.join(wrappers))

        if link_commands:
            verbose_stream.write("Applying {}...".format(inflect.no("link", len(link_commands))))
            with verbose_stream.DoneManager() as dm:
                dm.result, output = shell.ExecuteCommands(link_commands, output_stream=None)
                if dm.result != 0:
                    raise Exception(textwrap.dedent(
                        """\
                        Unable to create '{}' symbolic links.

                            {}
                        """).format( cls.Name,
                                     CommonEnvironmentImports.StringHelpers.LeftJustify(output, 4),
                                   ))

            # Check for eggs
            eggs = []

            for link in link_commands:
                if os.path.splitext(link.Target)[1] == ".egg":
                    eggs.append(link.LinkFilename)

            if eggs:
                verbose_stream.write("Applying {}...".format(inflect.no("egg", len(eggs))))
                with verbose_stream.DoneManager() as dm:
                    if nonlocals.easy_install_path_filename is not None:
                        original_content = open(nonlocals.easy_install_path_filename).read()
                    else:
                        original_content = "# No original content"

                    with open(os.path.join(library_dest_dir, EASY_INSTALL_PTH_FILENAME), 'w') as f:
                        f.write(textwrap.dedent(
                            """\
                            {}

                            {}
                            """).format( original_content,
                                         '\n'.join([ "./{}".format(os.path.basename(egg)) for egg in eggs ]),
                                       ))

        cls._WriteLibraryInfo(generated_dir, libraries)

        return actions

    # ----------------------------------------------------------------------
    @staticmethod
    def _CreateSubDict(python_version):
        if python_version.startswith('v'):
            python_version = python_version[1:]

        return { "python_version" : python_version,
                 "python_version_short" : '.'.join(python_version.split('.')[:2]),
               }
