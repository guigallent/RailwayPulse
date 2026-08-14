import sys
from pathlib import Path
import chainlit as cl

THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS_DIR))

from utils.sql_chain import generate_sql
from utils.executor import execute_query
from utils.consultant import generate_recommendation


@cl.on_chat_start
async def on_chat_start():
    await cl.Message(
        content=(
            "👋 **Welcome to RailPulse AI Co-Pilot!**\n\n"
            "I am your assistant for SNCB/NMBS station management operations "
            "(Snapshot Data: **Wednesday, August 5, 2026**).\n\n"
            "Ask me about station delays, train volume, or punctuality."
        ),
    ).send()


@cl.on_message
async def on_message(message: cl.Message):
    user_question = message.content.strip()

    async with cl.Step(name="Generating & Validating SQL") as sql_step:
        try:
            sql_query = generate_sql(user_question)
            sql_step.output = f"```sql\n{sql_query}\n```"
        except Exception as e:
            sql_step.output = f"❌ SQL Generation Error: {str(e)}"
            await cl.Message(
                content=f"⚠️ I could not generate a safe query for your request.\n\n**Reason:** `{str(e)}`"
            ).send()
            return

    async with cl.Step(
        name="Executing Query on railpulse_snapshot.db"
    ) as exec_step:
        try:
            results, columns = execute_query(sql_query)
            exec_step.output = (
                f"Retrieved {len(results)} rows.\n\nSample Output:\n`{results[:2]}`"
            )
        except Exception as e:
            exec_step.output = f"❌ Database Execution Error: {str(e)}"
            await cl.Message(
                content=f"⚠️ An error occurred while querying the snapshot database.\n\n**Reason:** `{str(e)}`"
            ).send()
            return

    async with cl.Step(name="Synthesizing Station Briefing") as consultant_step:
        try:
            briefing = generate_recommendation(
                user_question, sql_query, results
            )
            consultant_step.output = "Briefing ready."
        except Exception as e:
            await cl.Message(
                content=f"⚠️ Could not generate operational briefing.\n\n**Reason:** `{str(e)}`"
            ).send()
            return

    final_content = (
        f"{briefing}\n\n"
        f"🔍View Generated SQL Query\n\n"
        f"```sql\n{sql_query}\n```\n"

    )

    await cl.Message(content=final_content).send()