# ¿Cómo contribuir a Honeycomb?

La manera más sencilla de contribuir es probando esta plataforma en tu escuela u organización, o encontrando una instancia pública e interactuando con sus contenidos.
Si a partir de esto tienes alguna retroalimentación (una mejora, una sugerencia o quizás algo que crees que es un error en la programación), nos encantaría escucharte y saber más al respecto.
Para ponerte en contacto con nosotrxs, por favor escríbenos al correo: [convida@apuntia.com](mailto:convida@apuntia.com), o también puedes crear una [Propuesta](https://github.com/convidauam/honeycomb/issues) usando [nuestro repositorio](https://github.com/convidauam/honeycomb/).

Si ya le echaste un ojo a nuestro código y te interesa hacer una modificación, te agradeceremos mucho que te familiarices con el tipo de [licencia](LICENSE) bajo el que publicamos Honeycomb, pues nos interesa que cualquier mejora o corrección a este software beneficie a todos sus usuarios, por lo que estaremos encantados de platicar contigo respecto a las modificaciones o mejoras que te gustaría incorporar.
Probablemente tu idea nos va a gustar también y podemos hacerla en conjunto.

Después de ese paréntesis, ahora sí, aquí te dejamos las instrucciones para que configures tu ambiente de desarrollo y puedas empezar a hacer experimentos.

## Configura tu ambiente de desarrollo

Antes que nada, necesitas descargar el código. Para esto, puedes usar la opción de obtener una copia en un archivo comprimido: [descargar archivo zip](https://github.com/convidauam/honeycomb/archive/refs/heads/main.zip).

O, todavía mejor, puedes:

1) Clonar directamente nuestro repositorio usando git: `git clone https://github.com/convidauam/honeycomb.git`
2) Todavía mejor, aunque un poco más avanzado, crea tu cuenta en GitHub, [haz un fork](https://github.com/convidauam/honeycomb/fork) de nuestro repositorio, y clona tu nuevo repositorio usando git.

Una vez que ya tengas tu copia del código, ahora sí, puedes probarlo.

### Mise (recomendado)

La forma más fácil de configurar y ejecutar este proyecto es con [mise](https://mise.jdx.dev/getting-started.html#installing-mise-cli) y [uv](https://docs.astral.sh/uv/getting-started/installation/#installation-methods).

Primero, dile a `mise` que confías en el proyecto:

```bash
mise trust
```

Así puedes ver las tareas disponibles:

```bash
mise tasks
```

### Tareas principales

- **Configura el ambiente:**

    Instala todas las dependencias usando `uv` (incluye grupos opcionales definidos en el proyecto):

    ```bash
    mise setup
    ```
    
- **Inicia el servidor de desarrollo:**
    
    Ejecuta el servidor de desarrollo usando la directiva personalizada *dev*:
    
    ```bash
    mise dev
    ```
    
- **Ejecuta las pruebas:**
    
    Ejecuta el conjunto definido de pruebas usando *pytest*:

    ```bash
    mise test
    ```

- **Configura y ejecuta usando Docker:**

    Configura la imagen de Docker de Honeycomb e inicia un contenedor:

    ```bash
    mise docker
    ```

Eso es todo — con *mise* todo es automático y reproducible.

---

### Forma alternativa (sin mise)

1. Cámbiate a la carpeta donde está el código (es la misma en la que están el archivo CONTRIBUIR.md y `setup.py`):

    ```bash
    cd honeycomb
    ```

2. Crea un ambiente virtual de Python:

    ```bash
    python3 -m venv env
    ```

3. Actualiza las herramientas para crear paquetes:

    ```bash
    env/bin/pip install --upgrade pip setuptools
    ```

4. Instala el paquete en modo editable con las características de testeo:

    ```bash
    env/bin/pip install -e ".[testing]"
    ```

5. Ejecuta las pruebas del proyecto:

    ```bash
    env/bin/pytest
    ```

6. Ejecuta el proyecto en modo de desarrollo:

    ```bash
    env/bin/pserve development.ini
    ```
---

### Ejecuta con Docker (standalone)

1. Ve a la carpeta del proyecto.
    
2. Crea la imagen de Docker:
    ```bash
    docker build -t "honeycomb:latest" .
    ```

3. Ejecuta el contenedor:

    ```bash
    docker run -p 6543:6543 --rm honeycomb:latest
    ```

4. Abre esta dirección en tu navegador: [http://127.0.0.1:6543](http://127.0.0.1:6543)
