import os
import sys
from pathlib import Path
from typing import Any, Dict, List

THIS_DIR = Path(__file__).resolve().parent
REPO_ROOT = THIS_DIR.parent
sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq

from utils.prompts import CONSULTANT_SYSTEM_PROMPT

load_dotenv(REPO_ROOT / ".env")

GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

_CONSULTANT_PROMPT = ChatPromptTemplate.from_messages([
    ("system", CONSULTANT_SYSTEM_PROMPT),
    ("human", """User Question: {question}

Database Query Executed:
{sql}

Database Results:
{results}

Provide a concise, tactical briefing (3-5 sentences) for the station manager based on these results."""),
])


def _get_llm() -> ChatGroq:
    return ChatGroq(model=GROQ_MODEL, temperature=0, groq_api_key=os.getenv("GROQ_API_KEY"))


def build_consultant_chain():
    return _CONSULTANT_PROMPT | _get_llm() | StrOutputParser()


def generate_recommendation(question: str, sql: str, results: List[Dict[str, Any]]) -> str:
    """
    Generates operational recommendations for station managers based on query results.
    """
    chain = build_consultant_chain()
    return chain.invoke({
        "question": question,
        "sql": sql,
        "results": str(results)
    })


if __name__ == "__main__":
    from utils.executor import execute_query
    from utils.sql_chain import generate_sql

    test_q = "Which station had the most delays today?"
    sql = generate_sql(test_q)
    results, _ = execute_query(sql)

    print(f"Q: {test_q}\n")
    print("Consultant Briefing:\n")
    print(generate_recommendation(test_q, sql, results))