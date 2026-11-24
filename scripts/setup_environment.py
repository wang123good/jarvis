"""Create or validate the ignored local vault configuration."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from uuid import uuid4

import resolve_environment as reader


ROOT = Path(__file__).resolve().parents[1]
ENVIRONMENT_REL = Path(".local/environment.json")


class SetupError(ValueError):
    """The requested local configuration cannot be applied safely."""


def atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid4().hex + ".tmp")
    try:
        with temporary.open("xb") as stream:
            stream.write(data)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def json_bytes(value: dict) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def configure(project_root: Path, connector_vault: str, *, replace: bool = False) -> dict:
    root = Path(project_root).resolve()
    vault = reader.absolute_path(connector_vault, "connector_vault")
    if not vault.is_dir():
        raise SetupError(f"Connected vault directory does not exist: {vault}")

    environment_path = root / ENVIRONMENT_REL
    original = environment_path.read_bytes() if environment_path.is_file() else None
    existing = None
    if original is not None:
        try:
            existing = reader.read_object(environment_path)
        except reader.EnvironmentConfigError as exc:
            if not replace:
                raise SetupError(
                    f"Existing local environment is invalid; use --replace to rebuild it: {exc}"
                ) from exc
    skill_roots: list = []
    status = "updated" if existing is None and original is not None else "created"

    if existing is not None:
        if existing.get("version") != 1:
            if not replace:
                raise SetupError(
                    "Unsupported .local/environment.json version; use --replace to rebuild it"
                )
            existing = None
            status = "updated"
    if existing is not None:
        current = reader.absolute_path(existing.get("vault_root"), "vault_root")
        roots = existing.get("skill_roots", [])
        if not isinstance(roots, list):
            raise SetupError("skill_roots must be a list")
        skill_roots = roots
        if current == vault:
            status = "already_configured"
        elif not replace:
            raise SetupError(
                f"Local vault is already configured as {current}; use --replace to change it"
            )
        else:
            status = "updated"

    profile_path = root / "up.json"
    profile_before = profile_path.read_bytes() if profile_path.is_file() else None
    new_environment = {
        "version": 1,
        "vault_root": vault.as_posix(),
        "skill_roots": skill_roots,
    }

    changed = original != json_bytes(new_environment)
    try:
        if changed:
            atomic_write_bytes(environment_path, json_bytes(new_environment))
        resolved = reader.resolve_environment(root, str(vault))
        runtime_pointer = reader.write_runtime_pointer(resolved)
    except Exception:
        if original is None:
            if environment_path.exists():
                environment_path.unlink()
        else:
            atomic_write_bytes(environment_path, original)
        raise

    profile_after = profile_path.read_bytes() if profile_path.is_file() else None
    if profile_before != profile_after:
        raise SetupError("up.json changed unexpectedly; preserve it and investigate before retrying")

    return {
        "ok": True,
        "status": status,
        "environment_file": str(environment_path),
        "vault_root": str(vault),
        "runtime_pointer": str(runtime_pointer),
        "profile_modified": False,
        "next": 'python scripts/verify_installation.py --environment-only --connector-vault "'
        + str(vault)
        + '"',
    }


def main(argv=None, project_root=ROOT) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--connector-vault",
        "--vault",
        dest="connector_vault",
        required=True,
        help="Actual vault root reported by the connected Obsidian tool",
    )
    parser.add_argument("--replace", action="store_true", help="Replace a different existing vault path")
    args = parser.parse_args(argv)
    try:
        result = configure(project_root, args.connector_vault, replace=args.replace)
    except (OSError, SetupError, reader.EnvironmentConfigError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
