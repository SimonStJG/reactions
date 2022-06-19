#!/usr/bin/env bash

set -eu

poetry run black --check reactions
poetry run isort --check reactions
poetry run pylint reactions
