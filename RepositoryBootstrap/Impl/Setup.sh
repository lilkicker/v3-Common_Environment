# ----------------------------------------------------------------------
# |  
# |  Setup.sh
# |  
# |  David Brownell <db@DavidBrownell.com>
# |      2018-05-10 23:23:57
# |  
# ----------------------------------------------------------------------
# |  
# |  Copyright David Brownell 2018.
# |  Distributed under the Boost Software License, Version 1.0.
# |  (See accompanying file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
# |  
# ----------------------------------------------------------------------
set -e                                      # Exit on error
set +v                                      # Disable output

pushd $1 > /dev/null                        # +repo_dir

# The following environment variables must be set prior to invoking this bash file:
#       - DEVELOPMENT_ENVIRONMENT_FUNDAMENTAL

# Create a temporary file that contains output produced by the python script. This lets us quickly bootstrap
# to the python environment while still executing OS-specific commands.
temp_script_name=`mktemp`

# Generate
export PYTHONPATH=$DEVELOPMENT_ENVIRONMENT_FUNDAMENTAL

python -m RepositoryBootstrap.Impl.Setup "$temp_script_name" "$@"
generation_error=$?

export PYTHONPATH=

# Invoke
if [[ -f $temp_script_name ]]
then
    chmod u+x $temp_script_name
    source $temp_script_name
fi
execution_error=$?

# Process errors...
if [[ $generation_error != 0 ]]
then 
    echo ""
    echo "ERROR: Errors were encountered and the repository has not been setup for development."
    echo ""
    echo "       [$DEVELOPMENT_ENVIRONMENT_FUNDAMENTAL\RepositoryBootstrap\Impl\Setup.py failed]"
    echo ""
    
    exit -1
fi

if [[ $execution_error != 0 ]]
then
    echo ""
    echo "ERROR: Errors were encountered and the repository has not been setup for development."
    echo ""
    echo "       [$temp_script_name failed]"
    echo ""

    exit -1
fi

# Success
rm $temp_script_name

echo "                    ^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^"
echo "                    <                                                                                                                                                   >"
echo "                    >   The repository has been setup for development. Please run Activate.sh within a new console window to begin development with this repository.    <"
echo "                    <                                                                                                                                                   >"
echo "                    v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v^v"
echo ""
echo ""

popd > /dev/null                            # -this_dir

exit 0
