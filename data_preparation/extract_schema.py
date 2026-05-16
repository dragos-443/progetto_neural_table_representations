import json
import sqlite3
from pathlib import Path


SPIDER_DB_DIR = Path("spider/database")                 
SUBSET_PATH = Path("data/mini_spider_subset.json")      
OUTPUT_PATH = Path("data/db_schemas.json")              # file degli schemi dei database

# estrae i nomi di tutte le tabelle del database
def get_tables(cursor):
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    return [row[0] for row in cursor.fetchall()]

# estrae le colonne di una tabella con tipo e primary key
def get_columns(cursor, table_name):
    cursor.execute(f"PRAGMA table_info({table_name});")
    columns = cursor.fetchall()

    # PRAGMA table_info ritorna:
    # cid, name, type, notnull, default_value, pk
    return [
        {
            "name": col[1],
            "type": col[2],
            "primary_key": bool(col[5]),
        }
        for col in columns
    ]

# estrae le foreign key di una tabella
def get_foreign_keys(cursor, table_name):
    cursor.execute(f"PRAGMA foreign_key_list({table_name});")
    foreign_keys = cursor.fetchall()

    # ritorna informazioni sulle foreign key
    return [
        {
            "from_column": fk[3],
            "to_table": fk[2],
            "to_column": fk[4],
        }
        for fk in foreign_keys
    ]

# estrae lo schema completo di un database
def extract_schema(db_id):
    # percorso del database SQLite
    db_path = SPIDER_DB_DIR / db_id / f"{db_id}.sqlite"

    # controlla che il database esista
    if not db_path.exists():
        raise FileNotFoundError(f"Database non trovato: {db_path}")

    # apre la connessione al database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # struttura che conterrà lo schema
    schema = {
        "db_id": db_id,
        "tables": {},
    }

    # estrae colonne e foreign key per ogni tabella
    for table in get_tables(cursor):
        schema["tables"][table] = {
            "columns": get_columns(cursor, table),
            "foreign_keys": get_foreign_keys(cursor, table),
        }

    conn.close()
    return schema


# converte lo schema del database in testo per il prompt dell'LLM
def schema_to_prompt_text(schema):
    lines = []

    lines.append(f"Database: {schema['db_id']}")
    lines.append("Schema:")

    # scorro tutte le tabelle del database
    for table_name, table_info in schema["tables"].items():
        columns = []

        # prendo nome e tipo della colonna
        for col in table_info["columns"]:
            col_text = f"{col['name']} {col['type']}"

            # aggiungo primary key se presente
            if col["primary_key"]:
                col_text += " PRIMARY KEY"
            columns.append(col_text)

        # unisco nome tabella e colonne
        lines.append(f"- {table_name}({', '.join(columns)})")

        # aggiungo le relazioni tra tabelle tramite foreign key
        for fk in table_info["foreign_keys"]:
            lines.append(
                f"  FK: {table_name}.{fk['from_column']} -> "
                f"{fk['to_table']}.{fk['to_column']}"
            )

    # unisco tutte le righe in un unico testo
    return "\n".join(lines)


def main():
    # carico gli esempi del subset
    with open(SUBSET_PATH, "r", encoding="utf-8") as f:
        examples = json.load(f)

    # estraggo i database presenti nel subset
    db_ids = sorted(set(ex["db_id"] for ex in examples))

    # creo il dizionario che conterrà tutti gli schemi
    all_schemas = {}

    # estraggo lo schema per ogni database
    for db_id in db_ids:
        schema = extract_schema(db_id)

        # converto lo schema in testo per il prompt
        prompt_text = schema_to_prompt_text(schema)

        # salvo schema e testo del prompt
        all_schemas[db_id] = {
            "raw_schema": schema,
            "prompt_text": prompt_text,
        }

        print("=" * 80)
        print(prompt_text)

    # salvo tutti gli schemi nel file JSON
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(all_schemas, f, indent=2, ensure_ascii=False)

    print("\nSchemi salvati in:", OUTPUT_PATH)


if __name__ == "__main__":
    main()