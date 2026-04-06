"""Internal bridge utilities."""


def extract_js_stack(exc: BaseException) -> str | None:
    """Try to extract a JS stack trace from a JSPyBridge exception.

    JSPyBridge exceptions may carry a ``stack`` attribute with the
    JavaScript stack trace string.
    """
    stack = getattr(exc, "stack", None)
    if isinstance(stack, str):
        return stack
    for chained in (exc.__cause__, exc.__context__):
        if chained is not None:
            stack = getattr(chained, "stack", None)
            if isinstance(stack, str):
                return stack
    return None
