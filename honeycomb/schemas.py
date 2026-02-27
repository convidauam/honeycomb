"""
Esquemas de validación para cada tipo de contenido usando deform.
Cada tipo de celda tiene su propio esquema específico.
"""

import colander
from deform import widget


class CellTextSchema(colander.MappingSchema):
    """Esquema para celdas de texto simple"""
    title = colander.SchemaNode(
        colander.String(),
        description="Título de la celda",
        widget=widget.TextInputWidget()
    )
    contents = colander.SchemaNode(
        colander.String(),
        description="Contenido de texto",
        widget=widget.TextAreaWidget(rows=10)
    )
    icon = colander.SchemaNode(
        colander.String(),
        description="URL del icono (opcional)",
        widget=widget.TextInputWidget(),
        missing=""
    )


class CellRichTextSchema(colander.MappingSchema):
    """Esquema para celdas con texto enriquecido"""
    title = colander.SchemaNode(
        colander.String(),
        description="Título de la celda"
    )
    contents = colander.SchemaNode(
        colander.String(),
        description="Contenido HTML enriquecido",
        widget=widget.TextAreaWidget(rows=15)
    )
    icon = colander.SchemaNode(
        colander.String(),
        description="URL del icono (opcional)",
        widget=widget.TextInputWidget(),
        missing=""
    )


class CellAnimationSchema(colander.MappingSchema):
    """Esquema para celdas de animación"""
    title = colander.SchemaNode(
        colander.String(),
        description="Título de la celda"
    )
    href = colander.SchemaNode(
        colander.String(),
        description="URL o ruta de la animación",
        widget=widget.TextInputWidget()
    )
    icon = colander.SchemaNode(
        colander.String(),
        description="URL del icono (opcional)",
        widget=widget.TextInputWidget(),
        missing=""
    )


class CellWebContentSchema(colander.MappingSchema):
    """Esquema para celdas de contenido web"""
    title = colander.SchemaNode(
        colander.String(),
        description="Título de la celda"
    )
    href = colander.SchemaNode(
        colander.String(),
        description="URL del contenido web",
        widget=widget.TextInputWidget()
    )
    icon = colander.SchemaNode(
        colander.String(),
        description="URL del icono (opcional)",
        widget=widget.TextInputWidget(),
        missing=""
    )


class CellIconSchema(colander.MappingSchema):
    """Esquema para celdas de icono"""
    title = colander.SchemaNode(
        colander.String(),
        description="Título de la celda"
    )
    icon = colander.SchemaNode(
        colander.String(),
        description="URL del icono",
        widget=widget.TextInputWidget()
    )


class HoneycombSchema(colander.MappingSchema):
    """Esquema para crear un nuevo Honeycomb"""
    name = colander.SchemaNode(
        colander.String(),
        description="Nombre único del Honeycomb (slug)"
    )
    title = colander.SchemaNode(
        colander.String(),
        description="Título del Honeycomb"
    )


class BeeHiveSchema(colander.MappingSchema):
    """Esquema para crear un nuevo BeeHive"""
    name = colander.SchemaNode(
        colander.String(),
        description="Nombre único del BeeHive"
    )
    title = colander.SchemaNode(
        colander.String(),
        description="Título del BeeHive"
    )


class CreateCellBaseSchema(colander.MappingSchema):
    """Esquema base para crear celdas con ubicación opcional en el árbol"""
    parent_id = colander.SchemaNode(
        colander.String(),
        description="ID del nodo padre (opcional - si no se proporciona, se crea en el nivel superior)",
        widget=widget.TextInputWidget(),
        missing=None,
        required=False
    )
