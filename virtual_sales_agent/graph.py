import os
from datetime import datetime
from typing import Annotated

from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnableConfig
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import AnyMessage, add_messages
from langgraph.prebuilt import tools_condition
from typing_extensions import TypedDict

from virtual_sales_agent.tools import (
    check_order_status,
    create_order,
    get_available_categories,
    search_products,
    search_products_recommendations,
    get_api_welcome,
    check_api_health,
    get_db_tables,
    get_current_user,
    list_users,
    list_expenses,
    list_expense_categories,
    list_investments,
    list_goals,
    list_incomes,
    get_expenses_by_category,
    get_expenses_by_month,
    get_cashflow,
    get_financial_summary,
    get_financial_trends,
    list_projects,
    list_boards,
    list_columns,
    list_tasks,
    register_user,
    login_user,
    logout_user,
    update_user,
    delete_user,
    create_expense,
    get_expense,
    update_expense,
    delete_expense,
    create_expense_category,
    get_expense_category,
    update_expense_category,
    delete_expense_category,
    create_investment,
    get_investment,
    update_investment,
    delete_investment,
    create_goal,
    get_goal,
    update_goal,
    delete_goal,
    create_income,
    get_income,
    update_income,
    delete_income,
    create_project,
    get_project,
    update_project,
    delete_project,
    create_board,
    get_board,
    update_board,
    delete_board,
    create_column,
    get_column,
    update_column,
    delete_column,
    create_task,
    get_task,
    update_task,
    delete_task,
    send_chat_message,
    get_session_state,
    reset_session,
)
from virtual_sales_agent.utils import create_tool_node_with_fallback

load_dotenv()

os.environ["LANGCHAIN_API_KEY"] = os.getenv("LANGCHAIN_API_KEY")
os.environ["LANGCHAIN_TRACING_V2"] = os.getenv("LANGCHAIN_TRACING_V2")
os.environ["LANGCHAIN_ENDPOINT"] = os.getenv("LANGCHAIN_ENDPOINT")
os.environ["LANGCHAIN_PROJECT"] = os.getenv("LANGCHAIN_PROJECT")
os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")


class State(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    user_info: str


class Assistant:
    def __init__(self, runnable: Runnable):
        self.runnable = runnable

    def __call__(self, state: State, config: RunnableConfig):
        while True:
            configuration = config.get("configurable", {})
            customer_id = configuration.get("customer_id", None)
            state = {**state, "user_info": customer_id}
            result = self.runnable.invoke(state)
            # If the LLM happens to return an empty response, we will re-prompt it
            # for an actual response.
            if not result.tool_calls and (
                not result.content
                or isinstance(result.content, list)
                and not result.content[0].get("text")
            ):
                messages = state["messages"] + [("user", "Respond with a real output.")]
                state = {**state, "messages": messages}
            else:
                break
        return {"messages": result}


# Replace Google's LLM with OpenAI
llm = ChatOpenAI(model="gpt-4o-mini")

assistant_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """You are a versatile virtual assistant for FrontGestor, a comprehensive platform that integrates e-commerce, financial management, project management, and user administration. Your goal is to provide excellent assistance across all these domains.

USE CASES AND TOOLS:

2. FINANCIAL MANAGEMENT:
   - Track expenses (list_expenses, create_expense, update_expense, delete_expense)
   - Manage expense categories (list_expense_categories, create_expense_category, etc.)
   - Monitor investments (list_investments, create_investment, update_investment, etc.)
   - Set and track financial goals (list_goals, create_goal, update_goal, etc.)
   - Record incomes (list_incomes, create_income, update_income, etc.)
   - Analyze financial data (get_expenses_by_category, get_expenses_by_month)
   - Generate financial reports (get_cashflow, get_financial_summary, get_financial_trends)

3. PROJECT MANAGEMENT:
   - Organize projects (list_projects, create_project, update_project, etc.)
   - Manage kanban boards (list_boards, create_board, update_board, etc.)
   - Configure columns (list_columns, create_column, update_column, etc.)
   - Track tasks (list_tasks, create_task, update_task, etc.)

4. USER MANAGEMENT:
   - Handle user accounts (register_user, login_user, logout_user, update_user, delete_user)
   - View user information (get_current_user, list_users)

GUIDELINES:

- Be proactive in understanding user needs across all platform domains
- Verify user identity and permissions before performing sensitive operations
- Provide clear explanations for financial metrics and recommendations
- Help organize projects and tasks efficiently
- Present information in a structured, easy-to-understand format
- Ask clarifying questions when needed
- Provide step-by-step guidance for complex operations
- Maintain data privacy and security at all times

SYSTEM FUNCTIONS:
- Use check_api_health to verify system status
- Use get_session_state to understand user context
- Use reset_session when needed for a fresh start

Always maintain a professional, helpful tone and provide comprehensive assistance across all platform functions.

\n\nCurrent user:\n<User>\n{user_info}\n</User>
\nCurrent time: {time}.""",
        ),
        ("placeholder", "{messages}"),
    ]
).partial(time=datetime.now)

