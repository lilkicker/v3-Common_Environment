# ----------------------------------------------------------------------
# |  
# |  __init__.py
# |  
# |  David Brownell <db@DavidBrownell.com>
# |      2018-05-06 10:32:50
# |  
# ----------------------------------------------------------------------
# |  
# |  Copyright David Brownell 2018.
# |  Distributed under the Boost Software License, Version 1.0.
# |  (See accompanying file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
# |  
# ----------------------------------------------------------------------
"""Types and methods useful during environment activation"""

import os
import sys
import textwrap

from collections import OrderedDict

import six
import six.moves.cPickle as pickle

import RepositoryBootstrap
from RepositoryBootstrap import Constants

from RepositoryBootstrap.Impl import CommonEnvironmentImports
from RepositoryBootstrap.Impl import Utilities

# ----------------------------------------------------------------------
_script_fullpath = os.path.abspath(__file__) if "python" in sys.executable.lower() else sys.executable
_script_dir, _script_name = os.path.split(_script_fullpath)
# ----------------------------------------------------------------------

# ----------------------------------------------------------------------
# |  
# |  Public Types
# |  
# ----------------------------------------------------------------------
class ActivationActivity(CommonEnvironmentImports.Interface.Interface):
    """
    Activity that can be performed at any time (during activation or later).
    Derived classes should account for repeated invocations within the same
    environment.
    """

    # ----------------------------------------------------------------------
    # |  
    # |  Public Properties
    # |  
    # ----------------------------------------------------------------------
    @CommonEnvironmentImports.Interface.abstractproperty
    def Name(self):
        raise Exception("Abstract property")

    @CommonEnvironmentImports.Interface.abstractproperty
    def DelayExecute(self):
        """
        True if the commands should be executed via DelayExecute

        The vast majority of activation activities can be created as script generation
        time. However, there are some actions that must be generated at execution time, as 
        they rely on information or state changes output by the statements that run immediately
        before them.

        For example, an action may rely on an environment variable being created; this environment
        variable will not exist at generation time (as the code to create the variable has not been
        executed yet), but is available at execution time.

        Note that this functionality should be used only when necessary, as it is
        has a large performance penality.
        """
        raise Exception("Abstract property")

    # ----------------------------------------------------------------------
    # |  
    # |  Public Methods
    # |  
    # ----------------------------------------------------------------------
    @classmethod
    def CreateCommands( cls,
                        output_stream,
                        verbose,
                        configuration,
                        repositories,
                        version_specs,
                        generated_dir,
                        *args, 
                        **kwargs
                      ):
        commands = []

        if cls.DelayExecute:
            commands += cls._DelayExecute( cls,
                                           configuration,
                                           repositories,
                                           version_specs,
                                           generated_dir,
                                         )

            for command in commands:
                if isinstance(command, CommonEnvironmentImports.CurrentShell.Commands.Message):
                    command.Value = "  {}".format(command.Value)

            commands.insert(0, CommonEnvironmentImports.CurrentShell.Commands.Message("Delay invoking '{}'...".format(cls.Name)))
            commands.append(CommonEnvironmentImports.CurrentShell.Commands.Message("DONE!"))

        else:
            output_stream.write("Activating '{}'...".format(cls.Name))
            output_stream.flush()

            with output_stream.DoneManager( suffix='\n' if verbose else None,
                                          ) as dm:
                commands += cls._CreateCommandsImpl( dm.stream,
                                                     CommonEnvironmentImports.StreamDecorator(dm.stream if verbose else None),
                                                     configuration,
                                                     repositories,
                                                     version_specs,
                                                     generated_dir,
                                                     *args,
                                                     **kwargs
                                                   )

        return commands

    # ----------------------------------------------------------------------
    @staticmethod
    def SortVersions(version_strings):
        if not version_strings:
            return

        import semantic_version

        lookup = {}
        versions = []

        for version_string in version_strings:
            original_version_string = version_string
            
            for potential_prefix in [ "v", "r", ]:
                if version_string.startswith(potential_prefix):
                    version_string = version_string[len(potential_prefix):]
                    break

            try:
                # Remove leading zeros from version string values
                parts = []

                for part in version_string.split('.'):
                    assert part

                    part = part.lstrip('0')
                    if part:
                        parts.append(part)
                    else:
                        parts.append('0')

                version = semantic_version.Version.coerce('.'.join(parts))

                lookup[version] = original_version_string
                versions.append(version)

            except ValueError:
                continue

        if not versions:
            return

        versions.sort(reverse=True)

        for version in versions:
            yield lookup[version]

    # ----------------------------------------------------------------------
    @classmethod
    def GetVersionedDirectory(cls, version_info, *path_components_or_fullpath):
        """Returns the fullpath to the latest versioned directory or the version specified in version_info."""
        return cls.GetVersionedDirectoryEx(version_info, *path_components_or_fullpath)[0]

    # ----------------------------------------------------------------------
    @classmethod
    def GetVersionedDirectoryEx(cls, version_info, *path_components_or_fullpath):
        """Returns the fullpath to the latest versioned directory or the version specified in version_info and its version."""

        if len(path_components_or_fullpath) == 1:
            fullpath = path_components_or_fullpath[0]
            path_components = fullpath.split(os.path.sep)
        else:
            fullpath = os.path.join(*path_components_or_fullpath)
            path_components = path_components_or_fullpath

        # The last part of the path is the name of the library/tool.
        # The second to last part is the type (Tools | Libraries)
        assert len(path_components) > 1, fullpath

        name = path_components[-1]

        explicit_version = next((vi for vi in version_info if vi.Name == name), None)
        if explicit_version is not None:
            versions = [ explicit_version.Version, ]
        else:
            versions = cls.SortVersions([ item for item in os.listdir(fullpath) if os.path.isdir(os.path.join(fullpath, item)) ])

        # Cache any exceptions associated with fullpath customization and only percolate them
        # if we don't find any other valid customization
        exceptions = []

        for version in versions:
            if version is not None:
                this_fullpath = os.path.join(fullpath, version)
            else:
                this_fullpath = fullpath

            assert os.path.isdir(this_fullpath), this_fullpath

            try:
                this_fullpath = cls.GetCustomizedFullpath(this_fullpath)
                assert os.path.isdir(this_fullpath), this_fullpath

                return this_fullpath, version
                
            except Exception as ex:
                exceptions.append(ex)

        if exceptions:
            raise exceptions[0]

        return fullpath, version

    # ----------------------------------------------------------------------
    _GetCustomizedFullpath_PotentialOSNames = None

    @classmethod
    def GetCustomizedFullpath(cls, path):
        # Lazy init the set of potential os names
        if cls._GetCustomizedFullpath_PotentialOSNames is None:
            potential_names = set([ Constants.AGNOSTIC_OS_NAME,
                                    "src",
                                  ])

            for this_shell in CommonEnvironmentImports.Shell_ALL_TYPES:
                potential_names.add(this_shell.Name)
                potential_names.add(this_shell.CategoryName)

        
            cls._GetCustomizedFullpath_PotentialOSNames = potential_names

        # ----------------------------------------------------------------------
        def IsOSNamesDir(path, items):
            found_one = False

            for item in items:
                fullpath = os.path.join(path, item)
                if not os.path.isdir(fullpath):
                    continue

                if item in cls._GetCustomizedFullpath_PotentialOSNames:
                    found_one = True
                else:
                    return False

            return found_one

        # ----------------------------------------------------------------------
        def IsArchitectureDir(path, items):
            found_one = False

            for item in items:
                fullpath = os.path.join(path, item)
                if not os.path.isdir(fullpath):
                    continue

                if item in [ "x86", "x64", ]:
                    found_one = True
                else:
                    return False

            return found_one

        # ----------------------------------------------------------------------

        while True:
            subdirs = os.listdir(path)

            if IsOSNamesDir(path, subdirs):
                if CommonEnvironmentImports.CurrentShell.Name in subdirs:
                    path = os.path.join(path, CommonEnvironmentImports.CurrentShell.Name)
                elif CommonEnvironmentImports.CurrentShell.CategoryName in subdirs:
                    path = os.path.join(path, CommonEnvironmentImports.CurrentShell.CategoryName)
                elif Constants.AGNOSTIC_OS_NAME in subdirs:
                    path = os.path.join(path, Constants.AGNOSTIC_OS_NAME)
                else:
                    potential_names = [ CommonEnvironmentImports.CurrentShell.Name, ]
                    if CommonEnvironmentImports.CurrentShell.CategoryName != CommonEnvironmentImports.CurrentShell.Name:
                        potential_names.append(CommonEnvironmentImports.CurrentShell.CategoryName)
                    potential_names.append(Constants.AGNOSTIC_OS_NAME)

                    raise Exception("OS names were found in '{}', but no customization was found for '{}'.\n    Is one of {} missing?.".format( path,
                                                                                                                                                CommonEnvironmentImports.CurrentShell.Name,
                                                                                                                                                ', '.join([ "'{}'".format(name) for name in potential_names ]),
                                                                                                                                              ))
            elif IsArchitectureDir(path, subdirs):
                if CommonEnvironmentImports.CurrentShell.Architecture in subdirs:
                    path = os.path.join(path, CommonEnvironmentImports.CurrentShell.Architecture)
                else:
                    raise Exception("OS architectures were found in '{}', but no customization was found for '{}'.\n    Is one of {} missing?.".format( path,
                                                                                                                                                        CommonEnvironmentImports.CurrentShell.Architecture,
                                                                                                                                                        ', '.join([ "'{}'".format(name) for name in [ "x86",
                                                                                                                                                                                                      "x64",
                                                                                                                                                                                                    ] ]),
                                                                                                                                                      ))
            else:
                break

        return path

    # ----------------------------------------------------------------------
    @staticmethod
    def CallCustomMethod( customization_filename, 
                          method_name, 
                          kwargs, 
                          as_list=True,
                        ):
        """
        Calls the specified method if it exists with the args that it expects.
        Ensure that the return value is None or a list of items.
        """

        with Utilities.CustomMethodManager(customization_filename, method_name) as method:
            if method is None:
                return None

            method = CommonEnvironmentImports.Interface.CreateCulledCallable(method)

            result = method(kwargs)

            if as_list and not isinstance(result, list) and result is not None:
                result = [ result, ]

            return result

    # ----------------------------------------------------------------------
    # |  
    # |  Protected Types
    # |  
    # ----------------------------------------------------------------------
    class LibraryInfo(object):
        # ----------------------------------------------------------------------
        def __init__(self, repository, version_string, fullpath):
            self.Repository                 = repository
            self.Version                    = version_string
            self.Fullpath                   = fullpath

        # ----------------------------------------------------------------------
        def __str__(self):
            return CommonEnvironmentImports.CommonEnvironment.ObjectStrImpl(self)

    # ----------------------------------------------------------------------
    class ScriptInfo(object):
        # ----------------------------------------------------------------------
        def __init__(self, repository, fullpath):
            self.Repository                 = repository
            self.Fullpath                   = fullpath

        # ----------------------------------------------------------------------
        def __str__(self):
            return CommonEnvironmentImports.CommonEnvironment.ObjectStrImpl(self)

    # ----------------------------------------------------------------------
    # |  
    # |  Protected Methods
    # |  
    # ----------------------------------------------------------------------
    @classmethod
    def _GetLibraries( cls,
                       output_stream,
                       repositories,
                       version_specs,
                       generated_dir,
                       library_version_dirs=None,  # { ( <potential_version_dir>, ... ) : <dir_to_use>, }
                     ):
        """Returns all versioned libraries that should be activated."""
        library_version_dirs = library_version_dirs or {}

        version_info = version_specs.Libraries.get(cls.Name, [])

        # Create the libraries
        libraries = OrderedDict()
        errors = []

        for repository in repositories:
            potential_library_dir = os.path.join(repository.Root, Constants.LIBRARIES_SUBDIR, cls.Name)
            if not os.path.isdir(potential_library_dir):
                continue

            for item in os.listdir(potential_library_dir):
                if item in libraries:
                    errors.append(textwrap.dedent(
                        """\
                        The library '{name}' has already been defined.

                            New:                {new_name}{new_config} <{new_id}> [{new_root}]
                        Original:           {original_name}{original_config} <<{original_version}>> <{original_id}> [{original_root}]

                        """).format( name=item,
                                     new_name=repository.Name,
                                     new_config=" ({})".format(repository.Configuration) if repository.Configuration else '',
                                     new_id=repository.Id,
                                     new_root=repository.Root,
                                     original_name=libraries[item].Repository.Name,
                                     original_config=" ({})".format(libraries[item].Repository.Configuration) if libraries[item].Repo.Configuration else '',
                                     original_version=libraries[item].Version,
                                     original_id=libraries[item].Repository.Id,
                                     original_root=libraries[item].Repository.Root,
                                   ))
                    continue

                fullpath = os.path.join(potential_library_dir, item)

                # Drill down into the fullpath
                nonlocals = CommonEnvironmentImports.CommonEnvironment.Nonlocals(version=None)

                # ----------------------------------------------------------------------
                def InternalGetVersionedDirectoryEx(fullpath):
                    fullpath, nonlocals.version = cls.GetVersionedDirectoryEx(version_info, fullpath)
                    return fullpath

                # ----------------------------------------------------------------------
                def AugmentLibraryDir(fullpath):
                    while True:
                        prev_fullpath = fullpath

                        dirs = [ item for item in os.listdir(fullpath) if os.path.isdir(os.path.join(fullpath, item)) ]
                        if not dirs:
                            break

                        for library_versions, this_version in six.iteritems(library_version_dirs):
                            applies = True

                            for directory in dirs:
                                if directory not in library_versions:
                                    applies = False
                                    break

                            if not applies:
                                continue

                            if this_version not in dirs:
                                raise Exception("Library versions were found in '{}', but no customization was found for '{}' ({} found).".format( fullpath,
                                                                                                                                                   this_version,
                                                                                                                                                   ', '.join([ "'{}'".format(dir) for dir in dirs ]),
                                                                                                                                                 ))
                            fullpath = os.path.join(fullpath, this_version)
                            break

                        if fullpath == prev_fullpath:
                            break

                    return fullpath

                # ----------------------------------------------------------------------

                try:
                    for index, method in enumerate([ cls.GetCustomizedFullpath,
                                                     AugmentLibraryDir,
                                                     InternalGetVersionedDirectoryEx,
                                                     cls.GetCustomizedFullpath,
                                                     AugmentLibraryDir,
                                                   ]):
                        fullpath = method(fullpath)
                        assert os.path.isdir(fullpath), (index, fullpath)

                    libraries[item] = cls.LibraryInfo(repository, nonlocals.version, fullpath)

                except Exception as ex:
                    output_stream.write("WARNING: {}\n".format(CommonEnvironmentImports.StringHelpers.LeftJustify( str(ex),
                                                                                                                   len("WARNING: "),
                                                                                                                 )))

        if errors:
            raise Exception(''.join(errors))

        return libraries

    # ----------------------------------------------------------------------
    @classmethod
    def _GetLibraryScripts( cls,
                            output_stream,
                            libraries,
                            library_script_dir_name,
                          ):
        """
        Returns unique scripts that should be activated.
        """

        scripts = OrderedDict()

        for library_info in six.itervalues(libraries):
            potential_dir = os.path.join(library_info.Fullpath, library_script_dir_name)
            if not os.path.isdir(potential_dir):
                continue

            try:
                potential_dir = cls.GetCustomizedFullpath(potential_dir)
            except Exception as ex:
                output_stream.write("WARNING: {}\n".format(CommonEnvironmentImports.StringHelpers.LeftJustify( str(ex),
                                                                                                               len("WARNING: "),
                                                                                                             )))
                continue

            for item in os.listdir(potential_dir):
                item_name = item

                if item_name in scripts:
                    # ----------------------------------------------------------------------
                    def GenerateNewName(repository):
                        filename, ext = os.path.splitext(item)

                        new_name = "{}.{}{}".format( filename,
                                                     repository.Name,
                                                     ext,
                                                   )

                        assert new_name not in scripts, new_name

                        output_stream.write(textwrap.dedent(
                            """\
                            To avoid naming conflicts, the script '{}' has been renamed to '{}'.
                                Repository Name:        {}
                                Repository Id:          {}
                                Repository Root:        {}

                            """).format( item,
                                         new_name,
                                         repository.Name,
                                         repository.Id,
                                         repository.Root,
                                       ))

                        return new_name

                    # ----------------------------------------------------------------------

                    new_name = GenerateNewName(scripts[item_name].Repository)
                    
                    scripts[new_name] = scripts[item_name]

                    item_name = GenerateNewName(library_info.Repository)

                scripts[item_name] = cls.ScriptInfo( library_info.Repository,
                                                     os.path.join(potential_dir, item),
                                                   )

        return scripts

    # ----------------------------------------------------------------------
    @classmethod
    def _WriteLibraryInfo(cls, generated_dir, libraries):
        # Text file
        with open(os.path.join(generated_dir, "{}.txt".format(cls.Name)), 'w') as f:
            col_sizes = [ 40, 15, 60, ]
        
            template = "{{name:{0}}}  {{version:<{1}}}  {{fullpath:<{2}}}".format(*col_sizes)
        
            f.write(textwrap.dedent(
                """\
                {}
                {}
                {}
                """).format( template.format( name="Name",
                                              version="Version",
                                              fullpath="Fullpath",
                                            ),
                             template.format(**{ k : v for k, v in six.moves.zip( [ "name", "version", "fullpath", ],
                                                                                  [ '-' * col_size for col_size in col_sizes ],
                                                                                ) }),
                             '\n'.join([ template.format( name=k,
                                                          version=libraries[k].Version,
                                                          fullpath=libraries[k].Fullpath,
                                                        )
                                         for k in sorted(six.iterkeys(libraries), key=str.lower)
                                       ]),
                           ))

        # Pickle file
        with open(os.path.join(generated_dir, "{}.pickle".format(cls.Name)), 'wb') as f:
            pickle.dump(libraries, f)

    # ----------------------------------------------------------------------
    # |  
    # |  Private Methods
    # |  
    # ----------------------------------------------------------------------
    @staticmethod
    @CommonEnvironmentImports.Interface.abstractmethod
    def _CreateCommandsImpl( output_stream,
                             verbose_stream,
                             configuration,
                             repositories,
                             version_specs,
                             generated_dir,
                             *args,
                             **kwargs
                           ):
        """Returns commands returned to the activation script."""
        raise Exception("Abstract method")

