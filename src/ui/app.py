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
st.set_page_config(page_title="LuxeLink", page_icon="💎", layout="wide")

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
    # Logo and Title
    logo_path = "Public/LuxeLink-Logo_upscayl_2x_digital-art-4x_upscayl_2x_digital-art-4x.png"
    if os.path.exists(logo_path):
        st.image(logo_path, width=300)
    
    st.title("LuxeLink Dashboard")
    st.markdown("---")

    # Sidebar
    st.sidebar.image(logo_path, use_container_width=True) if os.path.exists(logo_path) else None
    st.sidebar.header("Controls")
    if st.sidebar.button("🔄 Refresh Data"):
        st.rerun()

    # Tabs
    tab1, tab2, tab3, tab4 = st.tabs(["📋 Found Listings", "🤖 Search Profiles", "➕ Add Profile", "⚙️ Configuration"])

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
        st.header("Active Search Profiles")
        agents = asyncio.run(get_agents())
        if not agents:
            st.warning("No search profiles found. Create one in the 'Add Profile' tab!")
        else:
            for agent in agents:
                col1, col2, col3 = st.columns([0.6, 0.2, 0.2])
                with col1:
                    with st.expander(f"Profile: {agent.name} ({'Enabled' if agent.enabled else 'Disabled'})"):
                        st.json(agent.config_json)
                with col2:
                    if st.button(f"Run Now", key=f"run_{agent.id}"):
                        st.info(f"Triggering run for {agent.name}...")
                        # In a real app, we'd use a task queue.
                        st.success("Run triggered!")
                with col3:
                    status_label = "Disable" if agent.enabled else "Enable"
                    if st.button(status_label, key=f"toggle_{agent.id}"):
                        async def toggle_agent(aid, current_status):
                            engine = await init_db(settings.DATABASE_URL)
                            session_factory = get_session_factory(engine)
                            async with session_factory() as session:
                                db_agent = await session.get(Agent, aid)
                                if db_agent:
                                    db_agent.enabled = not current_status
                                    # Update config_json as well
                                    cfg = db_agent.config_json.copy()
                                    cfg["enabled"] = not current_status
                                    db_agent.config_json = cfg
                                    await session.commit()
                        asyncio.run(toggle_agent(agent.id, agent.enabled))
                        st.rerun()
                    
                    if st.button("🗑️ Delete", key=f"del_{agent.id}"):
                        async def delete_agent(aid):
                            engine = await init_db(settings.DATABASE_URL)
                            session_factory = get_session_factory(engine)
                            async with session_factory() as session:
                                db_agent = await session.get(Agent, aid)
                                if db_agent:
                                    await session.delete(db_agent)
                                    await session.commit()
                        asyncio.run(delete_agent(agent.id))
                        st.success("Profile deleted!")
                        st.rerun()

    with tab3:
        st.header("Create New Search Profile")
        with st.form("new_profile_form"):
            profile_name = st.text_input("Profile Name (e.g., Client: John Doe)")
            profile_id = profile_name.lower().replace(" ", "_")
            
            st.subheader("Vehicle Criteria")
            col1, col2, col3 = st.columns(3)
            with col1:
                make = st.text_input("Make")
            with col2:
                model = st.text_input("Model")
            with col3:
                year_min = st.number_input("Min Year", min_value=1900, max_value=2026, value=2020)
            
            st.subheader("Location")
            lcol1, lcol2 = st.columns(2)
            with lcol1:
                zip_code = st.text_input("Zip Code", value="60601")
            with lcol2:
                radius = st.number_input("Radius (miles)", value=500)
            
            sources = st.multiselect("Sources", ["bringatrailer", "cars_com", "carfax", "autonation", "marketcheck"], default=["cars_com", "carfax"])
            
            submit = st.form_submit_button("Create Profile")
            
            if submit and profile_name and make and model:
                new_config = {
                    "id": profile_id,
                    "name": profile_name,
                    "enabled": True,
                    "parameters": {
                        "vehicles": [{"make": make, "model": model, "year_min": year_min}],
                        "location": {"zip": zip_code, "radius_miles": radius}
                    },
                    "sources": sources,
                    "notifications": {"email_to": [settings.GMAIL_USER]}
                }
                
                async def save_profile(cfg):
                    engine = await init_db(settings.DATABASE_URL)
                    session_factory = get_session_factory(engine)
                    async with session_factory() as session:
                        new_agent = Agent(
                            id=cfg["id"],
                            name=cfg["name"],
                            enabled=True,
                            config_json=cfg
                        )
                        session.add(new_agent)
                        await session.commit()
                
                asyncio.run(save_profile(new_config))
                st.success(f"Profile '{profile_name}' created successfully!")
                st.rerun()

    with tab4:
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
