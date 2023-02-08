# Testing

It is difficult and time consuming to test Github Actions workflows through full-fledged runs. Using the tool https://github.com/nektos/act it is possible to test workflows on your local machine.

## Example usage

I had to test the `build-push-container.yml` workflow which is triggered by a new (pre)release in the Github repository. Here's how I did this with `act`.

1. Install `act` through distribution's package manager
2. Create a Github [personal access token](https://github.com/settings/tokens) (a fine-grained read-only token worked for me to access GHCR)
3. Create file `release-0.5.3.json` to mock the release event which normally triggers the workflow
```json
{
    "release": {
        "tag_name": "refs/tags/0.5.3",
        "prerelease": false
    }
}
```
4. Run the workflow with the mocked release event:
```sh
act release -W .github/workflows/build-push-container.yml -e release-0.5.3.json -s GITHUB_TOKEN=token_from_step2
```
5. Verify the workflow generates the version, `latest` and `edge` tag
```
[Build and push container image/build-and-push-image]   ❓  ::group::Docker tags
| ghcr.io/workfloworchestrator/orchestrator-core:0.5.3
| ghcr.io/workfloworchestrator/orchestrator-core:latest
| ghcr.io/workfloworchestrator/orchestrator-core:edge
[Build and push container image/build-and-push-image]
```
6. Create another file `release-0.5.3-rc1.json` for a pre-release
```json
{
    "release": {
        "tag_name": "refs/tags/0.5.3-rc1",
        "prerelease": true
    }
}
```
7. Run the workflow with the mocked pre-release event:
```sh
act release -W .github/workflows/build-push-container.yml  -e release-0.5.3-rc1.json -s GITHUB_TOKEN=token_from_step2
```
8. Verify the workflow generates the version and `edge` tag
```
[Build and push container image/build-and-push-image]   ❓  ::group::Docker tags
| ghcr.io/workfloworchestrator/orchestrator-core:0.5.3-rc1
| ghcr.io/workfloworchestrator/orchestrator-core:edge
[Build and push container image/build-and-push-image]
```


## Tips

**Exclude steps**
To prevent a step from running while testing with `act` you can add an `if:` condition
```yml
- name: Build and push Docker image
  if: ${{ !env.ACT }}  #  <-- add this
  uses: docker/build-push-action@v3
```

**Event payload**
Mocking events correctly is a bit of trial and error. I consulted [the docs](https://docs.github.com/developers/webhooks-and-events/webhooks/webhook-events-and-payloads#release) for the event properties, tried to guess what the values needed to be, and then compared the output of the workflow in `act` against that of actual workflow runs on Github.
