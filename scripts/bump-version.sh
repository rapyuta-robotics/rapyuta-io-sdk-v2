#!/usr/bin/env bash
set -euo pipefail

VERSION="$1"

# Bump Version
sed "0,/__version__.*/s/__version__.*/__version__ = \"$VERSION\"/" -i rapyuta_io_sdk_v2/__init__.py