# TODO: The following code may not be necessary. Remove it once Common_ContinuousIntegration
#       and Common_cpp_Common repositories are complete.
#
#     # ----------------------------------------------------------------------
#     @classmethod
#     def _DelayExecute( cls,
#                        shell,
#                        *args,
#                        **kwargs
#                      ):
#         script_tempfile = shell.CreateTempFilename(shell.ScriptExtension)
#         python_tempfile = shell.CreateTempFilename(".py")
#         pickle_tempfile = shell.CreateTempFilename(".pickle")
#     
#         # Write the arguments
#         with open(pickle_tempfile, 'wb') as f:
#             pickle.dump((args, kwargs), f)
#     
#         # Write the python code
#         with open(python_tempfile, 'w') as f:
#             f.write(textwrap.dedent(
#                 """\
#                 import os
#                 import sys
#     
#                 import six
#                 import six.moves.cPickle as pickle
#     
#                 sys.path.insert(0, r"{fundamental_path}")
#                 from RepositoryBootstrap.Impl import CommonEnvironmentImports
#                 from RepositoryBootstrap.Impl import ActivationActivity
#                 del sys.path[0]
#     
#                 shell = CommonEnvironmentImports.CurrentShell
#     
#                 # Read the arguments
#                 with open(r"{pickle_tempfile}", 'rb') as f:
#                     args, kwargs = pickle.load(f)
#     
#                 try:
#                     result = ActivationActivity._DelayExecuteCallback(*args, **kwargs)
#     
#                     if isinstance(result, tuple):
#                         result, commans = result
#                     elif result is None:
#                         result = 0
#                         commands = []
#                     else:
#                         commands = result
#                         result = 0
#     
#                 except:
#                     result = -1
#                     commands = []
#     
#                     import traceback
#                     sys.stderr.write("ERROR: {{}}".format(CommonEnvironmentImports.StringHelpers.LeftJustify(traceback.format_exc(), len("ERROR: "))))
#     
#                 if result != 0:
#                     for command in commands:
#                         if isinstance(command, shell.Commands.Message):
#                             sys.stderr.write(command.Value)
#     
#                     sys.stderr.write('\\n')
#                     sys.exit(result)
#     
#                 # Prep for execution
#                 while open(r"{script_tempfile}", 'w') as f:
#                     f.write(shell.GenerateCommands(commands))
#     
#                 shell.MakeFileExecutable(r"{script_tempfile}")
#     
#                 """).format( fundamental_path=RepositoryBootstrap.GetFundamentalRepository(),
#                              pickle_tempfile=pickle_tempfile,
#                              script_tempfile=script_tempfile,
#                            ))
#     
#         return [ shell.Commands.Comment("-- Delay executing '{}'".format(cls.Name)),
#     
#                  shell.Commands.Execute('python "{}"'.format(python_tempfile)),
#                  shell.Commands.ExitOnError(),
#                  shell.Commands.Call(script_tempfile),
#                  shell.Commands.ExitOnError(),
#                  
#                  shell.Commands.RemoveFile(python_tempfile),
#                  shell.Commands.RemoveFile(pickle_tempfile),
#                  shell.Commands.RemoveFile(script_tempfile),
#                  
#                  shell.Commands.Comment("-- End delay execution"),
#                ]
# 
# # ----------------------------------------------------------------------
# # ----------------------------------------------------------------------
# # ----------------------------------------------------------------------
# def _DelayExecuteCallback( configuration,
#                            repositories,
#                            version_specs,
#                            generated_dir,
#                            delay_execute_context,
#                          ):
#     return delay_execute_context._CreateCommandsImpl( None, # output_stream
#                                                       configuration,
#                                                       repositories,
#                                                       version_specs,
#                                                       generated_dir,
#                                                     )