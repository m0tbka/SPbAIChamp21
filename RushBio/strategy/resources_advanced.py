from model.resource import Resource


class ResourceAdv(Resource):
    def __init__(self, type_of_resource: Resource = None, amount=None):
        super().__init__()
        self.type_of_resource = type_of_resource
        self.amount = amount
