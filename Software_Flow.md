# Software Flow

- The format of this repository will be a continuous-integration/development format
- The `main` branch has all the current "new" changes.
- Small changes are committed directly to `main` while larger ones can get a `feature/FEATURE` branch.
- Bugs follow the same format

After the `main` reaches a stable state, a release can be created from `main`, into the `release/RELEASE` branches

## Code format

Anything in `main` must have 0 Warnings and Errors from the following tools:
1. black -- style
2. mypy -- type checking
3. interrogate -- docstring checking.