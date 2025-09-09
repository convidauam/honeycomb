# Honeycomb

## Getting Started with [mise](https://mise.jdx.dev/) (Recommended)

The easiest way to set up and run this project is with [mise](https://mise.jdx.dev/getting-started.html#installing-mise-cli) and [uv](https://docs.astral.sh/uv/getting-started/installation/#installation-methods).

First, trust the project environment:

```bash
mise trust
```

You can explore the available tasks with:

```bash
mise tasks
```

### Main Tasks

- **Setup the environment:**

    Installs all dependencies (including optional groups defined in the project):

    ```bash
    mise setup
    ```
    
- **Start the development server:**
    
    Runs the project locally using the custom dev launcher:
    
    ```bash
    mise dev
    ```
    
- **Run tests:**
    
    Launches the test suite with pytest:

    ```bash
    mise test
    ```

- **Docker build & run:**

    Builds the project Docker image and starts a container:

    ```bash
    mise docker
    ```

That’s it — with mise everything is automated and reproducible.

---

## **Manual Alternative (without mise)**

1. Change to the project directory (where this README and `setup.py` are located):

    ```bash
    cd honeycomb
    ```

2. Create a Python virtual environment:

    ```bash
    python3 -m venv env
    ```

3. Upgrade packaging tools:

    ```bash
    env/bin/pip install --upgrade pip setuptools
    ```

4. Install the project in editable mode with testing requirements:

    ```bash
    env/bin/pip install -e ".[testing]"
    ```

5. Run the project tests:

    ```bash
    env/bin/pytest
    ```

6. Run the project:

    ```bash
    env/bin/pserve development.ini
    ```
---

## **Running with Docker (standalone)**

1. Go to the project directory.
    
2. Build the Docker image:
    ```bash
    docker build -t "honeycomb:latest" .
    ```

3. Run the container:

    ```bash
    docker run -p 6543:6543 --rm honeycomb:latest
    ```

4. Open your browser at: [http://127.0.0.1:6543](http://127.0.0.1:6543)