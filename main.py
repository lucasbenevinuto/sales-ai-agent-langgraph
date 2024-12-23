import uuid

import streamlit as st
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.messages.tool import ToolMessage

from virtual_sales_agent.graph import graph
from virtual_sales_agent.utils import _print_event


def set_page_config():
    st.set_page_config(
        page_title="Virtual Sales Agent Chat",
        layout="wide",
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


def display_chat_history():
    """Display the chat history."""
    for message in st.session_state.messages:
        role = "user" if isinstance(message, HumanMessage) else "assistant"
        with st.chat_message(role):
            st.write(message.content)


def process_events(events):
    """Process events from the graph and extract messages."""
    processed_contents = set()

    for event in events:
        if isinstance(event, dict) and "messages" in event:
            messages = event["messages"]
            if isinstance(messages, (list, tuple)):
                for msg in messages:
                    if isinstance(msg, (AIMessage, str)):
                        content = msg.content if isinstance(msg, AIMessage) else msg
                        if (
                            content
                            and content.strip()
                            and content not in processed_contents
                        ):
                            processed_contents.add(content)
                            st.session_state.messages.append(AIMessage(content=content))
                            with st.chat_message("assistant"):
                                st.write(content)


def handle_tool_approval(snapshot, event):
    """Handle tool approval process."""
    st.write("⚠️ The assistant wants to perform an action. Do you approve?")

    # Display the proposed action
    if isinstance(event, dict) and "messages" in event:
        with st.chat_message("assistant"):
            st.write("Proposed action:")
            st.write(event["messages"][-1].content)

    col1, col2 = st.columns(2)

    with col1:
        if st.button("✅ Approve"):
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
            if reason and st.button("Submit Denial"):
                try:
                    result = graph.invoke(
                        {
                            "messages": [
                                ToolMessage(
                                    tool_call_id=event["messages"][-1].tool_calls[0][
                                        "id"
                                    ],
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
    display_chat_history()

    # Handle pending approval if exists
    if st.session_state.pending_approval:
        handle_tool_approval(*st.session_state.pending_approval)

    if prompt := st.chat_input("What would you like to order?"):
        human_message = HumanMessage(content=prompt)
        st.session_state.messages.append(human_message)
        with st.chat_message("user"):
            st.markdown(prompt)

        try:
            events = list(
                graph.stream(
                    {"messages": ("user", prompt)},
                    st.session_state.config,
                    stream_mode="values",
                )
            )
            print(events)
            # Process initial response
            process_events(events)

            # Check for required approvals
            snapshot = graph.get_state(st.session_state.config)
            if snapshot.next:
                for event in events:
                    st.session_state.pending_approval = (snapshot, event)
                    st.rerun()

        except Exception as e:
            st.error(f"Error processing message: {str(e)}")


if __name__ == "__main__":
    main()
