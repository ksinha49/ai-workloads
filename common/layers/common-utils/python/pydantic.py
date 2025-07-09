class ValidationError(Exception):
    """Minimal validation error."""

class BaseModel:
    def __init__(self, **data):
        import sys, typing
        module = sys.modules.get(self.__class__.__module__)
        base = module.__dict__ if module else {}
        hints = {}
        for name, typ in self.__class__.__annotations__.items():
            if isinstance(typ, str):
                hints[name] = eval(typ, base, vars(typing))
            else:
                hints[name] = typ
        for name in hints:
            setattr(self, name, data.get(name, getattr(self.__class__, name, None)))
        extras = {k: v for k, v in data.items() if k not in hints}
        self.__extras__ = extras
        for k, v in extras.items():
            setattr(self, k, v)

    @classmethod
    def parse_obj(cls, obj):
        if not isinstance(obj, dict):
            raise ValidationError("Event must be a dict")
        import sys, typing
        module = sys.modules.get(cls.__module__)
        base = module.__dict__ if module else {}
        hints = {}
        for name, typ in cls.__annotations__.items():
            if isinstance(typ, str):
                hints[name] = eval(typ, base, vars(typing))
            else:
                hints[name] = typ
        data = {}
        for name, typ in hints.items():
            if name in obj:
                val = obj[name]
                if typ is int:
                    try:
                        val = int(val)
                    except Exception:
                        raise ValidationError(f"{name} invalid")
                elif typ is str:
                    if not isinstance(val, str):
                        raise ValidationError(f"{name} invalid")
                elif getattr(typ, "__origin__", typ) is list:
                    if not isinstance(val, list):
                        raise ValidationError(f"{name} invalid")
                data[name] = val
            else:
                data[name] = getattr(cls, name, None)
        data.update({k: v for k, v in obj.items() if k not in hints})
        return cls(**data)

    def model_dump(self):
        import typing
        hints = typing.get_type_hints(self.__class__)
        out = {k: getattr(self, k) for k in hints}
        out.update(self.__extras__)
        return out


def create_model(name: str, **fields):
    """Return a simple dynamic model class."""
    return type(name, (BaseModel,), fields)


class Extra:
    """Minimal placeholder for pydantic.Extra."""

    ignore = "ignore"
    forbid = "forbid"
    allow = "allow"
