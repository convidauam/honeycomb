import colander
import deform


class AudioCellSchema(colander.MappingSchema):
    title = colander.SchemaNode(colander.String(), missing="")
    # data = colander.SchemaNode(deform.schema.FileData())
    mimetype = colander.SchemaNode(colander.String(), validator=colander.OneOf(['audio/mpeg', 'audio/aac', 'audio/ogg', 'audio/wav', 'audio/flac'], msg_err='"${val}" must be one of ${choices}'))
    parent = colander.SchemaNode(colander.String(), validator=colander.uuid, missing=None)
    length = colander.SchemaNode(colander.Float(), missing=0.0)
