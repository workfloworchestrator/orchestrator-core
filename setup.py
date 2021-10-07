import toml
from setuptools import setup

from orchestrator import __version__

setup_variables = toml.load("pyproject.toml")

setup(
    name=setup_variables["tool"]["dist-name"],
    version=__version__,
    classifiers=setup_variables["tool"]["classifiers"],
    module=setup_variables["tool"]["module"],
    author=setup_variables["tool"]["author"],
    author_email=setup_variables["tool"]["author_email"],
    packages=setup_variables["tool"]["dist-name"],
    requires=setup_variables["tool"]["requires"],
    description_file=setup_variables["tool"]["README.md"],
)
