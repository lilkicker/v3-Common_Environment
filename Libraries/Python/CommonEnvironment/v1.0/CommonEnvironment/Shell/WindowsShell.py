# ----------------------------------------------------------------------
# |  
# |  WindowsShell.py
# |  
# |  David Brownell <db@DavidBrownell.com>
# |      2018-04-30 21:12:38
# |  
# ----------------------------------------------------------------------
# |  
# |  Copyright David Brownell 2018.
# |  Distributed under the Boost Software License, Version 1.0.
# |  (See accompanying file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
# |  
# ----------------------------------------------------------------------
"""Contains the WindowsShell object."""

import os
import sys
import textwrap

from CommonEnvironment.Interface import staticderived, clsinit
from CommonEnvironment.Shell import Shell
from CommonEnvironment.Shell.Commands import Set, Augment
from CommonEnvironment.Shell.Commands.Visitor import Visitor

# ----------------------------------------------------------------------
_script_fullpath = os.path.abspath(__file__) if "python" in sys.executable.lower() else sys.executable
_script_dir, _script_name = os.path.split(_script_fullpath)
# ----------------------------------------------------------------------

@staticderived
@clsinit
class WindowsShell(Shell):

    # ----------------------------------------------------------------------
    # |  
    # |  Public Types
    # |  
    # ----------------------------------------------------------------------
    @staticderived
    class CommandVisitor(Visitor):

        # <Parameters differ from overridden '<...>' method> pylint: disable = W0221

        # ----------------------------------------------------------------------
        @staticmethod
        def OnComment(command):
            return "REM {}".format(command.Value)

        # ----------------------------------------------------------------------
        @staticmethod
        def OnMessage(command):
            replacement_chars = [ ( '%', '%%' ),
                                  ( '^', '^^' ),
                                  ( '&', '^&' ),
                                  ( '<', '^<' ),
                                  ( '>', '^>' ),
                                  ( '|', '^|' ),
                                  ( ',', '^,' ),
                                  ( ';', '^;' ),
                                  ( '(', '^(' ),
                                  ( ')', '^)' ),
                                  ( '[', '^[' ),
                                  ( ']', '^]' ),
                                  ( '"', '\"' ),
                                ]
                                
            output = []
            
            for line in command.Value.split('\n'):
                if not line.strip():
                    output.append("echo.")
                else:
                    for old_char, new_char in replacement_chars:
                        line = line.replace(old_char, new_char)
                        
                    output.append("echo {}".format(line))
                    
            return '\n'.join(output)

        # ----------------------------------------------------------------------
        @staticmethod
        def OnCall(command):
            return "call {}".format(command.CommandLine)

        # ----------------------------------------------------------------------
        @staticmethod
        def OnExecute(command):
            return command.CommandLine

        # ----------------------------------------------------------------------
        @staticmethod
        def OnSymbolicLink(command):
            d = { "link" : command.LinkFilename,
                  "target" : command.Target,
                }

            return textwrap.dedent(
                """\
                {remove}mklink{dir_flag} "{link}" "{target}" > NUL
                """).format( remove='' if not command.RemoveExisting else 'if exist "{link}" ({remove} "{link}")\n'.format( remove="rmdir" if command.IsDir else "del /Q",
                                                                                                                            **d
                                                                                                                          ),
                             dir_flag=" /D /J" if command.IsDir else '',
                             **d
                           )

        # ----------------------------------------------------------------------
        @classmethod
        def OnPath(cls, command):
            return cls.OnSet(Set("PATH", command.Values))

        # ----------------------------------------------------------------------
        @classmethod
        def OnAugmentPath(cls, command):
            return cls.OnAugment(Augment("PATH", command.Values))

        # ----------------------------------------------------------------------
        @staticmethod
        def OnSet(command):
            if command.Values is None:
                return "SET {}=".format(command.Name)

            assert command.Values

            return "SET {}={}".format(command.Name, WindowsShell.EnvironmentVariableDelimiter.join(command.Values))

        # ----------------------------------------------------------------------
        @classmethod
        def OnAugment(cls, command):
            if not command.Values:
                return None

            current_values = set(WindowsShell.EnumEnvironmentVariable(command.Name))
            
            new_values = [ value.strip() for value in command.Values if value.strip() ]
            new_values = [ value for value in new_values if value not in current_values ]

            if not new_values:
                return None

            return "SET {name}={values};%{name}%".format( name=command.Name,
                                                          values=WindowsShell.EnvironmentVariableDelimiter.join(command.Values),
                                                        )
            
        # ----------------------------------------------------------------------
        @staticmethod
        def OnExit(command):
            return textwrap.dedent(
                """\
                {success}
                {error}
                exit /B {return_code}
                """).format( success="if %ERRORLEVEL% EQ 0 ( pause )" if command.PauseOnSuccess else '',
                             error="if %ERRORLEVEL% NEQ 0 ( pause )" if command.PauseOnError else '',
                             return_code=command.ReturnCode or 0,
                           )

        # ----------------------------------------------------------------------
        @staticmethod
        def OnExitOnError(command):
            return "if %ERRORLEVEL% NEQ 0 (exit /B {})".format(command.ReturnCode or "%ERRORLEVEL%")

        # ----------------------------------------------------------------------
        @staticmethod
        def OnRaw(command):
            return command.Value

        # ----------------------------------------------------------------------
        @staticmethod
        def OnEchoOff(command):
            return "@echo off"

        # ----------------------------------------------------------------------
        @staticmethod
        def OnCommandPrompt(command):
            return "set PROMPT=({}) $P$G".format(command.Prompt)

        # ----------------------------------------------------------------------
        @staticmethod
        def OnDelete(command):
            if command.IsDir:
                return 'rmdir /S /Q "{}"'.format(command.FilenameOrDirectory)
            
            return 'del "{}"'.format(command.FilenameOrDirectory)

        # ----------------------------------------------------------------------
        @staticmethod
        def OnCopy(command):
            return 'copy /T "{source}" "{dest}"'.format( source=command.Source,
                                                         dest=command.Dest,
                                                       )

        # ----------------------------------------------------------------------
        @staticmethod
        def OnMove(command):
            return 'move /Y "{source}" "{dest}"'.format( source=command.Source,
                                                         dest=command.Dest,
                                                       )

    # ----------------------------------------------------------------------
    # |  
    # |  Public Properties
    # |  
    # ----------------------------------------------------------------------
    Name                                    = "Windows"
    CategoryName                            = "Windows"
    ScriptExtension                         = ".cmd"
    ExecutableExtension                     = ".exe"
    CompressionExtensions                   = [ ".zip", ]
    AllArgumentsScriptVariable              = "%*"
    EnvironmentVariableDelimiter            = ";"
    HasCaseSensitiveFileSystem              = False
    Architecture                            = "x64" if os.getenv("ProgramFiles(x86)") else "x86"
    UserDirectory                           = None      # Set in __clsinit__
    TempDirectory                           = os.getenv("TMP")

    # ----------------------------------------------------------------------
    # |  
    # |  Public Methods
    # |  
    # ----------------------------------------------------------------------
    @classmethod
    def __clsinit__(cls):
        try:
            from win32com.shell import shellcon, shell      # <Unable to import> pylint: disable = F0401, E0611
            import unicodedata
            
            homedir = shell.SHGetFolderPath(0, shellcon.CSIDL_APPDATA, 0, 0)
            homedir = unicodedata.normalize("NFKD", homedir)
            
            if sys.version_info[0] == 2:
                homedir = homedir.encode("ascii", "ignore")

            cls.UserDirectory               = homedir

        except:
            cls.UserDirectory               = None

    # ----------------------------------------------------------------------
    @staticmethod
    def IsActive(platform_name):
        return "windows" in platform_name or platform_name == "nt"

    # ----------------------------------------------------------------------
    @staticmethod
    def RemoveDir(path):
        if os.path.isdir(path):
            os.system('rmdir /S /Q "{}"'.format(path))

    # ----------------------------------------------------------------------
    @staticmethod
    def IsSymLink(filename):
        import win32file

        # <Module 'win32file' has not 'GetFileAttributes' member, but source is unavailable. Consider adding this module to extension-pkg-whitelist if you want to perform analysis based on run-time introspection of living objects.> pylint: disable = I1101

        file_attribute_reparse_point = 1024
    
        return os.path.exists(filename) and win32file.GetFileAttributes(filename) & file_attribute_reparse_point == file_attribute_reparse_point

    # ----------------------------------------------------------------------
    if sys.version_info[0] == 2:
        # Python 2.+ doesn't support symlinks on Windows, so we have to provide 
        # much of its functionality manually.

        # ----------------------------------------------------------------------
        @classmethod
        def ResolveSymLink(cls, filename):
            # Python 2.+ doesn't support symlinks on Windows and there doesn't seem to be
            # a way to resolve a symlink without parsing the file, and libraries mentioned
            # http://stackoverflow.com/questions/1447575/symlinks-on-windows/7924557#7924557
            # and https://github.com/sid0/ntfs seem to have problems. The only way I have found
            # to reliabaly get this info is to parse the output of 'dir' and extact the info.
            # This is horribly painful code.
            
            import re

            # <No name in module> pylint: disable = E0611
            # <Unable to import> pylint: disable = F0401
            import six.moves.cPickle as pickle          

            from CommonEnvironment import Process

            filename = filename.replace('/', os.path.sep)

            assert cls.IsSymLink(filename)

            if not hasattr(cls, "_symlink_lookup"):
                cls._symlink_lookup = {}                # <Attribute defined outside __init__> pylint: disable = W0201
                cls._symlink_redirection_maps = {}      # <Attribute defined outside __init__> pylint: disable = W0201

            if filename in cls._symlink_lookup:
                return cls._symlink_lookup[filename]

            # Are there any redirection maps that reside in the filename's path?
            path = os.path.split(filename)[0]
            while True:
                potential_map_filename = os.path.join(path, "symlink.redirection_map")
                if os.path.isfile(potential_map_filename):
                    if potential_map_filename not in cls._symlink_redirection_maps:
                        cls._symlink_redirection_maps[potential_map_filename] = pickle.loads(open(potential_map_filename).read())

                    if filename in cls._symlink_redirection_maps[potential_map_filename]:
                        return cls._symlink_redirection_maps[potential_map_filename][filename]

                new_path = os.path.split(path)[0]
                if new_path == path:
                    break

                path = new_path

            # If here, there isn't a map filename so we have to do things the hard way.
            if os.path.isfile(filename):
                command_line = 'dir /AL "%s"' % filename
                is_match = lambda name: True
            else:
                command_line = 'dir /AL "%s"' % os.path.dirname(filename)
                is_match = lambda name: name == os.path.basename(filename)

            result, output = Process.Execute(command_line)
            assert result == 0

            regexp = re.compile(r".+<(?P<type>.+?)>\s+(?P<link>.+?)\s+\[(?P<filename>.+?)\]\s*")

            for line in output.split('\n'):
                match = regexp.match(line)
                if match:
                    link = match.group("link")
                    if not is_match(link):
                        continue

                    target_filename = match.group("filename")
                    assert os.path.exists(target_filename), target_filename

                    cls._symlink_lookup[filename] = target_filename
                    return target_filename

            assert False, output

        # ----------------------------------------------------------------------
        @classmethod
        def DeleteSymLink(cls, filename, command_only=False):
            assert cls.IsSymLink(filename), filename
        
            if os.path.isdir(filename):
                command_line = 'rmdir "{}"'.format(filename)
            elif os.path.isfile(filename):
                command_line = 'del /Q "{}"'.format(filename)
            else:
                assert False, filename

            if command_only:
                return command_line
                
            os.system(command_line)
            return None
