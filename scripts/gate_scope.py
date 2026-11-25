"""Decide whether a file the agent writes is product code that the edit gate covers.

A file is product code when it sits in a git repo, matches a `scope` glob of the nearest
`.fe-kit/config.yaml` between the file and the repo root (every file, when that config sets no
`scope` or there is none), and matches no `exclude` glob of that config. Globs are relative to the
folder that holds the config, so each package of a monorepo can keep its own.

The config and the tracked-file list come from the HEAD commit, not from the disk, so a config
written on disk changes nothing until it is committed. The path is resolved with realpath first. A
repo nested in another repo cannot narrow it: when an outer repo's committed config calls the file
product code, the gate stays on. A file in no repo, such as a scratchpad script, is not product code.
A config or a git call that fails keeps the gate on.
"""
import functools
import os
import subprocess

import project_config

CONFIG_SUFFIX = project_config.CONFIG_PATH


@functools.lru_cache(maxsize=None)
def _repo_root_of_dir(folder):
    current = folder
    while True:
        if os.path.isdir(current) and os.path.exists(os.path.join(current, ".git")):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            return None
        current = parent


def repo_root(path):
    """The nearest folder at or above `path` that holds `.git`, or None. `path` need not exist."""
    return _repo_root_of_dir(os.path.abspath(path))


def _git(root, *args):
    try:
        return subprocess.run(["git", "-C", root, "-c", "core.quotepath=off", *args], capture_output=True,
                              text=True, encoding="utf-8", errors="replace", timeout=30, check=True).stdout
    except subprocess.CalledProcessError:
        return None
    except (OSError, subprocess.SubprocessError) as exc:
        raise project_config.ConfigError("git failed in %s: %s" % (root, exc))


@functools.lru_cache(maxsize=None)
def _head_files(root):
    """Repo-relative paths in the HEAD commit, or () when the repo has no commit yet."""
    out = _git(root, "ls-tree", "-r", "-z", "--name-only", "HEAD")
    return tuple(path for path in (out or "").split("\0") if path)


@functools.lru_cache(maxsize=None)
def _config_dirs(root):
    dirs = set()
    for path in _head_files(root):
        if path == CONFIG_SUFFIX or path.endswith("/" + CONFIG_SUFFIX):
            dirs.add(path[: -len(CONFIG_SUFFIX)].rstrip("/"))
    return dirs


def _fold(text):
    return text.lower() if os.name == "nt" else text


def _config_dir(root, relative_dir):
    """The repo-relative folder of the nearest committed config at or above `relative_dir`, or None."""
    dirs = {_fold(folder): folder for folder in _config_dirs(root)}
    current = relative_dir.strip("/") if relative_dir not in (".", "") else ""
    while True:
        if _fold(current) in dirs:
            return dirs[_fold(current)]
        if not current:
            return None
        current = current.rpartition("/")[0]


@functools.lru_cache(maxsize=None)
def _config(root, folder):
    """The committed config in repo-relative `folder`. A `scope` pattern that matches no committed
    file under `folder` is a config error, because it would turn the gate off for every file."""
    prefix = folder + "/" if folder else ""
    text = _git(root, "show", "HEAD:" + prefix + CONFIG_SUFFIX)
    if text is None:
        raise project_config.ConfigError("cannot read %s%s at HEAD" % (prefix, CONFIG_SUFFIX))
    config = project_config.parse_config(text)[0]
    if not config["scope"]:
        return config
    files = [path[len(prefix):] for path in _head_files(root) if path.startswith(prefix)]
    for pattern in config["scope"]:
        if not any(project_config.matches(pattern, path) for path in files):
            raise project_config.ConfigError("`scope` pattern %r matches no committed file" % pattern)
    return config


def _repo_chain(path):
    """Every repo root that holds `path`, innermost first."""
    roots = []
    current = repo_root(path)
    while current is not None:
        roots.append(current)
        parent = os.path.dirname(current)
        current = repo_root(parent) if parent != current else None
    return roots


def _verdict(root, full_path, needs_config):
    """True or False for `full_path` under the committed config of `root`. None when `needs_config`
    is set and no committed config covers the file, so the repo has no say."""
    try:
        relative = project_config.normalize(root, full_path)
        folder = _config_dir(root, os.path.dirname(relative))
        if folder is None:
            if needs_config:
                return None
            config, inner = None, relative
        else:
            config = _config(root, folder)
            inner = relative[len(folder) + 1:] if folder else relative
    except project_config.ConfigError:
        return True
    if project_config.exclude_hit(config, inner):
        return False
    scope = config["scope"] if config else []
    return not scope or any(project_config.matches(_fold(pattern), _fold(inner)) for pattern in scope)


def in_scope(full_path):
    # realpath follows junctions, symlinks and 8.3 names, so another name for a folder cannot hide it.
    full_path = os.path.realpath(full_path)
    roots = _repo_chain(full_path)
    if not roots:
        return False
    if _verdict(roots[0], full_path, needs_config=False):
        return True
    # A repo inside another repo cannot narrow the outer repo: an outer repo whose committed config
    # calls the file product code keeps the gate on.
    return any(_verdict(root, full_path, needs_config=True) for root in roots[1:])
