def pre_mutation(context):
    line = context.current_source_line.strip()
    if context.current_line_index != 0:
        prev_line = context.source_by_line_number[context.current_line_index - 1]
    else:
        prev_line = ""

    if line.strip().startswith("logger.") or prev_line.strip().startswith("logger."):
        context.skip = True
    if line.strip().startswith("cls.__doc__"):
        context.skip = True
