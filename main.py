import json
import uuid

import streamlit as st
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.messages.tool import ToolMessage

from virtual_sales_agent.graph import graph


def set_page_config():
    st.set_page_config(
        page_title="Virtual Sales Agent Chat",
        layout="wide",
        initial_sidebar_state="expanded",
    )

def initialize_session_state():
    """Initialize session state variables."""
    if "messages" not in st.session_state:
        st.session_state.messages = []

    if "thread_id" not in st.session_state:
        st.session_state.thread_id = str(uuid.uuid4())

    if "pending_approval" not in st.session_state:
        st.session_state.pending_approval = None

    if "config" not in st.session_state:
        st.session_state.config = {
            "configurable": {
                "customer_id": "3442 587242",
                "thread_id": st.session_state.thread_id,
            }
        }


def setup_sidebar():
    """Configure the sidebar with agent information and controls."""
    with st.sidebar:
        # Agent Profile Section
        st.title("🤖 Max")
        st.markdown("### Your Virtual Sales Assistant")

        # Agent Description
        st.markdown(
            """
        Hi! I'm Max, your dedicated virtual sales assistant. I'm here to help you:
        
        - 🛒 Browse available products
        - 📦 Place and track orders
        - 💫 Get personalized recommendations
        - ❓ Answer any questions
        """
        )

        # Availability Status
        st.markdown("---")
        st.markdown("#### 🟢 Status: Online")
        st.markdown("Available 24/7 to assist you!")

        # New Chat Button
        st.markdown("---")
        if st.button("🔄 Start New Chat", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

        # Footer
        st.markdown("---")
        st.markdown("*Powered by LangGraph & Streamlit*")


def display_chat_history():
    """Display the chat history."""
    if not st.session_state.messages:
        st.markdown(
            """
            <div style='text-align: center; padding: 30px;'>
                <h1>👋 Welcome!</h1>
                <p>How can I assist you today?</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    for message in st.session_state.messages:
        role = "user" if isinstance(message, HumanMessage) else "assistant"
        with st.chat_message(role):
            st.write(message.content)


def process_events(events):
    """Process events from the graph and extract messages."""
    seen_ids = set()

    for event in events:
        if isinstance(event, dict) and "messages" in event:
            messages = event["messages"]
            last_message = messages[-1] if messages else None

            if isinstance(last_message, AIMessage):
                if last_message.id not in seen_ids and last_message.content:
                    seen_ids.add(last_message.id)
                    st.session_state.messages.append(last_message)
                    with st.chat_message("assistant"):
                        st.write(last_message.content)

                # Check for tool calls
                if hasattr(last_message, "tool_calls") and last_message.tool_calls:
                    return last_message.tool_calls[0]

    return None


def handle_tool_approval(snapshot, event):
    """Handle tool approval process."""
    st.write("⚠️ The assistant wants to perform an action. Do you approve?")

    last_message = snapshot.values.get("messages", [])[-1]

    if (
        isinstance(last_message, AIMessage)
        and hasattr(last_message, "tool_calls")
        and last_message.tool_calls
    ):
        tool_call = last_message.tool_calls[0]
        with st.chat_message("assistant"):
            st.markdown("#### 🔧 Proposed Action")

            with st.expander("View Function Details", expanded=True):
                st.info(f"Function: **{tool_call['name']}**")

                try:
                    args_formatted = json.dumps(tool_call["args"], indent=2)
                    st.code(f"Arguments:\n{args_formatted}", language="json")
                except:
                    st.code(f"Arguments:\n{tool_call['args']}")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("✅ Approve"):
            with st.spinner("Processing..."):
                try:
                    result = graph.invoke(None, st.session_state.config)
                    process_events([result])
                    st.session_state.pending_approval = None
                    st.rerun()
                except Exception as e:
                    st.error(f"Error processing approval: {str(e)}")

    with col2:
        if st.button("❌ Deny"):
            reason = st.text_input("Please explain why you're denying this action:")
            if reason and st.button("Submit", use_container_width=True):
                with st.spinner("Processing..."):
                    try:
                        result = graph.invoke(
                            {
                                "messages": [
                                    ToolMessage(
                                        tool_call_id=last_message.tool_calls[0]["id"],
                                        content=f"API call denied by user. Reasoning: '{reason}'. Continue assisting, accounting for the user's input.",
                                    )
                                ]
                            },
                            st.session_state.config,
                        )
                        process_events([result])
                        st.session_state.pending_approval = None
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error processing denial: {str(e)}")


def main():
    set_page_config()
    initialize_session_state()
    setup_sidebar()

    chat_container = st.container()
    with chat_container:
        st.markdown(
            """
            <h1 style='text-align: center; margin-bottom: 30px;'>
                🏪 Virtual Store Assistant
            </h1>
            """,
            unsafe_allow_html=True,
        )

        display_chat_history()

        if st.session_state.pending_approval:
            handle_tool_approval(*st.session_state.pending_approval)

        if prompt := st.chat_input("What would you like to order?"):
            human_message = HumanMessage(content=prompt)
            st.session_state.messages.append(human_message)
            with st.chat_message("user"):
                st.markdown(prompt)

            try:
                with st.spinner("Thinking..."):
                    events = list(
                        graph.stream(
                            {"messages": st.session_state.messages},
                            st.session_state.config,
                            stream_mode="values",
                        )
                    )

                    tool_call = process_events(events)

                    if tool_call:
                        snapshot = graph.get_state(st.session_state.config)
                        if snapshot.next:
                            for event in events:
                                st.session_state.pending_approval = (snapshot, event)
                                st.rerun()

            except Exception as e:
                st.error(f"Error processing message: {str(e)}")


if __name__ == "__main__":
    main()
