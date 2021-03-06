# ----------------------------------------------------------------------
# |  
# |  DockerBuildImpl.py
# |  
# |  David Brownell <db@DavidBrownell.com>
# |      2018-06-02 20:13:29
# |  
# ----------------------------------------------------------------------
# |  
# |  Copyright David Brownell 2018.
# |  Distributed under the Boost Software License, Version 1.0.
# |  (See accompanying file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
# |  
# ----------------------------------------------------------------------
"""Functionality useful when creating docker-related build files"""

import inspect
import json
import os
import re
import sys
import textwrap
import time
import uuid

import six

from CommonEnvironment.CallOnExit import CallOnExit
from CommonEnvironment import CommandLine
from CommonEnvironment import FileSystem
from CommonEnvironment import Process
from CommonEnvironment.Shell.All import CurrentShell
from CommonEnvironment.SourceControlManagement.All import GetAnySCM
from CommonEnvironment.StreamDecorator import StreamDecorator

# ----------------------------------------------------------------------
_script_fullpath = os.path.abspath(__file__) if "python" in sys.executable.lower() else sys.executable
_script_dir, _script_name = os.path.split(_script_fullpath)
# ----------------------------------------------------------------------

# ----------------------------------------------------------------------
def CreateRepositoryBuildFunc( repository_name,
                               repository_uri,
                               docker_username,
                               docker_image_name,
                               base_docker_image,
                               maintainer,
                               no_now_tag=False,
                               no_activated_image=False,
                               repository_setup_configurations=None,
                               repository_activation_configurations=None,
                               repository_source_excludes=None,
                             ):
    """
    Creates a Build function that is able to build a docker image for Common_Environment-
    based repositories. To use this functionality, there must exist a dockerfile Jinja2 
    template with the variable {{repository_content}}. This template will be populated 
    with different values during the build process.
    """

    calling_dir = _GetCallingDir()
    repository_activation_configurations = repository_activation_configurations or [ None, ]

    image_username = "source_user"
    image_groupname = "source_users"

    docker_image_name = "{}{}".format( "{}/".format(docker_username) if docker_username else '',
                                       docker_image_name,
                                     )

    # ----------------------------------------------------------------------
    @CommandLine.EntryPoint
    @CommandLine.Constraints( output_stream=None,
                            )
    def Build( force=False,
               no_squash=False,
               keep_temporary_image=False,
               output_stream=sys.stdout,
               preserve_ansi_escape_sequences=False,
             ):
        with StreamDecorator.GenerateAnsiSequenceStream( output_stream,
                                                         preserve_ansi_escape_sequences=preserve_ansi_escape_sequences,
                                                       ) as output_stream:
            with StreamDecorator(output_stream).DoneManager( line_prefix='',
                                                             prefix="\nResults: ",
                                                             suffix='\n',
                                                           ) as dm:
                if not _VerifyDocker():
                    dm.stream.write("ERROR: Ensure that docker is installed and available within this environment.\n")
                    dm.result = -1

                    return dm.result

                output_dir = os.path.join(calling_dir, "Generated")

                source_dir = os.path.join(output_dir, "Source")
                base_image_dir = os.path.join(output_dir, "Images", "Base")
                activated_image_dir = os.path.join(output_dir, "Images", "Activated")

                image_code_base = "/usr/lib/CommonEnvironmentImage"
                image_code_dir = "{}/{}".format( image_code_base,
                                                 repository_name.replace('_', '/'),
                                               )

                if no_now_tag:
                    now_tag = None
                else:
                    now = time.localtime()
                    now_tag = "{0}.{1:02d}.{2:02d}".format(now[0], now[1], now[2])
                    
                # Create the base image
                dm.stream.write("Creating base image...")
                with dm.stream.DoneManager(suffix='\n') as base_dm:
                    FileSystem.MakeDirs(base_image_dir)

                    # Get the source
                    scm = GetAnySCM(calling_dir)
                    
                    if not os.path.isdir(source_dir):
                        base_dm.stream.write("Cloning source...")
                        with base_dm.stream.DoneManager() as this_dm:
                            # Ensure that the parent dir exists, but don't create the dir iteself.
                            FileSystem.MakeDirs(os.path.dirname(source_dir))
                    
                            # Enlist in the repo. 
                            temp_dir = CurrentShell.CreateTempDirectory()
                            FileSystem.RemoveTree(temp_dir)
                    
                            this_dm.result, output = scm.Clone(repository_uri, temp_dir)
                            if this_dm.result != 0:
                                this_dm.stream.write(output)
                                return this_dm.result
                    
                            os.rename(temp_dir, source_dir)
                    
                        has_changes = True
                    else:
                        # The repo exists
                        base_dm.stream.write("Updating source...")
                        with base_dm.stream.DoneManager() as this_dm:
                            this_dm.result, output = scm.Pull(source_dir)
                            if this_dm.result != 0:
                                this_dm.stream.write(output)
                                return this_dm.result
                    
                            has_changes = True
                    
                            if scm.Name == "Mercurial":
                                if "no changes found" in output:
                                    has_changes = False
                            elif scm.Name == "Git":
                                if "Already up-to-date" in output:
                                    has_changes = False
                            else:
                                assert False, "Unsupported SCM: {}".format(scm.Name)
                    
                            if has_changes:
                                this_dm.result, output = scm.Update(source_dir)
                                if this_dm.result != 0:
                                    this_dm.stream.write(output)
                                    return this_dm.result
                    
                    # Filter the source
                    filtered_source_dir = os.path.join(base_image_dir, "FilteredSource")

                    if os.path.isdir(filtered_source_dir) and not force and not has_changes:
                        base_dm.stream.write("No source changes were detected.\n")
                    else:
                        with base_dm.stream.SingleLineDoneManager( "Filtering source...",
                                                                 ) as this_dm:
                            temp_dir = CurrentShell.CreateTempDirectory()
                            FileSystem.RemoveTree(temp_dir)
                    
                            FileSystem.CopyTree( source_dir,
                                                 temp_dir,
                                                 excludes=[ "/.git",
                                                            "/.gitignore",
                                                            "/.hg",
                                                            "/.hgignore",
                    
                                                            "*/Generated",
                                                            "*/__pycache__",
                                                            "*/Windows",
                                                            "/*/src",
                    
                                                            "*.cmd",
                                                            "*.ps1",
                                                            "*.pyc",
                                                            "*.pyo",
                                                          ],
                                                 optional_output_stream=this_dm.stream,
                                               )
                    
                            FileSystem.RemoveTree(filtered_source_dir)
                    
                            os.rename(temp_dir, filtered_source_dir)
                    
                    base_dm.stream.write("Verifying Docker base image...")
                    with base_dm.stream.DoneManager() as this_dm:
                        this_dm.result, output = Process.Execute('docker image history "{}"'.format(base_docker_image))
                        if this_dm.result != 0:
                            this_dm.stream.write(output)
                            return this_dm.result
                    
                    base_dm.stream.write("Creating dockerfile...")
                    with base_dm.stream.DoneManager():
                        setup_statement = "./Setup.sh{}".format('' if not repository_setup_configurations else ' {}'.format(' '.join([ '"/configuration={}"'.format(configuration) for configuration in repository_setup_configurations ])))
                    
                        if repository_name == "Common_Environment":
                            commands = textwrap.dedent(
                                            """\
                                            RUN link /usr/bin/python3 /usr/bin/python
                    
                                            RUN adduser --disabled-password --disabled-login --gecos "" "{username}" \\
                                             && addgroup "{groupname}" \\
                                             && adduser "{username}" "{groupname}"
                    
                                            RUN cd {image_code_dir} \\
                                             && {setup_statement}
                    
                                            """).format( username=image_username,
                                                         groupname=image_groupname,
                                                         image_code_dir=image_code_dir,
                                                         setup_statement=setup_statement,
                                                       )
                        else:
                            import io
                    
                            with io.open( os.path.join(base_image_dir, "SetupEnvironmentImpl.sh"),
                                          'w',
                                          newline='\n',
                                        ) as f:
                                f.write(textwrap.dedent(
                                            """\
                                            #!/bin/bash
                                            . {image_code_base}/Common/Environment/Activate.sh python36
                                            cd {image_code_dir}
                                            {setup_statement}
                                            rm --recursive {image_code_base}/Common/Environment/Generated/Linux/Default
                                            """).format( image_code_base=image_code_base,
                                                         image_code_dir=image_code_dir,
                                                         setup_statement=setup_statement,
                                                       ))
                    
                            commands = textwrap.dedent(
                                            """\
                                            COPY SetupEnvironmentImpl.sh /tmp/SetupEnvironmentImpl.sh
                    
                                            RUN chmod a+x /tmp/SetupEnvironmentImpl.sh \\
                                             && /tmp/SetupEnvironmentImpl.sh
                                            """)
                    
                        with open(os.path.join(base_image_dir, "Dockerfile"), 'w') as f:
                            f.write(textwrap.dedent(
                                """\
                                FROM {base_image}
                    
                                COPY FilteredSource {image_code_dir}
                    
                                {commands}
                    
                                RUN chown -R {username}:{groupname} {image_code_dir} \\
                                 && chmod g-s {image_code_dir}/Generated/Linux \\
                                 && chmod 0750 {image_code_dir}/Generated/Linux \\
                                 && chmod -R o-rwx {image_code_dir}
                    
                                # Cleanup
                                RUN apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*
                    
                                LABEL maintainer="{maintainer}"
                    
                                # By default, run a bash prompt as the source code user
                                WORKDIR {image_code_dir}
                                CMD [ "/sbin/my_init", "/sbin/setuser", "{username}", "bash" ]
                    
                                """).format( base_image=base_docker_image,
                                             commands=commands,
                                             username=image_username,
                                             groupname=image_groupname,
                                             image_code_dir=image_code_dir,
                                             maintainer=maintainer,
                                           ))
                    
                    base_dm.stream.write("Building Docker image...")
                    with base_dm.stream.DoneManager() as this_dm:
                        tags = [ "base",
                                 "base_latest",
                               ]

                        if now_tag:
                            tags.append("base_{}".format(now_tag))

                        command_line = 'docker build "{dir}" {tags}{squash}{force}' \
                                            .format( dir=base_image_dir,
                                                     tags=' '.join([ '--tag "{}:{}"'.format(docker_image_name, tag) for tag in tags ]),
                                                     squash='' if no_squash else " --squash",
                                                     force=" --no-cache" if force else '',
                                                   )
                        this_dm.result = Process.Execute(command_line, this_dm.stream)
                        if this_dm.result != 0:
                            return this_dm.result
                    
                if not no_activated_image:
                    # Create the activated image(s)
                    dm.stream.write("Creating activated image(s)...")
                    with dm.stream.DoneManager() as all_activated_dm:
                        for index, configuration in enumerate(repository_activation_configurations):
                            all_activated_dm.stream.write("Creating activated image{} ({} of {})...".format( '' if not configuration else " for the configuration '{}'".format(configuration),
                                                                                                             index + 1,
                                                                                                             len(repository_activation_configurations),
                                                                                                           ))
                            with all_activated_dm.stream.DoneManager(suffix='\n') as activated_dm:
                                this_activated_dir = os.path.join(activated_image_dir, configuration or "Default")
                                FileSystem.MakeDirs(this_activated_dir)

                                unique_id = str(uuid.uuid4())

                                temp_image_name = "{}_image".format(unique_id)
                                temp_container_name = "{}_container".format(unique_id)

                                # Activate the image so we can extract the changes
                                activated_dm.stream.write("Activating...")
                                with activated_dm.stream.DoneManager(suffix='\n') as this_dm:
                                    command_line = 'docker run -it --name "{container_name}" "{image_name}:base_latest" /sbin/my_init -- /sbin/setuser "{username}" bash -c "cd {image_code_dir} && . ./Activate.sh {configuration} && pushd {image_code_base}/Common/Environment && python -m RepositoryBootstrap.EnvironmentDiffs After /decorate' \
                                                        .format( container_name=temp_container_name,
                                                                 image_name=docker_image_name,
                                                                 configuration=configuration or '',
                                                                 username=image_username,
                                                                 image_code_dir=image_code_dir,
                                                                 image_code_base=image_code_base,
                                                               )

                                    sink = six.moves.StringIO()

                                    this_dm.result = Process.Execute(command_line, StreamDecorator([ sink, this_dm.stream, ]))
                                    if this_dm.result != 0:
                                        return this_dm.result

                                    sink = sink.getvalue()

                                activated_dm.stream.write("Extracting enviroment diffs...")
                                with activated_dm.stream.DoneManager():
                                    match = re.search( textwrap.dedent(
                                                            """\
                                                            //--//--//--//--//--//--//--//--//--//--//--//--//--//--//--//
                                                            (?P<content>.+?)
                                                            //--//--//--//--//--//--//--//--//--//--//--//--//--//--//--//
                                                            """),
                                                       sink,
                                                       re.DOTALL | re.MULTILINE,
                                                     )
                                    assert match, sink

                                    environment_diffs = json.loads(match.group("content"))

                                # ----------------------------------------------------------------------
                                def RemoveTempContainer():
                                    activated_dm.stream.write("Removing temp container...")
                                    with activated_dm.stream.DoneManager() as this_dm:
                                        this_dm.result, output = Process.Execute('docker rm "{}"'.format(temp_container_name))
                                        if this_dm.result != 0:
                                            this_dm.stream.write(output)

                                # ----------------------------------------------------------------------

                                with CallOnExit(RemoveTempContainer):
                                    # Commit the activated image
                                    activated_dm.stream.write("Committing container...")
                                    with activated_dm.stream.DoneManager() as this_dm:
                                        command_line = 'docker commit "{container_name}" "{image_name}"' \
                                                            .format( container_name=temp_container_name,
                                                                     image_name=temp_image_name,
                                                                   )

                                        this_dm.result, output = Process.Execute(command_line)
                                        if this_dm.result != 0:
                                            this_dm.stream.write(output)
                                            return this_dm.result

                                    # ----------------------------------------------------------------------
                                    def RemoveTempImage():
                                        if keep_temporary_image:
                                            return

                                        activated_dm.stream.write("Removing temp image...")
                                        with activated_dm.stream.DoneManager() as this_dm:
                                            this_dm.result, output = Process.Execute('docker rmi "{}"'.format(temp_image_name))
                                            if this_dm.result != 0:
                                                this_dm.stream.write(output)

                                    # ----------------------------------------------------------------------

                                    with CallOnExit(RemoveTempImage):
                                        # Create a new dockerfile. The temp image has all the harddrive changes
                                        # made during activation, but doesn't have the environment changes.
                                        activated_dm.stream.write("Creating dockerfile...")
                                        with activated_dm.stream.DoneManager() as this_dm:
                                            with open(os.path.join(this_activated_dir, "Dockerfile"), 'w') as f:
                                                f.write(textwrap.dedent(
                                                    """\
                                                    FROM {temp_image_name}

                                                    ENV {env}

                                                    # By default, run a bash prompt as the source code user
                                                    CMD [ "/sbin/my_init", "/sbin/setuser", "{username}", "bash" ]

                                                    LABEL maintainer="{maintainer}"

                                                    """).format( temp_image_name=temp_image_name,
                                                                 env='\\\n'.join([ '  {}={} '.format(k, v) for k, v in six.iteritems(environment_diffs) ]),
                                                                 image_code_dir=image_code_dir,
                                                                 maintainer=maintainer,
                                                                 username=image_username,
                                                               ))

                                        activated_dm.stream.write("Building Docker image...")
                                        with activated_dm.stream.DoneManager() as this_dm:
                                            tags = [ "latest",
                                                   ]

                                            if now_tag:
                                                tags.append(now_tag)

                                            if len(repository_activation_configurations) > 1:
                                                tags = [ "{}_{}".format(configuration, tag) for tag in tags ]
                                                tags.insert(0, configuration)

                                            command_line = 'docker build "{dir}" {tags}{squash}{force}' \
                                                                .format( dir=this_activated_dir,
                                                                         tags=' '.join([ '--tag "{}:{}"'.format(docker_image_name, tag) for tag in tags ]),
                                                                         squash='', # <squash is not supported here> '' if no_squash else " --squash",
                                                                         force=" --no-cache" if force else '',
                                                                       )

                                            this_dm.result = Process.Execute(command_line, this_dm.stream)
                                            if this_dm.result != 0:
                                                return this_dm.result
                                
                return dm.result

    # ----------------------------------------------------------------------

    return Build

# ----------------------------------------------------------------------
def CreateRepositoryCleanFunc():
    calling_dir = _GetCallingDir()

    # ----------------------------------------------------------------------
    @CommandLine.EntryPoint
    @CommandLine.Constraints( output_stream=None,
                            )
    def Clean( output_stream=sys.stdout,
             ):
        """Cleans previously build content."""

        potential_dir = os.path.join(calling_dir, "Generated")

        if not os.path.isdir(potential_dir):
            output_stream.write("'{}' does not exist.\n".format(potential_dir))
        else:
            FileSystem.RemoveTree(potential_dir)
            output_stream.write("'{}' has been removed.\n".format(potential_dir))

        return 0

    # ----------------------------------------------------------------------

    return Clean

# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
def _GetCallingDir():
    frame = inspect.stack()[2]
    module = inspect.getmodule(frame[0])

    calling_dir = os.path.dirname(os.path.realpath(module.__file__))
    assert os.path.isdir(calling_dir), calling_dir

    return calling_dir

# ----------------------------------------------------------------------
def _VerifyDocker():
    result, output = Process.Execute("docker version")
    return "Client:" in output and "Server:" in output
