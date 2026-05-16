import json
import os
import re
import sqlite3
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent
for path in (PROJECT_ROOT, SCRIPT_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from config import MODEL, get_tableqa_results_dir
from tableqa_serialization import serialize_database


SUBSET_PATH = Path("data/mini_spider_subset.json")

# Stesso path usato nella pipeline Text2SQL
SPIDER_DB_DIR = Path("spider/database")

SERIALIZATION_STRATEGY = "row_wise"  # Scegli tra "row_wise", "natural_language", "special_tokens"

USE_FEW_SHOT = True  # Attiva o disattiva gli esempi few-shot

PROMPTING_MODE = "few_shot" if USE_FEW_SHOT else "zero_shot"

OUTPUT_PATH = get_tableqa_results_dir(MODEL) / f"tableqa_results_{SERIALIZATION_STRATEGY}_{PROMPTING_MODE}.json"

# Esempi statici per guidare il formato della risposta
FEW_SHOT_EXAMPLES = """
Example 1:
Question:
List the name of singers whose citizenship is not "France".

Answer:
{"answer": [["Joe Sharp"], ["Timbaland"]]}

Example 2:
Question:
Find the average weight for each pet type.

Answer:
{"answer": [[10.6, "cat"], [11.35, "dog"]]}

Example 3:
Question:
What is the name and capacity for the stadium with highest average attendance?

Answer:
{"answer": [["Hampden Park", 52500]]}

Example 4:
Question:
What is the id and weight of every pet who is older than 1?

Answer:
{"answer": [[1, 12.0], [2, 13.4]]}
""".strip()

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))



def extract_tables_from_sql(sql: str) -> list[str]:
    tables = []
    seen = set()

    matches = re.findall(r"\b(?:FROM|JOIN)\s+([A-Za-z_][A-Za-z0-9_]*)", sql, re.IGNORECASE)

    for table_name in matches:
        normalized_name = table_name.lower()

        if normalized_name not in seen:
            tables.append(table_name)
            seen.add(normalized_name)

    return tables


# eseguo una query SQL sul database SQLite
def execute_sql(db_id, sql):

    # costruisco il percorso del database
    db_path = SPIDER_DB_DIR / db_id / f"{db_id}.sqlite"

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(sql)

        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description] if cursor.description else []

        conn.close()

        # restituisco il risultato della query
        return {
            "success": True,
            "columns": columns,
            "rows": rows,
            "error": None,
        }

    except Exception as e:
        return {
            "success": False,
            "columns": [],
            "rows": [],
            "error": str(e),
        }


# carico le oracle tables selezionate dal database
def load_selected_tables_from_db(db_id, selected_tables):

    # costruisco il percorso del database
    db_path = SPIDER_DB_DIR / db_id / f"{db_id}.sqlite"

    if not db_path.exists():
        raise FileNotFoundError(f"Database non trovato: {db_path}")

    if not selected_tables:
        raise ValueError(f"Nessuna oracle table trovata nella query per il database: {db_id}")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    db_data = {}

    for table_name in selected_tables:
        cursor.execute(f"PRAGMA table_info({table_name});")
        table_info = cursor.fetchall()

        if not table_info:
            raise ValueError(
                f"Tabella '{table_name}' non trovata nel database '{db_id}'"
            )

        columns = [col[1] for col in table_info]

        cursor.execute(f"SELECT * FROM {table_name};")
        rows = cursor.fetchall()

        db_data[table_name] = {
            "columns": columns,
            "rows": rows,
        }

    conn.close()
    return db_data

