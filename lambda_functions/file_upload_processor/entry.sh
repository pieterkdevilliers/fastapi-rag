#!/bin/sh

# If the handler is the first argument, run it
if [ -z "${AWS_LAMBDA_RUNTIME_API}" ]; then
  exec /usr/local/bin/python -m awslambdaric "$1"
else
  exec /usr/local/bin/python -m awslambdaric "$_HANDLER"
fi