#!/usr/bin/env python3
"""Four-axis gate for a de-identified estate. Run AFTER 5_verify.sh.

5_verify.sh answers "are there secrets left?". This answers a different and
easier-to-miss question: "are there NAMES left, and did the rewrite break the
code?" A name-only check happily passes a tree full of `class Acme-corpApi`,
which is not valid PHP -- hence axis 3.

    NAMES      no identifying token in commit messages OR file contents
    INTEGRITY  commit counts identical to the source
    SYNTAX     php -l on every touched PHP file (real parser, not a regex)
    PATHS      no identifying token in a file or directory NAME

The token list is supplied at runtime and never lives in this repository --
it is a list of the real names you are removing. Keep it out of version
control. One token per line; blank lines and #comments ignored.

    ./6_verify_names.py work/delivery/repos work/clones tokens.txt
"""
import os, re, sys, shutil, subprocess, collections

SKIP = {".git", "node_modules", "vendor", "vendors", "dist", "build", ".venv",
        "venv", "bower_components", "__pycache__", "Pods", "Carthage", ".gradle",
        "target", "bin", "obj", "packages", "third_party", "lib"}
TEXT = {".php", ".js", ".jsx", ".ts", ".tsx", ".py", ".java", ".kt", ".swift",
        ".rb", ".go", ".cs", ".m", ".mm", ".vue", ".dart", ".html", ".css",
        ".scss", ".json", ".xml", ".yml", ".yaml", ".env", ".sql", ".md",
        ".txt", ".sh", ".properties", ".plist", ""}
MAX_BYTES = 2_000_000


def git(path, *args):
    return subprocess.run(["git", "-C", path, *args], capture_output=True,
                          text=True, errors="replace").stdout


def load_tokens(path):
    out = []
    for line in open(path):
        line = line.strip()
        if line and not line.startswith("#"):
            out.append(line)
    if not out:
        sys.exit(f"no tokens found in {path}")
    return out


def main():
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    dst, src, tokfile = sys.argv[1:4]
    tokens = load_tokens(tokfile)
    name_rx = re.compile("|".join(map(re.escape, tokens)), re.I)

    names = collections.Counter()
    paths = collections.Counter()
    mismatch, php_fail = [], []
    commits = 0
    php = shutil.which("php")
    repos = sorted(d for d in os.listdir(dst)
                   if os.path.isdir(os.path.join(dst, d)))

    for repo in repos:
        p = os.path.join(dst, repo)
        for m in name_rx.findall(git(p, "log", "--all", "--pretty=%s%n%b")):
            names[m.lower()] += 1

        new = git(p, "rev-list", "--count", "HEAD").strip()
        old = git(os.path.join(src, repo), "rev-list", "--count", "HEAD").strip()
        commits += int(new or 0)
        if old and new != old:
            mismatch.append((repo, old, new))

        for dirpath, dirs, files in os.walk(p):
            dirs[:] = [d for d in dirs if d not in SKIP]
            for entry in list(dirs) + files:
                if name_rx.search(entry):
                    paths[repo] += 1
            for f in files:
                ext = os.path.splitext(f)[1].lower()
                if ext not in TEXT:
                    continue
                fp = os.path.join(dirpath, f)
                try:
                    if os.path.getsize(fp) > MAX_BYTES:
                        continue
                    body = open(fp, errors="replace").read()
                except OSError:
                    continue
                for m in name_rx.findall(body):
                    names[m.lower()] += 1
                if php and ext == ".php":
                    rc = subprocess.run([php, "-l", fp], capture_output=True,
                                        text=True)
                    if rc.returncode != 0 and "syntax error" in (
                            rc.stdout + rc.stderr).lower():
                        php_fail.append((repo, os.path.relpath(fp, p)))

    print("repos verified        :", len(repos))
    print("commits preserved     :", f"{commits:,}")
    print("commit-count mismatch :", mismatch or "NONE - all exact")
    print("names left            :", dict(names) or "NONE")
    print("paths carrying a token:", sum(paths.values()) or "NONE",
          dict(paths.most_common(3)) if paths else "")
    print("php -l failures       :", len(php_fail) if php else "php absent")
    for row in php_fail[:10]:
        print("   ", row)

    bad = bool(names or paths or mismatch or php_fail)
    print("\nRESULT:", "FAIL" if bad else "PASS")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
