import collections.abc
import typing
import uuid
from collections import defaultdict
from datetime import date, datetime
from itertools import chain


class Field:
    def __init__(self, description=None, required=None, name=None, choices=None):
        self.name = name
        self.description = description
        self.required = required
        self.choices = choices

    def serialize(self):
        output = {}
        if self.name:
            output["name"] = self.name
        if self.description:
            output["description"] = self.description
        if self.required is not None:
            output["required"] = self.required
        if self.choices is not None:
            output["enum"] = self.choices
        return output


class Integer(Field):
    def serialize(self):
        return {"type": "integer", "format": "int64", **super().serialize()}


class Float(Field):
    def serialize(self):
        return {"type": "number", "format": "double", **super().serialize()}


class String(Field):
    def serialize(self):
        return {"type": "string", **super().serialize()}


class Boolean(Field):
    def serialize(self):
        return {"type": "boolean", **super().serialize()}


class Tuple(Field):
    pass


class Date(Field):
    def serialize(self):
        return {"type": "string", "format": "date", **super().serialize()}


class DateTime(Field):
    def serialize(self):
        return {"type": "string", "format": "date-time", **super().serialize()}


class File(Field):
    def serialize(self):
        return {"type": "file", **super().serialize()}


class Dictionary(Field):
    def __init__(self, fields=None, **kwargs):
        self.fields = fields or {}
        super().__init__(**kwargs)

    def serialize(self):
        return {
            "type": "object",
            "properties": {
                key: serialize_schema(schema) for key, schema in self.fields.items()
            },
            **super().serialize(),
        }


class JsonBody(Field):
    def __init__(self, fields=None, **kwargs):
        self.fields = fields or {}
        super().__init__(**kwargs, name="body")

    def serialize(self):
        return {
            "schema": {
                "type": "object",
                "properties": {
                    key: serialize_schema(schema) for key, schema in self.fields.items()
                },
            },
            **super().serialize(),
        }


class List(Field):
    def __init__(self, items=None, *args, **kwargs):
        self.items = items or []
        if type(self.items) is not list:
            self.items = [self.items]
        super().__init__(*args, **kwargs)

    def serialize(self):
        if len(self.items) > 1:
            items = Tuple(self.items).serialize()
        elif self.items:
            items = serialize_schema(self.items[0])
        else:
            items = []
        return {"type": "array", "items": items, **super().serialize()}


class UUID(Field):
    def serialize(self):
        return {"type": "string", "format": "uuid", **super().serialize()}


definitions = {}


class Object(Field):
    def __init__(self, cls, *args, object_name=None, **kwargs):
        self.cls = cls
        self.object_name = object_name or cls.__name__

        #getting properties of class
        self.properties = self.getProperties()

        #getting the name of discriminator if exists
        self.discriminator = self.getDiscriminatorName()

        #adding discriminator field in 'required'
        if self.discriminator:
            if 'required' in kwargs:
                kwargs['required'].append(self.discriminator)
            else:
                kwargs['required'] = [self.discriminator]

        super().__init__(*args, **kwargs)

        register_as = object_name or "{}.{}".format(cls.__module__, cls.__qualname__)
        if register_as not in definitions:
            definitions[register_as] = (self, self.definition)

        #creating definitions for all parental classes
        for base in cls.__bases__:
            if base.__name__ != "object":
                Object(base)

    def inheritanceRef(self):
        """if class has any parents except 'object' class, 
        return dict with a key 'allOf' and a list with links
         on parental classes definitions"""
        refs = []
        for base in self.cls.__bases__:
            if base.__name__ != "object":
                refs.append({'$ref': "#/definitions/{}".format(base.__name__)})
        return refs

    def getDiscriminatorName(self):
        """if class has field that fits into discriminator's
        name template, returns that field name"""
        if f"{self.cls.__name__}Type" in self.properties:
            return f"{self.cls.__name__}Type"

    def getDiscriminatorDef(self):
        """if class has discriminator, returns dict with it definition"""
        return {'discriminator': self.discriminator} if self.discriminator else {}

    def getProperties(self):
        """moved from definition method because of necessity in additional use"""
        return {
            key: serialize_schema(schema)
            for key, schema in chain(
                self.cls.__dict__.items(), typing.get_type_hints(self.cls).items()
            )
            if not key.startswith("_")
        }

    @property
    def definition(self):
        definition = {
            "type": "object",

            #inserting the definiton of discriminator
            **self.getDiscriminatorDef(),

            "properties": self.properties,
            **super().serialize(),
        }

        #getting all refs on parental classes
        refs = self.inheritanceRef()

        return {"allOf": refs+[definition]} if refs != [] else definition

    def serialize(self):
        return {
            "$ref": "#/definitions/{}".format(self.object_name),
            **super().serialize(),
        }


