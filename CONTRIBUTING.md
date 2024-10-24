# Contribution Guidelines
## 🌟 Setup Your Development Environment

The project uses [uv](https://docs.astral.sh/uv/) for development. It needs to be installed to set up the development environment.

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

> Note: In case of installation error, please refer to this [installation documentation](https://docs.astral.sh/uv/getting-started/installation/).

Once `uv` is installed, a Python virtual environment can be quickly bootstrapped by running the following commands in the root of the repository:

```bash
uv venv
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

You can check and fix the code style by running the following commands:

```bash
uvx ruff check --fix
uvx ruff format
```