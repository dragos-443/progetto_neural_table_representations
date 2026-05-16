import re
from pathlib import Path


MODEL = "gpt-5.5"       #gpt-4o-mini
DATA_DIR = Path("data")


def get_model_output_dir(model_name=MODEL):
    safe_model_name = re.sub(r"[^A-Za-z0-9._-]+", "_", model_name).strip("_")
    if not safe_model_name:
        safe_model_name = "model"
    return DATA_DIR / safe_model_name


def get_text2sql_results_dir(model_name=MODEL):
    return get_model_output_dir(model_name) / "text2sql_results"


def get_text2sql_evaluation_dir(model_name=MODEL):
    return get_model_output_dir(model_name) / "text2sql_evaluation"


def get_tableqa_results_dir(model_name=MODEL):
    return get_model_output_dir(model_name) / "tableqa_results"


def get_tableqa_evaluation_dir(model_name=MODEL):
    return get_model_output_dir(model_name) / "tableqa_evaluation"