def serialize_schema(schema):
    schema_type = type(schema)

    # --------------------------------------------------------------- #
    # Class
    # --------------------------------------------------------------- #
    if issubclass(schema_type, type):
        if issubclass(schema, Field):
            return schema().serialize()
        elif schema is dict:
            return Dictionary().serialize()
        elif schema is list:
            return List().serialize()
        elif schema is int:
            return Integer().serialize()
        elif schema is float:
            return Float().serialize()
        elif schema is str:
            return String().serialize()
        elif schema is bool:
            return Boolean().serialize()
        elif schema is date:
            return Date().serialize()
        elif schema is datetime:
            return DateTime().serialize()
        elif schema is uuid.UUID:
            return UUID().serialize()
        else:
            return Object(schema).serialize()

    # --------------------------------------------------------------- #
    # Object
    # --------------------------------------------------------------- #
    else:
        if issubclass(schema_type, Field):
            return schema.serialize()
        elif schema_type is dict:
            return Dictionary(schema).serialize()
        elif schema_type is list:
            return List(schema).serialize()
        elif getattr(schema, "__origin__", None) in (list, collections.abc.Sequence):
            # Type hinting with either List or Sequence
            return List(list(schema.__args__)).serialize()

    return {}


# --------------------------------------------------------------- #
# Route Documenters
# --------------------------------------------------------------- #


class RouteSpec(object):
    consumes = None
    consumes_content_type = None
    produces = None
    produces_content_type = None
    summary = None
    description = None
    operation = None
    blueprint = None
    tags = None
    exclude = None
    response = None

    def __init__(self):
        self.tags = []
        self.consumes = []
        self.response = []
        super().__init__()


class RouteField(object):
    field = None
    location = None
    required = None
    description = None

    def __init__(self, field, location=None, required=False, description=None):
        self.field = field
        self.location = location
        self.required = required
        self.description = description


route_specs = defaultdict(RouteSpec)


def route(
    summary=None,
    description=None,
    consumes=None,
    produces=None,
    consumes_content_type=None,
    produces_content_type=None,
    exclude=None,
    response=None,
):
    def inner(func):
        route_spec = route_specs[func]

        if summary is not None:
            route_spec.summary = summary
        if description is not None:
            route_spec.description = description
        if consumes is not None:
            route_spec.consumes = consumes
        if produces is not None:
            route_spec.produces = produces
        if consumes_content_type is not None:
            route_spec.consumes_content_type = consumes_content_type
        if produces_content_type is not None:
            route_spec.produces_content_type = produces_content_type
        if exclude is not None:
            route_spec.exclude = exclude
        if response is not None:
            route_spec.response = response

        return func

    return inner


def exclude(boolean):
    def inner(func):
        route_specs[func].exclude = boolean
        return func

    return inner


def summary(text):
    def inner(func):
        route_specs[func].summary = text
        return func

    return inner


def description(text):
    def inner(func):
        route_specs[func].description = text
        return func

    return inner


def consumes(*args, content_type=None, location="query", required=False):
    def inner(func):
        if args:
            for arg in args:
                field = RouteField(arg, location, required)
                route_specs[func].consumes.append(field)
                route_specs[func].consumes_content_type = [content_type]
        return func

    return inner


def produces(*args, description=None, content_type=None):
    def inner(func):
        if args:
            routefield = RouteField(args[0], description=description)
            route_specs[func].produces = routefield
            route_specs[func].produces_content_type = [content_type]
        return func

    return inner


def response(*args, description=None):
    def inner(func):
        if args:
            status_code = args[0]
            routefield = RouteField(args[1], description=description)
            route_specs[func].response.append((status_code, routefield))
        return func

    return inner


def tag(name):
    def inner(func):
        route_specs[func].tags.append(name)
        return func

    return inner


def operation(name):
    def inner(func):
        route_specs[func].operation = name
        return func

    return inner
