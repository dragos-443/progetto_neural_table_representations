# Neural Table Representations

Repository for the assignment "Models and Practice of Neural Table Representations".

The project implements and evaluates two ways of answering natural-language questions over relational databases:

- **Text-to-SQL**: the model generates a SQL query, the query is executed on SQLite, and the result is compared against the ground truth.
- **Direct Table QA**: the model receives serialized tables as text and directly produces the answer in JSON format.

The evaluation follows the data-centric approach required by the assignment: the SQL string alone is not evaluated; instead, the data produced by each pipeline is evaluated.

## Assignment Objectives

The assignment requires a Python pipeline that:

- works on a controlled Spider subset;
- uses an LLM for Text-to-SQL;
- uses an LLM for Direct Table QA over serialized tables;
- compares the outputs with the gold results;
- reports Cell Precision, Cell Recall, and Tuple Cardinality;
- analyzes strengths, limitations, and failure modes of the two paradigms.

This project also implements optional metrics: Tuple Order, Tuple Constraint, and Exact Match Accuracy.

## Dataset

The subset used in the experiments is saved in:

```text
data/mini_spider_subset.json
```

It contains **20 examples** extracted from **2 Spider databases**:

- `concert_singer`
- `pets_1`

The examples were selected to cover different query patterns:

- projection;
- selection;
- join;
- aggregation;
- grouping;
- ordering;
- subquery/intersect.

The complete Spider folder must be available locally at:

```text
spider/
```

In particular, the scripts expect the SQLite databases at:

```text
spider/database/<db_id>/<db_id>.sqlite
```

The `spider/` folder is not tracked by Git because it contains large files.

## Repository Structure

