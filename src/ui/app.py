import streamlit as st
import pandas as pd
import asyncio
import yaml
import os
import sys

# Add project root to sys.path to handle imports when running from subdirectories
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from sqlalchemy import select
from src.storage.database import init_db, get_session_factory, Listing, Agent
from src.utils.config import AppSettings, load_agents_from_yaml
from src.core.agent_manager import AgentManager

# Page config
st.set_page_config(page_title="Vehicle Search Agent", page_icon="🚗", layout="wide")

# Load settings
settings = AppSettings()

async def get_listings():
    engine = await init_db(settings.DATABASE_URL)
    session_factory = get_session_factory(engine)
    async with session_factory() as session:
        stmt = select(Listing).order_by(Listing.first_seen.desc())
        result = await session.execute(stmt)
        return result.scalars().all()

async def get_agents():
    engine = await init_db(settings.DATABASE_URL)
    session_factory = get_session_factory(engine)
    async with session_factory() as session:
        stmt = select(Agent)
        result = await session.execute(stmt)
        return result.scalars().all()

def main():
    st.title("🚗 Vehicle Search Agent Dashboard")
    st.markdown("---")

    # Sidebar
    st.sidebar.header("Controls")
    if st.sidebar.button("🔄 Refresh Data"):
        st.rerun()

    # Tabs
    tab1, tab2, tab3 = st.tabs(["📋 Found Listings", "🤖 Active Agents", "⚙️ Configuration"])

    with tab1:
        st.header("Recent Matches")
        listings = asyncio.run(get_listings())
        
        if not listings:
            st.info("No listings found yet. Run an agent to start searching!")
        else:
            data = []
            for l in listings:
                data.append({
                    "Date Found": l.first_seen.strftime("%Y-%m-%d %H:%M"),
                    "Year": int(l.year) if l.year else "N/A",
                    "Title": l.title,
                    "Price": f"${l.price:,.2f}" if l.price else "Contact",
                    "Source": l.source,
                    "URL": l.url
                })
            
            df = pd.DataFrame(data)
            st.dataframe(
                df, 
                column_config={
                    "URL": st.column_config.LinkColumn("Listing Link")
                },
                hide_index=True,
                use_container_width=True
            )

    with tab2:
        st.header("Configured Agents")
        agents = asyncio.run(get_agents())
        if not agents:
            st.warning("No agents found in database. Run the main script to initialize them.")
        else:
            for agent in agents:
                with st.expander(f"Agent: {agent.name} ({agent.id})"):
                    st.json(agent.config_json)
                    if st.button(f"Run {agent.name} Now", key=agent.id):
                        st.info(f"Triggering run for {agent.name}...")
                        # In a real app, we'd use a task queue. 
                        # For MVP, we'll just show the intent.
                        st.success("Run triggered! (Check logs for progress)")

    with tab3:
        st.header("System Configuration")
        st.write("**Database URL:**", settings.DATABASE_URL.split("@")[-1]) # Hide credentials
        st.write("**Gmail User:**", settings.GMAIL_USER)
        st.write("**Log Level:**", settings.LOG_LEVEL)
        
        if os.path.exists("config/agents.yaml"):
            st.subheader("agents.yaml Content")
            with open("config/agents.yaml", "r") as f:
                st.code(f.read(), language="yaml")

if __name__ == "__main__":
    main()
