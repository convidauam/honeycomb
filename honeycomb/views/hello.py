from cornice import Service

hello = Service(name='hello', path='/hello', description="Servicio de saludo")

@hello.get()
def get_hello(request):
    return {"message": "Hola desde el backend Pyramid + Cornice"}
