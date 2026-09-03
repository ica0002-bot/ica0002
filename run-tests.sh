#!/bin/sh -eu

if ! ~/ansible-venv/bin/pip freeze | grep -q ^pytest; then
	echo "Installing test packages..."
	~/ansible-venv/bin/pip install pytest pytest-testinfra
fi

echo "Downloading test cases..."
curl -s https://raw.githubusercontent.com/ica0002-bot/ica0002/refs/heads/main/test_all.py > test_all.py
git diff test_all.py

~/ansible-venv/bin/pytest -rA --tb=no
