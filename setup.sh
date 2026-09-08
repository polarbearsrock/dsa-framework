#!/bin/bash
DIR="$( cd "$( dirname "${BASH_SOURCE[0]:-$0}" )" >/dev/null 2>&1 && pwd )"
export MAKEFLAGS="-j$(($(nproc) - 2))"

# Make sure conda is installed
if ! command -v conda &> /dev/null
then

  echo "conda could not be found. Please install conda package or 3rd-party like anaconda first"

else

  echo "set SS="$DIR
  export SS=$DIR

  echo "set SS_STACK="$DIR
  export SS_STACK=$SS

  echo "set SS_TOOLS="$DIR/ss-tools
  export SS_TOOLS=$SS_STACK/ss-tools

  FILE=$SS/chipyard/env.sh
  if test -f "$FILE"; then
    echo source chipyard environment script
    source $SS/chipyard/env.sh
  fi

  echo add "$"SS_TOOLS/bin to "$"PATH
  export PATH=$SS_TOOLS/bin:$PATH
  echo add "$"RISCV/bin to "$"PATH
  export PATH=$RISCV/bin:$PATH
  echo add gem5 to "$"PATH
  export PATH=$SS/dsa-gem5/build/RISCV:$PATH

  echo add "$"SS_TOOLS/lib to "$"LD_LIBRARY_PATH
  export PATH=$SS/scripts:$PATH
  export LD_LIBRARY_PATH=$SS_TOOLS/lib64:$SS_TOOLS/lib:$SS/dsa-scheduler/3rd-party/libtorch/lib/${LD_LIBRARY_PATH:+":${LD_LIBRARY_PATH}"}

  SS_CONDA_ENV="$SS_TOOLS/conda-envs/ss-stack"
  if [ ! -d "$SS_CONDA_ENV/conda-meta" ]; then
    echo "ss-stack environment not found"
    conda env create --prefix "$SS_CONDA_ENV" -f "$SS/ss-stack-conda-env.yml"
  fi
  conda activate "$SS_CONDA_ENV"

  export LD_LIBRARY_PATH=${CONDA_PREFIX}/lib:${LD_LIBRARY_PATH}

fi

# Support macOS compilation
case "$OSTYPE" in
  solaris*) echo "SOLARIS" ;;
  darwin*)
	# Change flex version
	export PATH="/opt/homebrew/opt/flex/bin:$PATH"
	export LDFLAGS="-L/opt/homebrew/opt/flex/lib"
	export CPPFLAGS="-I/opt/homebrew/opt/flex/include"
	# Change bison version
	export PATH="/opt/homebrew/opt/bison/bin:$PATH"
	export LDFLAGS="-L/opt/homebrew/opt/bison/lib"
	echo "Switch Flex and Bison to Homebrew version" ;;
  linux*)   echo "OS Type is Linux, Not need to switch Bison and Flex" ;;
  bsd*)     echo "BSD" ;;
  msys*)    echo "WINDOWS" ;;
  cygwin*)  echo "ALSO WINDOWS" ;;
  *)        echo "unknown: $OSTYPE" ;;
esac
