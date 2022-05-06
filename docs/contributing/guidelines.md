# Contributing
The workflow orchestrator projects welcomes any contributions from any party. If you are interested in contributing
or have questions about the project please contact the board: workfloworchestrator.board@commonsconservancy.org or feel
free to raise an issue in the project. We will strive to reply to your enquiry A.S.A.P.

## Documentation
We use [**MKDOCS**](https://www.mkdocs.org) as a documentation tool. Please create a PR if you have any additions or
contributions to make. All docs can be written in MD or html.

## Orchestrator release
The `orchestrator-core` has no release schedule but is actively used and maintained by the workflow orchestrator group.
Creating a new release is done by the developers of the project and the procedure is as follows.

### Release candidates
When creating new features they can be released in so-called `pre-releases` on github. Depending on the feature type the
developer will need to run `bumpversion (major|minor|patch)` and then `bumpversion build --allow-dirty` to create a new release
candidate. This command will update the `.bumpversion.cfg` and the `orchestrator.__init__.py` files.

The next step would be to "Create a new release" -> "Fill in the tag and check the box, create tag upon release" and
use the checkbox "pre-release."

The code will be pushed to pypi and installed in a project.

### Official releases.

Official releases follow the same procedure as described above and can be either created from a release candidate by
removing the `-rc` string from the `.bumpversion.cfg` and the `orchestrator.__init__.py` files. After that a new release
can be created and the `Autogenerate changelog` option may be used.
