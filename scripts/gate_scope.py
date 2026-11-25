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


def _is_repo(folder):
    """A folder whose `.git` is a git dir with HEAD, or a gitfile. Any other `.git` is not a repo."""
    marker = os.path.join(folder, ".git")
    if os.path.isdir(marker):
        return os.path.isfile(os.path.join(marker, "HEAD"))
    if os.path.isfile(marker):
        try:
            with open(marker, encoding="utf-8", errors="ignore") as handle:
                return handle.readline().startswith("gitdir:")
        except OSError:
            return False
    return False


@functools.lru_cache(maxsize=None)
def _repo_root_of_dir(folder):
    current = folder
    while True:
        if os.path.isdir(current) and _is_repo(current):
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


def _inside(path, folder):
    path, folder = _fold(os.path.normpath(path)), _fold(os.path.normpath(folder))
    return path == folder or path.startswith(folder.rstrip("\\/") + os.sep)


def _project_repo(project):
    anchor = os.environ.get("CLAUDE_PROJECT_DIR") or os.environ.get("DEVIN_PROJECT_DIR") or project
    return repo_root(os.path.realpath(anchor)) if anchor else None


def in_scope(full_path, project=None):
    """True when `full_path` is product code. `project` is the hook cwd; the project dir from the
    environment wins over it.

    The innermost repo decides, and its default with no config is "every code file". A repo at or
    below the project repo cannot narrow it: each of them gives the same default. A repo above the
    project repo has a say only through a committed config, so a folder of projects with no config,
    such as D:/code, never turns the gate on for its projects.
    """
    full_path = os.path.realpath(full_path)
    roots = _repo_chain(full_path)
    if not roots:
        return False
    project_root = _project_repo(project)
    for index, root in enumerate(roots):
        governs = index == 0 or (project_root is not None and _inside(root, project_root))
        if _verdict(root, full_path, needs_config=not governs):
            return True
    return False
