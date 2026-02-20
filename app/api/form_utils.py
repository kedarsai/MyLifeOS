from __future__ import annotations

from urllib.parse import parse_qs


async def read_form_body(request) -> dict[str, list[str]]:
    content_type = request.headers.get("content-type", "").lower()
    if "multipart/form-data" in content_type:
        # Falls back to Starlette multipart parser when available.
        form = await request.form()
        out: dict[str, list[str]] = {}
        for key, value in form.multi_items():
            out.setdefault(str(key), []).append(str(value))
        return out

    body = await request.body()
    if not body:
        return {}
    parsed = parse_qs(body.decode("utf-8"), keep_blank_values=True)
    return {str(key): [str(v) for v in values] for key, values in parsed.items()}


def form_first(data: dict[str, list[str]], key: str, default: str | None = None) -> str | None:
    values = data.get(key)
    if not values:
        return default
    return values[0]


def form_list(data: dict[str, list[str]], key: str) -> list[str]:
    return list(data.get(key, []))
