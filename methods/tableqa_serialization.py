def _format_cell_value(value):
    """Converte i valori delle celle nel formato testuale usato da TableQA."""
    return str(value) if value is not None else "NULL"


def _serialize_table_row_wise(table_name, columns, rows):
    """
    Serializzazione riga per riga:
    Table: singer
    Singer_ID | Name | Country | Age
    1 | Alice | France | 30
    """
    lines = [
        f"Table: {table_name}",
        " | ".join(columns),
    ]

    # Ogni riga mantiene il separatore originale " | ".
    for row in rows:
        values = [_format_cell_value(value) for value in row]
        lines.append(" | ".join(values))

    return "\n".join(lines)


def _serialize_table_natural_language(table_name, columns, rows):
    """
    Serializzazione in linguaggio naturale:
    Table singer.
    Row 1: Singer_ID is 1, Name is Alice.
    """
    lines = [f"Table {table_name}."]

    for row_index, row in enumerate(rows, start=1):
        cells = [
            f"{column} is {_format_cell_value(value)}"
            for column, value in zip(columns, row)
        ]
        lines.append(f"Row {row_index}: {', '.join(cells)}.")

    return "\n".join(lines)


def _serialize_table_special_tokens(table_name, columns, rows):
    """
    Serializzazione con token speciali:
    [TABLE] singer
    [HEADER] Singer_ID | Name
    [ROW] [CELL] Singer_ID = 1 [CELL] Name = Alice
    """
    lines = [
        f"[TABLE] {table_name}",
        f"[HEADER] {' | '.join(columns)}",
    ]

    for row in rows:
        cells = [
            f"[CELL] {column} = {_format_cell_value(value)}"
            for column, value in zip(columns, row)
        ]
        lines.append(f"[ROW] {' '.join(cells)}")

    return "\n".join(lines)


def serialize_database(db_data, strategy="row_wise"):
    """
    Serializza le tabelle selezionate del database secondo la strategia richiesta.
    Le strategie supportate sono: row_wise, natural_language, special_tokens.
    """
    serializers = {
        "row_wise": _serialize_table_row_wise,
        "natural_language": _serialize_table_natural_language,
        "special_tokens": _serialize_table_special_tokens,
    }

    if strategy not in serializers:
        raise ValueError(f"Strategia di serializzazione sconosciuta: {strategy}")

    serialize_table = serializers[strategy]
    serialized_tables = []

    # Mantengo l'ordine delle tabelle fornito da db_data.
    for table_name, table in db_data.items():
        serialized_tables.append(
            serialize_table(
                table_name=table_name,
                columns=table["columns"],
                rows=table["rows"],
            )
        )

    return "\n\n".join(serialized_tables)
