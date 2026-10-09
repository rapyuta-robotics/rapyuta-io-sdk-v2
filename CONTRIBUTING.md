# Contribution Guidelines
## 🌟 Setup Your Development Environment

The project requires Python 3.13 or newer and uses [uv](https://docs.astral.sh/uv/) for development. It needs to be installed to set up the development environment.

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

> Note: In case of installation error, please refer to this [installation documentation](https://docs.astral.sh/uv/getting-started/installation/).

Once `uv` is installed, a Python virtual environment can be quickly bootstrapped by running the following commands in the root of the repository:

```bash
uv python install 3.13
uv venv --python 3.13
source .venv/bin/activate
```

This will create a virtual environment in the `.venv` directory and activate it.

Next, install all dependencies using the following command:

```bash
uv sync
```

New dependencies can be installed directly using `uv`. This modifies the `pyproject.toml` and `uv.lock`.

```bash
uv add <package-name>
```

### 🛠️ Linting and Formatting

Run the same checks as CI:

```bash
uvx ruff==0.16.9 check .
uvx ruff==0.16.9 format --check .
```

Apply safe fixes and formatting, then rerun both checks:

```bash
uvx ruff==0.16.9 check --fix .
uvx ruff==0.16.9 format .
```

The strict configuration in `pyproject.toml` enables all stable Ruff rules,
including unused code, commented-out code, missing annotations, broad exception
handlers, debugging statements, import sorting, security checks, and unnecessary
control flow. Selected preview rules also enforce local-variable, boolean-expression,
and nesting limits; other preview rules and preview formatting remain disabled.

| Constraint | Maximum |
| --- | --- |
| Code, comment, and docstring line length | 88 characters |
| Cyclomatic complexity (`C901`) | 5 |
| Arguments (`PLR0913`) | 5 |
| Positional arguments (`PLR0917`) | 3 |
| Branches (`PLR0912`) | 6 |
| Return statements (`PLR0911`) | 4 |
| Statements (`PLR0915`) | 30 |
| Local variables (`PLR0914`, preview) | 10 |
| Boolean expressions (`PLR0916`, preview) | 3 |
| Nested blocks (`PLR1702`, preview) | 3 |

Ruff exempts some long lines, including standalone URLs and unbreakable words;
the formatter also cannot wrap every string or docstring. Split ordinary long
strings and wrap prose manually when lint reports them. Formatting owns quote,
indentation, and trailing-comma style. Docstrings use the Google convention, and
their code examples are formatted.

Test-only exceptions allow assertions, dummy credentials, missing module/function
docstrings, and the existing namespace package layout. Examples may use `print`.
Complexity and line-length limits apply to tests and examples too. Agent tooling
under `.agents`, `.claude`, and `.specify` is excluded from SDK checks.

Refactor code to meet the limits. Do not relax the configuration or add blanket
`noqa`/`type: ignore` comments to make checks pass. A necessary suppression must
name the specific rule and explain the reason. Unused `noqa` comments are errors.
Unsafe fixes require deliberate review. Update the pinned version in
`pyproject.toml`, CI, and these commands together when upgrading Ruff.

Existing positional SDK signatures, camelCase model attributes, and required
framework interfaces have documented rule-specific compatibility exceptions.
New interfaces should meet the limits without suppressions. Ruff catches
structural problems; behavior still needs tests, and type correctness needs a
type checker.
