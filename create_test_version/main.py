import os
import zipfile
import json
import re


def load_project_name(config_path):
    """Load project name from a JSON config file."""
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
            name = config.get("name")
            if not name:
                raise ValueError("Missing 'name' in config.")
            return name
    except Exception as e:
        raise RuntimeError(f"Error loading config: {e}")


def zip_folder(source_folder, archive, prefix):
    """Zip all files in a folder with a given prefix inside the archive."""
    if not os.path.exists(source_folder):
        print(f"[WARN] Folder does not exist: {source_folder}")
        return
    for root, _, files in os.walk(source_folder):
        for file in files:
            filepath = os.path.join(root, file)
            arcname = os.path.relpath(filepath, source_folder)
            archive.write(filepath, os.path.join(prefix, arcname))


def parse_semver(filename, base_name):
    """Extract version tuple (major, minor, patch) from filename."""
    pattern = re.compile(rf"{re.escape(base_name)}_v(\d+)\.(\d+)\.(\d+)\.mcaddon$")
    match = pattern.match(filename)
    if match:
        return tuple(map(int, match.groups()))
    return None


def get_next_semver(output_dir, base_name):
    """Get the next semantic version by incrementing the patch."""
    highest = (0, 0, 0)

    if not os.path.exists(output_dir):
        return highest

    for fname in os.listdir(output_dir):
        version = parse_semver(fname, base_name)
        if version and version > highest:
            highest = version

    # Increment patch version
    major, minor, patch = highest
    return (major, minor, patch + 1)


def format_semver(version_tuple):
    return f"{version_tuple[0]}.{version_tuple[1]}.{version_tuple[2]}"


def create_mcaddon(name, bp_path, rp_path, output_dir):
    """Create versioned .mcaddon with semantic versioning."""
    os.makedirs(output_dir, exist_ok=True)

    version = get_next_semver(output_dir, name)
    version_str = format_semver(version)
    mcaddon_filename = f"{name}_v{version_str}.mcaddon"
    mcaddon_path = os.path.join(output_dir, mcaddon_filename)

    with zipfile.ZipFile(mcaddon_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        zip_folder(bp_path, zipf, f"{name}_BP")
        zip_folder(rp_path, zipf, f"{name}_RP")

    print(f"[INFO] MCAddon created at: {mcaddon_path}")


def main():
    config_path = "../../config.json"
    build_dir = "../../build"
    test_output_dir = "../../testversion"

    try:
        project_name = load_project_name(config_path)
        bp_path = os.path.join(build_dir, f"{project_name}_BP")
        rp_path = os.path.join(build_dir, f"{project_name}_RP")
        output_dir = test_output_dir


        create_mcaddon(project_name, bp_path, rp_path, output_dir)

    except Exception as e:
        print(f"[ERROR] {e}")


if __name__ == "__main__":
    main()
