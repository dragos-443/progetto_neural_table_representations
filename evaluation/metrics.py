def normalize(rows):
    """
    Converte tutto in stringhe lowercase per confronto robusto
    """
    return [
        tuple(str(cell).strip().lower() for cell in row)
        for row in rows
    ]


def flatten(rows):
    """
    Trasforma lista di tuple in lista di celle
    """
    return [cell for row in rows for cell in row]


def cell_precision(pred_rows, gold_rows):
    pred = flatten(normalize(pred_rows))
    gold = flatten(normalize(gold_rows))

    if not pred:
        return 0.0

    correct = sum(1 for cell in pred if cell in gold)
    return correct / len(pred)


def cell_recall(pred_rows, gold_rows):
    pred = flatten(normalize(pred_rows))
    gold = flatten(normalize(gold_rows))

    if not gold:
        return 0.0

    correct = sum(1 for cell in gold if cell in pred)
    return correct / len(gold)


def tuple_cardinality(pred_rows, gold_rows):
    return abs(len(pred_rows) - len(gold_rows))


def tuple_order(pred_rows, gold_rows):
    # controlla se le righe sono nello stesso ordine del gold
    pred = normalize(pred_rows)
    gold = normalize(gold_rows)

    if len(pred) != len(gold):
        return 0

    for pred_row, gold_row in zip(pred, gold):
        if pred_row[:len(gold_row)] != gold_row:
            return 0

    return 1


def tuple_constraint(pred_rows, gold_rows):
    # controlla che ogni riga abbia lo stesso numero di colonne del gold
    pred = normalize(pred_rows)
    gold = normalize(gold_rows)

    if not gold:
        return 1 if not pred else 0

    if not pred:
        return 0

    gold_num_columns = len(gold[0])

    for gold_row in gold:
        if len(gold_row) != gold_num_columns:
            return 0

    for pred_row in pred:
        if len(pred_row) != gold_num_columns:
            return 0

    return 1
