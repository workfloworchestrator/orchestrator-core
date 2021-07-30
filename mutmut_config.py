def pre_mutation(context):
    """
    Prepare mutmut context.

    This helps skipping needless mutations.
    """
    line = context.current_source_line.strip()
    if context.current_line_index != 0:
        prev_line = context.source_by_line_number[context.current_line_index - 1].strip()
    else:
        prev_line = ""

    if line.startswith("logger.") or prev_line.startswith("logger."):
        context.skip = True
    if line.startswith("logger = structlog"):
        context.skip = True
    if line.startswith("cls.__doc__"):
        context.skip = True

    # This file is copied verbatim and is not tested
    if context.filename.endswith("crypt.py"):
        context.skip = True
