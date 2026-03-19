#Standard imports
import os
import pdb

#Installed library imports
import toml
import setuptools_scm
from setuptools import setup, find_packages

#Teamtools Studio Imports
#This doesn't get to have a logger because it's in the same
#library as the logger itself.

def setup_from_pyproject(base_path="."):
    """
    Helper to support installation of libraries in version of Python from 3.6.8 to 3.11+

    Due to customer needs, the teamtools studio decided that we would need to support versions of Python
    3.6.8 and higher, but the studio also has a philosophy of trying to keep up to date with modern Python convention

    The decision was made to use pyproject.toml as the primary convention for packaging because it is sufficiently modern,
    but it is not available in Python versions prior to 3.8. This function provides a mapping from pyptoject.toml to
    setup.py. TTS studio libraries will include both setup.py and pyproject.toml, but the setup.py is little more than
    a call of this function. That way package details can all be contained in a single, modern source of truth (pyproject.toml), 
    but even older Python versions will still be able to package from that same source of truth

    :param base_path: Path to be used to look for the repository. Nominally setup.py and pyproject.toml are in the same place
    :type base_path: str
    """
    pyproject_path = os.path.join(base_path, "pyproject.toml")
    data = toml.load(pyproject_path)

    project = data.get("project", {})
    tool_setuptools = data.get("tool", {}).get("setuptools", {})
    tool_setuptools_find = tool_setuptools.get("packages", {}).get("find", {})

    def get_author_info(authors):
        if not authors:
            return "", ""
        author = authors[0]
        return author.get("name", ""), author.get("email", "")

    author, author_email = get_author_info(project.get("authors", []))
    
    version = setuptools_scm.get_version(
        root=base_path,
        version_scheme="post-release",
        local_scheme="node-and-date",
    )

    # 🧠 Default to "" -> "src" if not present
    package_dir = tool_setuptools.get("package-dir", {"": "src"})
    
    # --- Parse [tool.setuptools.packages.find] arguments ---
    # TOML 'where' is usually a list ["src"], but find_packages expects a string "src"
    where_list = tool_setuptools_find.get("where", ["src"])
    where_dir = where_list[0] if where_list else "."

    # Explicitly grab include/exclude so we don't rely on old setuptools defaults
    # (which would otherwise strip out the 'test' directory in Py3.6)
    include_patterns = tool_setuptools_find.get("include", ["*"])
    exclude_patterns = tool_setuptools_find.get("exclude", [])

    setup(
        name=project.get("name"),
        version=version,
        description=project.get("description", ""),
        author=author,
        author_email=author_email,
        license=project.get("license", {}).get("text", ""),
        python_requires=project.get("requires-python", ">=3.6"),
        install_requires=project.get("dependencies", []),
        extras_require=project.get("optional-dependencies", {}),
        include_package_data=True,
        package_dir=package_dir,
        packages=find_packages(
            where=where_dir,
            include=include_patterns,
            exclude=exclude_patterns
        ),
        entry_points={
            "console_scripts": [
                f"{cmd} = {target}" for cmd, target in project.get("scripts", {}).items()
            ]
        } if "scripts" in project else {},
    )