# Testing plugin.video.netflix

This document describes how to set up an environment, run the unit test
suite, and reproduce the two lint gates that CI runs. It is the reference for
anyone changing the add-on's API layer.

## The unit test suite

The suite lives in `tests/unit/` and runs under [pytest](https://pytest.org).
It is a **pure-Python** suite: it exercises the API layer — request paths,
response parsing, directory requests, batch handling — with no Kodi instance,
no network and no database.

### Why stubs exist

None of `resources/lib/` can be imported outside Kodi, because the add-on
imports `xbmc`, `xbmcaddon`, `xbmcgui`, `xbmcplugin`, `xbmcvfs` and `xbmcdrm`
at module load time and calls into them immediately. Without a Kodi runtime
those imports raise `ModuleNotFoundError`, so *no* test could even be collected.

`tests/unit/kodi_stubs.py` therefore builds minimal stand-ins for exactly
those six modules and registers them in `sys.modules` before anything from
`resources.lib` is imported. `tests/unit/conftest.py` calls
`kodi_stubs.install()` at module level, which is why every test file gets the
stubs without any per-test setup. The stubs are deliberately inert: they return
empty values instead of talking to Kodi, because the tests only care about what
the API layer *builds*, not what Kodi would do with it.

The stubs also put the repository's own `tests/` directory on `sys.path`,
because `resources.lib.common.ipc` imports `AddonSignals` as a top-level
module and that file lives in `tests/`.

### What the suite covers — and what it does not

The stubs cover the **import surface of the API layer only**, not the whole
add-on. Importing the following under pytest fails today:

| Module | Fails with |
| ------ | ---------- |
| `resources/lib/services/playback/action_controller` | `AttributeError: type object 'Player' has no attribute 'setAudioStream'` |
| `resources/lib/services/playback/am_stream_continuity` | `AttributeError: type object 'Player' has no attribute 'setAudioStream'` |
| `resources/lib/database/db_base_mysql` | `ModuleNotFoundError: No module named 'mysql'` |
| `resources/lib/services/nfsession/msl/default_crypto` | `ModuleNotFoundError: No module named 'Crypto'` |

The playback modules fail because the `Player` stub is incomplete; the database
and MSL modules fail because they need real third-party dependencies
(`mysql-connector-python`, `pycryptodomex`) that the pytest environment does not
install. Extending coverage to those areas means growing the stubs or adding
those dependencies to `[testenv:pytest]` in `tox.ini` — it is not automatic.

### The other test tooling

`tests/run.py` and `tests/update_translations.py` are **not** part of this
suite. They are runtime scripts exercised through `make test-run` against a
live Kodi with a MySQL backend, and they are not collected by pytest.

## Setting up the environment

The suite needs Python 3.10 or newer — that is the floor declared by
`min-version = 3.10` in `tox.ini` and the lowest version in the CI matrix
(3.10, 3.11, 3.12, 3.13). The suite itself was developed and last verified on
Python 3.13.15.

```bash
python3 -m venv /tmp/nfvenv
/tmp/nfvenv/bin/pip install --upgrade pip
/tmp/nfvenv/bin/pip install pytest requests flake8 pylint
```

`pytest` and `requests` are what `[testenv:pytest]` declares. `flake8` and
`pylint` are added by hand for the lint gates described below.

### Extra packages needed for the full pylint gate

The pylint gate that CI runs covers `resources/lib/` and `tests/`, which
imports three packages the pytest environment does not need. They are all in
`requirements.txt`, which is what CI installs:

* `Kodistubs==19.0.3` — supplies `xbmc`, `xbmcaddon`, `xbmcgui`, `xbmcplugin`,
  `xbmcvfs`, `xbmcdrm`
* `polib` — used by `tests/update_translations.py`
* `mysql-connector-python` — supplies `mysql.connector`

Skipping them is fine for the unit tests, but the full pylint gate will then
report 75 `E0401 import-error` messages and score 9.65/10. See
[Which gate can actually fail a build](#which-gate-can-actually-fail-a-build).

## Running the suite

`tox.ini` holds a `[pytest]` section, so pytest picks it up as its
configuration file automatically. No `PYTHONPATH` is needed — pytest resolves
the `resources.lib` and `tests.unit` packages from the repository root.

```bash
/tmp/nfvenv/bin/python -m pytest tests/unit -v
```

Expected result:

```
55 passed
```

The equivalent through tox, which builds its own throwaway environment
(`tox` is declared in `requirements.txt` but is **not** installed in
`/tmp/nfvenv`, so this form only works after `pip install tox`):

```bash
python -m tox -e pytest
```

`[testenv:pytest]` in `tox.ini` declares `pytest` and `requests` as its
dependencies and runs `{envbindir}/python -m pytest tests/unit -v`. That
command has **no** leading `-`, so a test failure does fail the env.

## Running the lint gates

### flake8 (advisory)

```bash
/tmp/nfvenv/bin/python -m flake8 --max-line-length=160 \
    --ignore=E129,E402,F401,F403,FI13,FI50,FI51,FI53,FI54,W503,W504 .
```

The flags repeat the `[flake8]` section of `tox.ini`; run them explicitly if
you invoke flake8 directly rather than through tox. On the current tree this
reports **22 pre-existing findings** (21 in `resources/lib/`, 1 in
`tests/inputstreamhelper.py`) — mostly `E302`, `E261` and `E251` style nits in
files this project has carried for a long time. Read them, but do not treat a
non-empty list as a regression.

### pylint (the gate that bites)

```bash
/tmp/nfvenv/bin/python -m pylint tests/unit
```

This is what you should run while working on the API layer. It is expected to
report 10.00/10.

For the full CI-parity gate you need the three packages above *and* the
`PYTHONPATH` that `.github/workflows/ci.yml` sets, which puts the repository's
own `tests/` directory on the import path for `AddonSignals` and
`inputstreamhelper`:

```bash
PYTHONPATH="$PWD/resources/lib:$PWD/tests" /tmp/nfvenv/bin/python -m pylint resources/lib/ tests/
```

With `polib`, `Kodistubs==19.0.3` and `mysql-connector-python` installed this
reports 10.00/10. Without the `PYTHONPATH` it reports 9.99/10 with three
`E0401` messages for `AddonSignals` and `inputstreamhelper`.

If you want a quick lint signal without installing those packages, disable the
import check rather than reading through the noise:

```bash
/tmp/nfvenv/bin/python -m pylint resources/lib tests/unit --disable=E0401
```

This also reports 10.00/10. It is a weaker check than the full gate — it simply
stops reporting names it cannot resolve — but it is honest about the code it
*can* see.

## Which gate can actually fail a build

**pylint is the gate that bites. flake8 is advisory.**

`.github/workflows/ci.yml` runs flake8 through `tox`, and the command in
`tox.ini` is prefixed with a dash:

```ini
[testenv:flake8]
commands =
    - {envbindir}/flake8
```

The leading `-` tells tox to *ignore the exit code*. flake8 prints its 22
findings and exits 1, tox prints `congratulations :)` and exits 0. This was
confirmed by running `tox -e flake8` on this tree: the findings appear in the
output and the env is reported `OK`. `[testenv:pytest]` deliberately has no such
dash, so the pytest env does report failures.

Two consequences worth knowing:

* Do not read a green `flake8` CI step as "the project is flake8-clean". It is
  not, and the CI badge will not tell you.
* If you want flake8 to actually gate, remove the `-` from `tox.ini:9` and fix
  the 22 findings first. That is out of scope for the API-layer work and was
  deliberately left alone.

The `py310`, `py311`, `py312` and `py313` envs in `envlist` declare no
commands at all, so they only verify that the interpreter is available — they
run no tests. The real checks are the `pytest` env and the standalone pylint
step.

## Test and production code are separate

Production code must never import the test harness. This is enforced by
inspection and should stay that way:

```bash
grep -rn "kodi_stubs\|tests.unit" resources/lib/ --include="*.py"
```

Expected output: nothing.

## Summary

| Check | Command | Result |
| ----- | ------- | ------ |
| Unit tests | `python -m pytest tests/unit -v` | 55 passed |
| pylint, unit scope | `python -m pylint tests/unit` | 10.00/10 |
| pylint, CI parity | `PYTHONPATH="$PWD/resources/lib:$PWD/tests" python -m pylint resources/lib/ tests/` | 10.00/10, needs `polib` + `Kodistubs` + `mysql-connector-python` |
| flake8 | `python -m flake8 --max-line-length=160 --ignore=E129,E402,F401,F403,FI13,FI50,FI51,FI53,FI54,W503,W504 .` | 22 pre-existing findings, advisory only |