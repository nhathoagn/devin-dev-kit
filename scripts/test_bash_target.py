"""Tests for bash_target.py: write_target() detects which product-code file a Bash command writes.

Every fixture runs inside a real temp git repo under /tmp because gate_scope.in_scope() only treats
a path as product code when a repo contains it. A command whose target cannot be known returns a
"(...)" pseudo-path marker so the gate stays on; that marker is a passing result, never "".
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bash_target
import gate_scope


def _clear_scope_caches():
    for name in ("_repo_root_of_dir", "_head_files", "_config_dirs", "_config"):
        getattr(gate_scope, name).cache_clear()


class WriteTargetCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="bash_target_test_")
        self.root = os.path.join(self.tmp, "repo")
        os.makedirs(os.path.join(self.root, "src"))
        for relative in ("app.tsx", os.path.join("src", "a.tsx"), os.path.join("src", "App.tsx")):
            with open(os.path.join(self.root, relative), "w") as handle:
                handle.write("const x = 1\n")
        subprocess.run(["git", "-C", self.root, "init", "-q"], check=True)
        subprocess.run(["git", "-C", self.root, "add", "-A"], check=True)
        subprocess.run(["git", "-C", self.root, "-c", "user.email=t@t", "-c", "user.name=t",
                        "commit", "-q", "-m", "init"], check=True)
        self._env = {key: os.environ.pop(key, None)
                     for key in ("CLAUDE_PROJECT_DIR", "DEVIN_PROJECT_DIR")}
        _clear_scope_caches()

    def tearDown(self):
        for key, value in self._env.items():
            if value is not None:
                os.environ[key] = value
        _clear_scope_caches()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def w(self, command, cwd=None):
        return bash_target.write_target(command, self.root if cwd is None else cwd)

    def path(self, relative):
        return os.path.join(self.root, relative)

    def write_script(self, name, text):
        script = os.path.join(self.tmp, name)
        with open(script, "w") as handle:
            handle.write(text)
        return script

    def assertWrites(self, command, relative):
        self.assertEqual(self.path(relative), self.w(command))

    def assertGated(self, command):
        """The write is a real path or an unknown-write marker; "" would run the command free."""
        self.assertNotEqual("", self.w(command))


class RedirectWrites(WriteTargetCase):
    def test_write_absolute(self):
        self.assertWrites("echo x > %s" % self.path("app.tsx"), "app.tsx")

    def test_append_absolute(self):
        self.assertWrites("echo x >> %s" % self.path("app.tsx"), "app.tsx")

    def test_cat_redirect(self):
        self.assertWrites("cat a > %s" % self.path("app.tsx"), "app.tsx")

    def test_redirect_relative_joined_with_cwd(self):
        self.assertWrites("echo x > app.tsx", "app.tsx")

    def test_redirect_after_cd_joined_with_cd_folder(self):
        self.assertWrites("cd %s && echo x > src/a.tsx" % self.root,
                          os.path.join("src", "a.tsx"))

    def test_redirect_after_cd_out_of_scope(self):
        self.assertEqual("", self.w("cd /tmp && echo x > app.tsx"))

    def test_redirect_to_non_code_extension(self):
        self.assertEqual("", self.w("echo x > %s" % self.path("out.txt")))

    def test_redirect_target_inside_quotes_is_text(self):
        self.assertEqual("", self.w('echo "a > b.tsx"'))

    def test_redirect_target_from_assigned_variable(self):
        self.assertWrites("F=src/app.tsx; echo x > $F", os.path.join("src", "app.tsx"))

    def test_redirect_target_unassigned_variable_is_unknown_marker(self):
        target = self.w('echo x > "$F"')
        self.assertTrue(target.startswith("("), target)

    def test_redirect_after_two_cds_is_gated_unknown(self):
        self.assertGated("cd a; cd b; echo x > src/app.tsx")

    def test_redirect_inside_subshell_is_gated_unknown(self):
        self.assertGated("(cd /tmp; echo x > app.tsx)")


class TeeAndInplace(WriteTargetCase):
    def test_tee(self):
        self.assertWrites("echo x | tee %s" % self.path("app.tsx"), "app.tsx")

    def test_tee_append_flag(self):
        self.assertWrites("echo x | tee -a %s" % self.path("app.tsx"), "app.tsx")

    def test_sed_in_place(self):
        self.assertWrites("sed -i s/x/y/ %s" % self.path("app.tsx"), "app.tsx")

    def test_sed_in_place_after_env_keyword(self):
        self.assertWrites("env X=1 sed -i s/a/b/ %s" % self.path("app.tsx"), "app.tsx")

    def test_sed_without_in_place_writes_nothing(self):
        self.assertEqual("", self.w("sed s/x/y/ %s" % self.path("app.tsx")))

    def test_perl_in_place(self):
        self.assertWrites("perl -pi -e s/x/y/ %s" % self.path("app.tsx"), "app.tsx")


class CopyMove(WriteTargetCase):
    def test_cp_to_file(self):
        self.assertWrites("cp a.tsx %s" % self.path("app.tsx"), "app.tsx")

    def test_cp_to_directory(self):
        self.assertWrites("cp a.tsx src/", os.path.join("src", "a.tsx"))

    def test_cp_target_directory_flag(self):
        self.assertWrites("cp -t src a.tsx", os.path.join("src", "a.tsx"))

    def test_mv_to_file(self):
        self.assertWrites("mv a.tsx %s" % self.path("app.tsx"), "app.tsx")


class ScriptWrites(WriteTargetCase):
    def test_python_inline_open_write(self):
        self.assertWrites("python3 -c \"open('src/app.tsx','w').write(1)\"",
                          os.path.join("src", "app.tsx"))

    def test_node_inline_write_file_sync(self):
        self.assertWrites("node -e \"require('fs').writeFileSync('src/app.tsx','x')\"",
                          os.path.join("src", "app.tsx"))

    def test_script_file_scanned_from_disk(self):
        script = self.write_script("gen.py", "open(%r, 'w').write('x')\n" % self.path("src/a.tsx"))
        self.assertWrites("python3 " + script, os.path.join("src", "a.tsx"))

    def test_test_script_writes_fixtures_not_gated(self):
        tests = os.path.join(self.tmp, "tests")
        os.makedirs(tests)
        script = self.write_script(os.path.join("tests", "test_gen.py"),
                                   "open(%r, 'w').write('x')\n" % self.path("src/a.tsx"))
        self.assertEqual("", self.w("python3 " + script))

    def test_script_that_only_prints_a_path_is_benign(self):
        script = self.write_script("mention.py", "print('src/App.tsx is fine')\n")
        self.assertEqual("", self.w("python3 " + script))

    def test_quoted_data_heredoc_body_not_scanned(self):
        command = "cat > %s <<'EOF'\necho x > %s\nEOF" % (self.path("data.txt"), self.path("app.tsx"))
        self.assertEqual("", self.w(command))

    def test_unquoted_heredoc_body_expands_so_scanned(self):
        command = "cat > %s <<EOF\necho x > %s\nEOF" % (self.path("data.txt"), self.path("app.tsx"))
        self.assertWrites(command, "app.tsx")


class BenignCommands(WriteTargetCase):
    def test_label_declaration_echo_is_benign(self):
        self.assertEqual("", self.w('echo "Runtime owner: OrderForm" "Decision: extend"'))

    def test_git_commit_is_benign(self):
        self.assertEqual("", self.w("git commit -m x"))

    def test_mkdir_is_benign(self):
        self.assertEqual("", self.w("mkdir -p %s" % self.path("src")))

    def test_write_outside_any_repo_is_out_of_scope(self):
        self.assertEqual("", self.w("echo x > /repo/app.tsx"))

    def test_new_untracked_code_file_is_still_gated(self):
        self.assertWrites("echo x > new.tsx", "new.tsx")


class Regressions(WriteTargetCase):
    """Writes that write_target() currently misses (returns "", so the gate runs them free).
    Each test encodes the correct contract and fails until the fix wave lands it."""

    def test_regression_r1_eval_write_is_gated(self):
        self.assertGated("eval 'echo x > src/app.tsx'")

    def test_regression_r2_bash_c_write_is_gated(self):
        self.assertGated("bash -c 'echo x > src/app.tsx'")

    def test_regression_r2_sh_c_write_is_gated(self):
        self.assertGated('sh -c "echo x > src/app.tsx"')

    def test_regression_r3_git_checkout_paths_write_is_gated(self):
        self.assertGated("git checkout HEAD~1 -- src/a.tsx")

    def test_regression_r3_git_restore_source_write_is_gated(self):
        self.assertGated("git restore --source=HEAD~1 src/a.tsx")

    def test_regression_r4_git_stash_pop_writes_worktree(self):
        self.assertGated("git stash pop")

    def test_regression_r4_git_stash_apply_writes_worktree(self):
        self.assertGated("git stash apply")

    def test_regression_r5_source_script_is_gated(self):
        script = self.write_script("gen.sh", "echo x > %s\n" % self.path("src/a.tsx"))
        self.assertGated("source " + script)

    def test_regression_r5_dot_script_is_gated(self):
        script = self.write_script("gen.sh", "echo x > %s\n" % self.path("src/a.tsx"))
        self.assertGated(". " + script)

    def test_regression_r5_direct_script_execution_is_gated(self):
        script = self.write_script("gen.sh", "echo x > %s\n" % self.path("src/a.tsx"))
        os.chmod(script, 0o755)
        self.assertGated(script)

    def test_regression_r6_shutil_copyfile_destination(self):
        self.assertWrites("python3 -c \"import shutil; shutil.copyfile('a.tsx','src/app.tsx')\"",
                          os.path.join("src", "app.tsx"))

    def test_regression_r6_shutil_copy2_destination(self):
        self.assertWrites("python3 -c \"import shutil; shutil.copy2('a.tsx','src/app.tsx')\"",
                          os.path.join("src", "app.tsx"))

    def test_regression_r6_shutil_move_destination(self):
        self.assertWrites("python3 -c \"import shutil; shutil.move('a.tsx','src/app.tsx')\"",
                          os.path.join("src", "app.tsx"))

    def test_regression_r7_mentioned_path_is_not_a_write_target(self):
        # dynamic_target() guesses the first code path the text names, so a script that only
        # prints src/App.tsx and writes a built path is pinned to a file it never writes.
        script = self.write_script("analyze.py",
                                   "print('scanning src/App.tsx')\n"
                                   "open(report, 'w').write('done')\n")
        target = self.w("python3 " + script)
        self.assertNotEqual(self.path("src/App.tsx"), target)


class HelperFunctions(WriteTargetCase):
    def test_dir_at_without_cd_is_cwd(self):
        self.assertEqual(("", True), bash_target.dir_at("echo x > a", 12))

    def test_dir_at_after_cd_is_folder(self):
        self.assertEqual(("/x", True), bash_target.dir_at("cd /x && echo x > a", 20))

    def test_dir_at_after_second_cd_is_unknown(self):
        self.assertEqual(("", False), bash_target.dir_at("cd a; cd b; echo x > a", 20))

    def test_dir_at_after_eval_is_unknown(self):
        self.assertEqual(("", False), bash_target.dir_at("eval 'x'; echo y > a", 22))

    def test_shell_segments_split_on_operators_not_in_quotes(self):
        segments = [tokens for tokens, _ in
                    bash_target.shell_segments("echo a; sed -i s/x/y/ f.tsx && echo 'b;c'")]
        self.assertEqual([["echo", "a"], ["sed", "-i", "s/x/y/", "f.tsx"], ["echo", "b;c"]],
                         segments)

    def test_command_index_skips_assignments_and_keywords(self):
        self.assertEqual(2, bash_target.command_index(["A=1", "env", "sed", "-i"]))


if __name__ == "__main__":
    unittest.main()
