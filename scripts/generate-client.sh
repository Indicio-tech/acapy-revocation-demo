#!/usr/bin/env bash

cd "$(dirname "$0")" || exit

CONTAINER_RUNTIME=${CONTAINER_RUNTIME:-docker}

${CONTAINER_RUNTIME} build -t openapi-generator -f ../docker/Dockerfile.openapi-generator ..

${CONTAINER_RUNTIME} run --rm \
    -v "$(realpath "$PWD/../"):/usr/src/app:z" \
    openapi-generator "$@"
