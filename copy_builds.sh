#!/bin/bash
parent_path=$( cd "$(dirname "${BASH_SOURCE[0]}")" ; pwd -P )

cd "$parent_path"

cp open-plc-utils/slac_python_module/slac_wrapper.so code/interface/slac_wrapper.so

cp libs/V2GDecoder/target/V2Gdecoder-jar-with-dependencies.jar schemas