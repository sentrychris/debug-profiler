#!/usr/bin/env bash

cd ./bin || exit

source ./build.sh

cd ../

cd ./service || exit

source ./build.sh