```text
.
|-- config.py
|-- data/
|   |-- mini_spider_subset.json
|   |-- db_schemas.json
|   |-- ground_truth_results.json
|   |-- gpt-4o-mini/
|   |   |-- text2sql_results/
|   |   |-- text2sql_evaluation/
|   |   |-- tableqa_results/
|   |   `-- tableqa_evaluation/
|   `-- gpt-5.5/
|       |-- text2sql_results/
|       |-- text2sql_evaluation/
|       |-- tableqa_results/
|       `-- tableqa_evaluation/
|-- data_preparation/
|   |-- create_subset.py
|   |-- extract_schema.py
|   `-- generate_ground_truth.py
|-- evaluation/
|   |-- metrics.py
|   |-- evaluate_text2sql.py
|   `-- evaluate_tableqa.py
|-- methods/
|   |-- run_text2sql.py
|   |-- run_table_qa.py
|   `-- tableqa_serialization.py
`-- README.md
```

## Setup

Install the main dependencies:

```bash
pip install openai python-dotenv
```

Create a `.env` file in the project root:

```text
OPENAI_API_KEY=your_api_key_here
```

Configure the model in `config.py`:

```python
MODEL = "gpt-5.5"
```

Results are automatically saved in a model-specific subfolder, for example:

```text
data/gpt-5.5/
data/gpt-4o-mini/
```

## Data Preparation

Generate the Spider subset:

```bash
python data_preparation/create_subset.py
```

Extract the schemas of the databases used in the subset:

```bash
python data_preparation/extract_schema.py
```

Generate the ground truth by executing the gold queries:

```bash
python data_preparation/generate_ground_truth.py
```

Main outputs:

- `data/mini_spider_subset.json`: selected questions and gold SQL queries;
- `data/db_schemas.json`: SQLite schemas and text to include in prompts;
- `data/ground_truth_results.json`: gold results obtained by executing the Spider queries.

## Text-to-SQL Pipeline

Implementation:

```text
methods/run_text2sql.py
```

For each example:

1. loads the question, database, and gold SQL;
2. loads the textual schema of the database;
3. asks the LLM to generate a SQLite query;
4. executes the generated query on the local database;
5. saves the predicted SQL, predicted output, and gold output.

Run:

```bash
python methods/run_text2sql.py
```

Evaluation:

```bash
python -m evaluation.evaluate_text2sql
```

Output:

```text
data/<model>/text2sql_results/text2sql_results.json
data/<model>/text2sql_evaluation/text2sql_evaluation.json
```

Note: the assignment suggests providing only the oracle relevant tables. In the current implementation, the Text-to-SQL pipeline uses the serialized schema of the subset database, while the Direct Table QA pipeline explicitly filters the relevant tables from the gold SQL query.

## Direct Table QA Pipeline

Implementation:

```text
methods/run_table_qa.py
methods/tableqa_serialization.py
```

For each example:

1. extracts the oracle relevant tables from the gold query;
2. loads only the relevant tables from the SQLite database;
3. serializes the tables;
4. asks the LLM to answer without using SQL;
5. enforces a JSON output in the format `{"answer": [[...], ...]}`;
6. normalizes and evaluates the answer.

Implemented serialization strategies:

- `row_wise`
- `natural_language`
- `special_tokens`

The file `methods/run_table_qa.py` controls:

```python
SERIALIZATION_STRATEGY = "row_wise"
USE_FEW_SHOT = True
```

Run:

```bash
python methods/run_table_qa.py
```

Evaluate all available strategies and modes:

```bash
python -m evaluation.evaluate_tableqa
```

Output:

```text
data/<model>/tableqa_results/tableqa_results_<strategy>_<mode>.json
data/<model>/tableqa_evaluation/tableqa_evaluation_<strategy>_<mode>.json
data/<model>/tableqa_evaluation/tableqa_evaluation_summary_by_strategy_and_mode.json
```

## Metrics

The metrics are implemented in:

```text
evaluation/metrics.py
```

Required metrics:

- **Cell Precision**: percentage of predicted cells that are present in the gold output;
- **Cell Recall**: percentage of gold cells recovered in the prediction;
- **Tuple Cardinality Error**: absolute difference between the number of predicted tuples and gold tuples.

Additional metrics:

- **Tuple Order**: checks whether tuples are in the same order as the gold output;
- **Tuple Constraint**: checks whether tuples respect the expected number of columns;
- **Exact Match Accuracy**: normalized comparison between predicted rows and gold rows;
- **Execution Success Rate**: only for Text-to-SQL, measures how many predicted queries execute without error.

Unparsable outputs, invalid SQL queries, execution errors, and empty outputs are treated as failures.

## Current Results

The saved experiments compare `gpt-5.5` and `gpt-4o-mini`.

### Text-to-SQL

| Model | Examples | Cell Precision | Cell Recall | Cardinality Error | Tuple Order | Tuple Constraint | Exact Match | Execution Success |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| gpt-5.5 | 20 | 0.92 | 0.95 | 0.25 | 0.80 | 1.00 | 0.80 | 1.00 |
| gpt-4o-mini | 20 | 0.89 | 0.95 | 0.25 | 0.75 | 0.95 | 0.70 | 1.00 |

### Direct Table QA - gpt-5.5

| Serialization | Prompting | Cell Precision | Cell Recall | Cardinality Error | Tuple Order | Tuple Constraint | Exact Match |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| row_wise | few_shot | 0.89 | 0.93 | 0.10 | 0.75 | 1.00 | 0.85 |
| row_wise | zero_shot | 0.89 | 0.92 | 0.10 | 0.70 | 1.00 | 0.80 |
| natural_language | few_shot | 0.89 | 0.92 | 0.10 | 0.70 | 1.00 | 0.80 |
| natural_language | zero_shot | 0.89 | 0.92 | 0.10 | 0.70 | 1.00 | 0.80 |
| special_tokens | few_shot | 0.89 | 0.92 | 0.10 | 0.70 | 1.00 | 0.80 |
| special_tokens | zero_shot | 0.89 | 0.92 | 0.10 | 0.70 | 1.00 | 0.80 |

### Direct Table QA - gpt-4o-mini

| Serialization | Prompting | Cell Precision | Cell Recall | Cardinality Error | Tuple Order | Tuple Constraint | Exact Match |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| row_wise | few_shot | 0.63 | 0.68 | 0.40 | 0.20 | 0.95 | 0.25 |
| row_wise | zero_shot | 0.64 | 0.69 | 0.35 | 0.25 | 0.95 | 0.30 |
| natural_language | few_shot | 0.64 | 0.68 | 0.20 | 0.30 | 1.00 | 0.40 |
| natural_language | zero_shot | 0.68 | 0.69 | 0.30 | 0.30 | 0.85 | 0.45 |
| special_tokens | few_shot | 0.65 | 0.71 | 0.15 | 0.40 | 1.00 | 0.55 |
| special_tokens | zero_shot | 0.68 | 0.69 | 0.35 | 0.25 | 0.85 | 0.40 |

## Experimental Observations

- With `gpt-5.5`, Direct Table QA with `row_wise` few-shot prompting achieves the highest exact match among the saved experiments.
- Text-to-SQL remains very strong and has an execution success rate of 1.00 for both models.
- Many Text-to-SQL errors do not come from invalid SQL, but from structural differences in the output: reversed columns, extra tuples caused by `LEFT JOIN`, or aggregations expressed with a different order from the gold output.
- Direct Table QA is more sensitive to serialization, the required JSON format, and the model's ability to preserve column order.
- Cell-level metrics can be high even when exact match fails: this helps distinguish partial errors from completely wrong answers.

## Reproducibility

Recommended order to reproduce the experiment:

```bash
python data_preparation/create_subset.py
python data_preparation/extract_schema.py
python data_preparation/generate_ground_truth.py
python methods/run_text2sql.py
python -m evaluation.evaluate_text2sql
python methods/run_table_qa.py
python -m evaluation.evaluate_tableqa
```

To reproduce all Table QA configurations, rerun `methods/run_table_qa.py` while changing:

- `SERIALIZATION_STRATEGY`
- `USE_FEW_SHOT`
- `MODEL` in `config.py`, if you want to compare another model.

## Project Status

Completed:

- selection of a 20-example Spider subset;
- SQLite schema extraction;
- ground-truth generation;
- Text-to-SQL pipeline;
- Direct Table QA pipeline;
- three serialization strategies;
- zero-shot/few-shot comparison;
- evaluation with data-centric metrics;
- separate result saving by model
