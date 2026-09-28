#!/bin/sh

python_command=$1
shift

if "$@" > /tmp/vwc-setup.log 2>&1; then
    cat /tmp/vwc-setup.log
else
    cat /tmp/vwc-setup.log
    printf '::error title=BSD setup failure::%s\n' "$(tail -c 5000 /tmp/vwc-setup.log | tr '\n' ' ')"
    exit 1
fi

if "$python_command" -m venv /tmp/vwc-venv > /tmp/vwc-venv.log 2>&1; then
    cat /tmp/vwc-venv.log
else
    cat /tmp/vwc-venv.log
    printf '::error title=BSD venv failure::%s\n' "$(tail -c 5000 /tmp/vwc-venv.log | tr '\n' ' ')"
    exit 1
fi

if /tmp/vwc-venv/bin/python -m pip install -e . pytest > /tmp/vwc-pip.log 2>&1; then
    cat /tmp/vwc-pip.log
else
    cat /tmp/vwc-pip.log
    printf '::error title=BSD pip failure::%s\n' "$(tail -c 5000 /tmp/vwc-pip.log | tr '\n' ' ')"
    exit 1
fi

if /tmp/vwc-venv/bin/python -m pytest -q -x --tb=short tests/test_local_reference.py > /tmp/vwc-tests.log 2>&1; then
    cat /tmp/vwc-tests.log
else
    cat /tmp/vwc-tests.log
    printf '::error title=BSD reference failure::%s\n' "$(tail -c 5000 /tmp/vwc-tests.log | tr '\n' ' ')"
    exit 1
fi