# creo prompt da inviare al LLM
def build_prompt(table_text, question, serialization_strategy, use_few_shot=False):
    # spiego al modello come leggere la serializzazione scelta
    if serialization_strategy == "row_wise":
        format_hint = """
Serialization format:
- The first line contains the table name.
- The second line contains column headers separated by "|".
- Each following line represents one row.
""".strip()
    elif serialization_strategy == "natural_language":
        format_hint = """
Serialization format:
- Tables are serialized as natural-language descriptions.
- Each sentence represents one row using column-value pairs.
""".strip()
    elif serialization_strategy == "special_tokens":
        format_hint = """
Serialization format:
- [TABLE] indicates the table name.
- [HEADER] indicates the column headers.
- [ROW] indicates a row.
- [CELL] indicates a column-value pair.
""".strip()
    else:
        format_hint = "Serialization format: read the provided tables as serialized text."

    # Blocco opzionale con esempi statici few-shot
    few_shot_block = ""
    if use_few_shot:
        few_shot_block = f"""
Here are some examples of the expected output format and reasoning style:

{FEW_SHOT_EXAMPLES}
""".strip()

    return f"""
You are a Direct Table Question Answering system.

You are given one or more database tables serialized as text.
Answer the question using ONLY the provided table data.

{format_hint}

Return ONLY a JSON object in this exact format:
{{"answer": [[value1, value2, ...], [value1, value2, ...]]}}

Rules:
- Use a list of rows.
- Each row must be a list.
- For a single scalar answer, return one row with one value, for example: {{"answer": [[5]]}}
- Preserve the requested column order.
- Do not add explanations.
- Do not use SQL.

{few_shot_block}

TABLES:
{table_text}

QUESTION:
{question}
""".strip()


# invio il prompt al modello LLM
def call_llm(prompt):
    response = client.chat.completions.create(
        model=MODEL,
        #temperature=0, # per output più deterministici, funziona con gpt-4o-mini ma non con gpt-5.5 (che è più creativo)
        messages=[{"role": "user", "content": prompt}],
    )

    answer = response.choices[0].message.content.strip()

    # pulizia se il modello restituisce markdown
    answer = answer.replace("```json", "").replace("```", "").strip()

    return answer


# converto la risposta JSON del modello in formato utilizzabile
def parse_answer(raw_answer):
    try:
        # converto la stringa JSON in dizionario Python
        parsed = json.loads(raw_answer)

        # recupero il campo "answer"
        rows = parsed.get("answer", [])

        # controllo che answer sia una lista
        if not isinstance(rows, list):
            raise ValueError("Il campo 'answer' non è una lista")

        # normalizzo le righe della risposta
        normalized_rows = []

        for row in rows:
            # se il modello restituisce un valore singolo
            # lo trasformo in lista
            if not isinstance(row, list):
                row = [row]

            normalized_rows.append(row)

        # parsing corretto
        return {
            "success": True,
            "columns": [],
            "rows": normalized_rows,
            "error": None,
            "raw_answer": raw_answer,
        }

    except Exception as e:
        return {
            "success": False,
            "columns": [],
            "rows": [],
            "error": str(e),
            "raw_answer": raw_answer,
        }


def main():
    with open(SUBSET_PATH, "r", encoding="utf-8") as f:
        examples = json.load(f)

    results = []

    for i, ex in enumerate(examples, start=1):
        db_id = ex["db_id"]
        question = ex["question"]
        gold_sql = ex["query"]
        oracle_tables = extract_tables_from_sql(gold_sql)

        gold_result = execute_sql(db_id, gold_sql)
        db_data = load_selected_tables_from_db(db_id, oracle_tables)
        table_text = serialize_database(db_data, strategy=SERIALIZATION_STRATEGY)

        prompt = build_prompt(
            table_text,
            question,
            SERIALIZATION_STRATEGY,
            USE_FEW_SHOT
        )
        raw_answer = call_llm(prompt)
        predicted_result = parse_answer(raw_answer)

        print("=" * 80)
        print(f"Esempio {i}")
        print(f"DB: {db_id}")
        print("Oracle tables:", oracle_tables)
        print("Domanda:")
        print(question)
        print("Gold rows:")
        print(gold_result["rows"])
        print("Risposta raw:")
        print(raw_answer)
        print("Parsed rows:")
        print(predicted_result["rows"])

        if not predicted_result["success"]:
            print("Errore parsing:")
            print(predicted_result["error"])

        results.append({
            "id": i,
            "db_id": db_id,
            "question": question,
            "oracle_tables": oracle_tables,
            "gold_sql": gold_sql,
            "gold_result": gold_result,
            "raw_answer": raw_answer,
            "predicted_result": predicted_result,
        })

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print("\nRisultati Table QA salvati in:", OUTPUT_PATH)


if __name__ == "__main__":
    main()
