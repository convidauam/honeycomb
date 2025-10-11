# How to contribute to Honeycomb?

The easiest way to contribute is to try this software in your school or organization, or finding a public instance and interacting with their contents.
If based on that experience you have some feedback (an enhancement idea, a suggestion or perhaps you found some programming bug), we would love to hear from you and know more about that.
If you want to contact us, please send an email to the address: [convida@apuntia.com](mailto:convida@apuntia.com), or you can also create an [Issue](https://github.com/convidauam/honeycomb/issues) using [our repository](https://github.com/convidauam/honeycomb/).

If you already looked into our code and are interested in modifying something, we would suggest that you make yourself acquainted with the Honeycomb project's [license](LICENSE) which is intended to ensure that any improvement to the software benefits all their users.
Hence, we will love to talk with you about the changes or improvements that you would like to add.
It is very likely that we will love your ideas, and we can work together on that.

After this side comment, here you have the instructions to set up your development environment so that you can start tinkering.

## Set up your environment

Before starting, you need to get our code. For this, you can get a copy by [downloading a zip file](https://github.com/convidauam/honeycomb/archive/refs/heads/main.zip).

Even better, you can:

1) Directly clone our repository using git: `git clone https://github.com/convidauam/honeycomb.git`
2) More advanced, you can create your GitHub account, [fork our code](https://github.com/convidauam/honeycomb/fork), and clone your new repository using git.

Once you have our code in your computer, now you can start working on it.

### Mise (recommended)

The easiest way to configure and try this project is with [mise](https://mise.jdx.dev/getting-started.html#installing-mise-cli) and [uv](https://docs.astral.sh/uv/getting-started/installation/#installation-methods).

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