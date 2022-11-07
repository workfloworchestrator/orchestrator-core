from importlib.machinery import SourceFileLoader

import toml
from setuptools import setup

version = SourceFileLoader("__version__", "orchestrator/__init__.py").load_module()

setup_variables = toml.load("pyproject.toml")["tool"]["flit"]["metadata"]

setup(
    name=setup_variables["dist-name"],
    version=str(version.__version__),
    classifiers=setup_variables["classifiers"],
    author=setup_variables["author"],
    author_email=setup_variables["author-email"],
    packages=[setup_variables["module"]],
    install_requires=setup_variables["requires"],
    description="The Orchestrator core",
    long_description=setup_variables["description-file"],
)
