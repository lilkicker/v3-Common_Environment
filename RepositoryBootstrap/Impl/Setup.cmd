@REM ----------------------------------------------------------------------
@REM |  
@REM |  Setup.cmd
@REM |  
@REM |  David Brownell <db@DavidBrownell.com>
@REM |      2018-04-20 11:34:32
@REM |  
@REM ----------------------------------------------------------------------
@REM |  
@REM |  Copyright David Brownell 2018.
@REM |  Distributed under the Boost Software License, Version 1.0.
@REM |  (See accompanying file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
@REM |  
@REM ----------------------------------------------------------------------
@echo off

pushd %1

REM The following environment variables must be set prior to invoking this batch file:
REM     - DEVELOPMENT_ENVIRONMENT_FUNDAMENTAL

REM Create a temporary file that contains output produced by the python script. This lets us quickly bootstrap
REM to the python environment while still executing OS-specific commands.
call :CreateTempScriptName

REM Generate...
set PYTHONPATH=%DEVELOPMENT_ENVIRONMENT_FUNDAMENTAL%

%~dp0\..\..\Tools\Python\v3.6.5\Windows\python -m RepositoryBootstrap.Impl.Setup "%_SETUP_TEMP_SCRIPT_NAME%" %*
set _SETUP_GENERATION_ERROR_LEVEL=%ERRORLEVEL%

set PYTHONPATH=

REM Invoke...
if exist "%_SETUP_TEMP_SCRIPT_NAME%" (
    call %_SETUP_TEMP_SCRIPT_NAME%
)
set _SETUP_EXECUTION_ERROR_LEVEL=%ERRORLEVEL%

REM Process errors...
if %_SETUP_GENERATION_ERROR_LEVEL% NEQ 0 (
    @echo.
    @echo ERROR: Errors were encountered and the repository has not been setup for development.
    @echo.
    @echo        [%DEVELOPMENT_ENVIRONMENT_FUNDAMENTAL%\RepositoryBootstrap\Impl\Setup.py failed]
    @echo.

    goto ErrorExit
)

if %_SETUP_EXECUTION_ERROR_LEVEL% NEQ 0 (
    @echo.
    @echo ERROR: Errors were encountered and the repository has not been setup for development.
    @echo.
    @echo        [%_SETUP_TEMP_SCRIPT_NAME% failed]
    @echo.

    goto ErrorExit
)

REM Success
del %_SETUP_TEMP_SCRIPT_NAME%

@echo                     ^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^
@echo                     ^<                                                                                                                                                   ^>
@echo                     ^>   The repository has been setup for development. Please run Activate.cmd within a new console window to begin development with this repository.   ^<
@echo                     ^<                                                                                                                                                   ^>
@echo                     v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v^^v
@echo.
@echo.

set _SETUP_ERROR_LEVEL=0
goto Exit

@REM ----------------------------------------------------------------------
:ErrorExit
set _SETUP_ERROR_LEVEL=-1
goto Exit

@REM ----------------------------------------------------------------------
:Exit
set _SETUP_GENERATION_ERROR_LEVEL=
set _SETUP_EXECUTION_ERROR_LEVEL=
set _SETUP_TEMP_SCRIPT_NAME=

popd

exit /B %_SETUP_ERROR_LEVEL%

@REM ----------------------------------------------------------------------
@REM |  
@REM |  Internal Functions
@REM |  
@REM ----------------------------------------------------------------------
:CreateTempScriptName
setlocal EnableDelayedExpansion
set _filename=%~dp0Setup-!RANDOM!-!Time:~6,5!.cmd
endlocal & set _SETUP_TEMP_SCRIPT_NAME=%_filename%

if exist "%_SETUP_TEMP_SCRIPT_NAME%" goto :CreateTempScriptName
goto :EOF
