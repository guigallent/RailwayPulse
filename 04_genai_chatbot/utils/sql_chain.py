import os
import sys
import warnings
from pathlib import Path

# Silence tokenizer parallelism and deprecation warnings
os.environ["TOKENIZERS_PARALLELISM"] = "false"
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", message=".*LangChainDeprecationWarning.*")

THIS_DIR = Path(__file__).resolve().parent
REPO_ROOT = THIS_DIR.parent
sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_groq import ChatGroq

from utils.guardrails import validate_sql
from utils.prompts import SCHEMA_CONTEXT, SQL_GENERATION_SYSTEM_PROMPT
from utils.vectorstore import get_similar_examples

load_dotenv(REPO_ROOT / ".env")

GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

_SQL_PROMPT = ChatPromptTemplate.from_messages([
    ("system", SQL_GENERATION_SYSTEM_PROMPT + "\n\n" + SCHEMA_CONTEXT),
    ("human", "Similar past questions and their SQL:\n{few_shot_examples}\n\nQuestion: {question}\n\nSQL:"),
])


def _get_llm() -> ChatGroq:
    return ChatGroq(model=GROQ_MODEL, temperature=0, groq_api_key=os.getenv("GROQ_API_KEY"))


def build_sql_chain():
    return (
        RunnablePassthrough.assign(
            few_shot_examples=lambda x: get_similar_examples(x["question"], k=3)
        )
        | _SQL_PROMPT
        | _get_llm()
        | StrOutputParser()
    )


def _strip_fences(sql: str) -> str:
    """Defensive net: prompt says no markdown fences, but Groq models sometimes add them anyway."""
    sql = sql.strip()
    if sql.startswith("```"):
        lines = sql.split("\n")
        sql = "\n".join(lines[1:])
        if sql.rstrip().endswith("```"):
            sql = sql.rstrip()[:-3]
    return sql.strip()


def generate_sql(question: str) -> str:
    """
    Generates SQL from user question and validates it through safety guardrails.
    Raises ValueError if generated SQL fails security checks.
    """
    chain = build_sql_chain()
    raw = chain.invoke({"question": question})
    clean_sql = _strip_fences(raw)

    # Validate against guardrails
    is_valid, error_msg = validate_sql(clean_sql)
    if not is_valid:
        raise ValueError(f"Safety Guardrail Triggered: {error_msg}\nQuery was: {clean_sql}")

    return clean_sql


if __name__ == "__main__":
    test_questions = [
        "Which station had the most delays today?",
        "What percentage of trips at Gent-Sint-Pieters were tracked for delay?",
        "Combien de trains ont eu du retard à Bruxelles-Midi?",
    ]
    for q in test_questions:
        print(f"Q: {q}")
        try:
            sql = generate_sql(q)
            print(f"Validated SQL:\n{sql}")
        except ValueError as e:
            print(f"Validation Error: {e}")
        print("---")