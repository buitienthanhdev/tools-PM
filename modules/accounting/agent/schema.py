"""Kiểm tra JSON theo một tập con JSON Schema (type, enum, required, properties, items, min/max, maxLength)."""


class SchemaError(ValueError):
    pass


_TYPES = {"object": dict, "array": list, "string": str, "boolean": bool, "integer": int, "number": (int, float)}


def validate(value, schema, path="$"):
    t = schema.get("type")
    if t:
        types = t if isinstance(t, list) else [t]
        ok = False
        for tt in types:
            if tt == "null" and value is None:
                ok = True
            elif tt in _TYPES and isinstance(value, _TYPES[tt]) and not (tt in ("integer", "number") and isinstance(value, bool)):
                ok = True
        if not ok:
            raise SchemaError(f"{path}: cần kiểu {t}")
    if value is None:
        return
    if "enum" in schema and value not in schema["enum"]:
        raise SchemaError(f"{path}: giá trị phải thuộc {schema['enum']}")
    if isinstance(value, str) and "maxLength" in schema and len(value) > schema["maxLength"]:
        raise SchemaError(f"{path}: quá dài")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            raise SchemaError(f"{path}: nhỏ hơn {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            raise SchemaError(f"{path}: lớn hơn {schema['maximum']}")
    if isinstance(value, dict):
        props = schema.get("properties", {})
        for k in schema.get("required", []):
            if k not in value:
                raise SchemaError(f"{path}.{k}: bắt buộc")
        if schema.get("additionalProperties") is False:
            extra = set(value) - set(props)
            if extra:
                raise SchemaError(f"{path}: tham số không hỗ trợ {sorted(extra)}")
        for k, v in value.items():
            if k in props:
                validate(v, props[k], f"{path}.{k}")
    if isinstance(value, list):
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            raise SchemaError(f"{path}: quá nhiều phần tử")
        if "items" in schema:
            for i, v in enumerate(value):
                validate(v, schema["items"], f"{path}[{i}]")
