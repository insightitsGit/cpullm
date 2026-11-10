# Release publishing and provenance

Version 1.11.1 was manually uploaded to PyPI by the maintainer. Its original
artifacts remain unchanged. See the [publication receipt](releases/1.11.1-publication.json).
The Git tag identifies the release implementation, rather than later documentation.

The manual GitHub workflow `pypi-release.yml` prepares future distributions and
checks their metadata. Its publish input defaults to false. Publishing requires
a matching `vVERSION` tag and the `pypi` GitHub environment; it uses PyPI Trusted
Publishing rather than a stored API token.

Before enabling publishing, the PyPI project owner must configure a publisher:

- Owner: `insightitsGit`; repository: `cpullm`.
- Workflow: `pypi-release.yml`; environment: `pypi`.
- Configure the GitHub environment's release protections for the project.

This account-side configuration has **not** been completed by this repository
change. Future successful OIDC uploads can carry publishing attestations; the
manually uploaded 1.11.1 files do not gain attestations retroactively. Do not
rerun publication for an existing version or overwrite its artifacts.

See [PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/).
Repository README corrections apply to future distribution descriptions; editing
the repository does not update the already-uploaded 1.11.1 long description.
Whether to yank the defective 1.11.0 HTTP release remains an owner decision.

## Release-candidate gates

Dispatch the workflow with publication disabled to build the wheel from the
source archive, validate metadata, and test the installed wheel on CPython 3.11
and 3.12 against disposable pgvector and prepared encoder assets. Both test
jobs must pass before publishing.

After approval, commit the validated release contents, create the annotated
tag matching the package version (for example, `v1.12.1rc1`), and push that
tag. Dispatch the workflow against the tag with publication enabled after
configuring the protected PyPI environment and trusted publisher. Verify PyPI
provenance for both uploaded files and retain the workflow run URL.