# "Read"-only tools
safe_tools = [
    get_available_categories,
    search_products,
    search_products_recommendations,
    check_order_status,
    get_api_welcome,
    check_api_health,
    get_db_tables,
    get_current_user,
    list_users,
    list_expenses,
    list_expense_categories,
    list_investments,
    list_goals,
    list_incomes,
    get_expenses_by_category,
    get_expenses_by_month,
    get_cashflow,
    get_financial_summary,
    get_financial_trends,
    list_projects,
    list_boards,
    list_columns,
    list_tasks,
]

# Sensitive tools (confirmation needed)
sensitive_tools = [
    create_order,
    register_user,
    login_user,
    logout_user,
    update_user,
    delete_user,
    create_expense,
    get_expense,
    update_expense,
    delete_expense,
    create_expense_category,
    get_expense_category,
    update_expense_category,
    delete_expense_category,
    create_investment,
    get_investment,
    update_investment,
    delete_investment,
    create_goal,
    get_goal,
    update_goal,
    delete_goal,
    create_income,
    get_income,
    update_income,
    delete_income,
    create_project,
    get_project,
    update_project,
    delete_project,
    create_board,
    get_board,
    update_board,
    delete_board,
    create_column,
    get_column,
    update_column,
    delete_column,
    create_task,
    get_task,
    update_task,
    delete_task,
    send_chat_message,
    get_session_state,
    reset_session,
]

sensitive_tool_names = {tool.name for tool in sensitive_tools}

assistant_runnable = assistant_prompt | llm.bind_tools(safe_tools + sensitive_tools)

builder = StateGraph(State)


# Define nodes: these do the work
builder.add_node("assistant", Assistant(assistant_runnable))
builder.add_node("safe_tools", create_tool_node_with_fallback(safe_tools))
builder.add_node("sensitive_tools", create_tool_node_with_fallback(sensitive_tools))


def route_tools(state: State):
    next_node = tools_condition(state)
    # If no tools are invoked, return to the user
    if next_node == END:
        return END
    ai_message = state["messages"][-1]
    # This assumes single tool calls. To handle parallel tool calling, you'd want to
    # use an ANY condition
    first_tool_call = ai_message.tool_calls[0]
    if first_tool_call["name"] in sensitive_tool_names:
        return "sensitive_tools"
    return "safe_tools"


# Define edges: these determine how the control flow moves
builder.add_edge(START, "assistant")
builder.add_conditional_edges(
    "assistant", route_tools, ["safe_tools", "sensitive_tools", END]
)
builder.add_edge("safe_tools", "assistant")
builder.add_edge("sensitive_tools", "assistant")

# Compile the graph
memory = MemorySaver()
graph = builder.compile(checkpointer=memory, interrupt_before=["sensitive_tools"])
